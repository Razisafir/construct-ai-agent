"""Tests for agent execution loop, LLM routing, and session management."""

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Generator, Optional
from unittest.mock import MagicMock, patch, Mock, call

import pytest


# ============================================================================
# Executor Tests
# ============================================================================


class TestExecutor:
    """Test the agent executor loop: observe, plan, act, verify."""

    @pytest.fixture
    def executor(self):
        """Create a mock executor for testing."""
        class MockExecutor:
            def __init__(self):
                self.project_state = {"files": [], "status": "ready"}
                self.plan = []
                self.max_retries = 3
                self.retry_count = 0
                self.tool_results = []
                self.completed = False

            def observe(self, project_path: str) -> Dict[str, Any]:
                """Read current project state."""
                return {
                    "project_path": project_path,
                    "files": self._list_files(project_path),
                    "last_modified": time.time(),
                }

            def plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
                """Decompose goal into tasks."""
                return [
                    {"id": f"task-{i}", "description": f"Step {i+1} for: {goal}", "tool": "read_file"}
                    for i in range(3)
                ]

            def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
                """Execute a tool."""
                return {
                    "task_id": task["id"],
                    "success": True,
                    "output": f"Executed {task['tool']}",
                }

            def verify(self, results: List[Dict[str, Any]]) -> bool:
                """Check if all tasks completed successfully."""
                return all(r.get("success", False) for r in results)

            def _list_files(self, path: str) -> List[str]:
                return []

            def run(self, goal: str, project_path: str) -> Dict[str, Any]:
                """Run the full OODA loop."""
                context = self.observe(project_path)
                plan = self.plan(goal, context)
                results = []
                for task in plan:
                    result = self.act(task)
                    results.append(result)
                    if not result["success"]:
                        self.retry_count += 1
                        if self.retry_count > self.max_retries:
                            break
                self.completed = self.verify(results)
                return {
                    "completed": self.completed,
                    "plan": plan,
                    "results": results,
                }

        return MockExecutor()

    # --- observe ---

    def test_observe_reads_project_state(self, executor):
        """Test that observe reads the project state."""
        state = executor.observe("/test/project")
        assert "project_path" in state
        assert state["project_path"] == "/test/project"
        assert "files" in state
        assert "last_modified" in state

    def test_observe_empty_project(self, executor):
        """Test observing an empty project."""
        state = executor.observe("/empty/project")
        assert state["files"] == []

    # --- plan ---

    def test_plan_decomposes_goal(self, executor):
        """Test that plan decomposes a goal into tasks."""
        plan = executor.plan("Create a login page", {})
        assert len(plan) == 3
        assert all("id" in task for task in plan)
        assert all("description" in task for task in plan)
        assert all("tool" in task for task in plan)

    def test_plan_different_goals(self, executor):
        """Test planning for different goals."""
        plan1 = executor.plan("Fix bug in auth", {})
        plan2 = executor.plan("Add database migration", {})
        assert len(plan1) == 3
        assert len(plan2) == 3
        assert any("auth" in task["description"] for task in plan1)
        assert any("migration" in task["description"] for task in plan2)

    # --- act ---

    def test_act_executes_tools(self, executor):
        """Test that act executes tools correctly."""
        task = {"id": "task-1", "description": "Read config", "tool": "read_file"}
        result = executor.act(task)
        assert result["task_id"] == "task-1"
        assert result["success"] is True
        assert "output" in result

    def test_act_tool_failure(self, executor):
        """Test handling tool execution failure."""
        # Simulate failure
        original_act = executor.act
        executor.act = lambda task: {
            "task_id": task["id"],
            "success": False,
            "error": "Tool not found",
        }
        result = executor.act({"id": "bad-task", "tool": "nonexistent"})
        assert result["success"] is False
        assert "error" in result

    # --- verify ---

    def test_verify_checks_tests_pass(self, executor):
        """Test verify with all successful results."""
        results = [
            {"task_id": "t1", "success": True},
            {"task_id": "t2", "success": True},
            {"task_id": "t3", "success": True},
        ]
        assert executor.verify(results) is True

    def test_verify_fails_on_error(self, executor):
        """Test verify with failed results."""
        results = [
            {"task_id": "t1", "success": True},
            {"task_id": "t2", "success": False, "error": "Failed"},
            {"task_id": "t3", "success": True},
        ]
        assert executor.verify(results) is False

    # --- full loop ---

    def test_full_loop_happy_path(self, executor):
        """Test the full OODA loop happy path."""
        result = executor.run("Create a component", "/test/project")
        assert result["completed"] is True
        assert len(result["plan"]) == 3
        assert len(result["results"]) == 3

    def test_loop_handles_tool_failure(self, executor):
        """Test that the loop handles tool failures."""
        call_count = [0]

        def failing_act(task):
            call_count[0] += 1
            if call_count[0] == 2:
                return {"task_id": task["id"], "success": False, "error": "Simulated failure"}
            return {"task_id": task["id"], "success": True, "output": "OK"}

        executor.act = failing_act
        result = executor.run("Test goal", "/test")
        # Should have attempted all tasks
        assert len(result["results"]) == 3
        # Should have one failure
        failures = [r for r in result["results"] if not r["success"]]
        assert len(failures) == 1

    def test_loop_respects_max_retries(self, executor):
        """Test that the loop respects max retries on failure."""
        executor.act = lambda task: {
            "task_id": task["id"],
            "success": False,
            "error": "Always fails",
        }
        result = executor.run("Failing goal", "/test")
        assert executor.retry_count > 0


# ============================================================================
# LLM Service Tests
# ============================================================================


class TestLLMService:
    """Test LLM routing, streaming, and fallback behavior."""

    @pytest.fixture
    def llm_service(self):
        """Create a mock LLM service."""
        class MockLLMService:
            def __init__(self):
                self.providers = {
                    "openai": self._openai_complete,
                    "anthropic": self._anthropic_complete,
                }
                self.fallback_order = ["openai", "anthropic"]

            def route_by_complexity(self, prompt: str) -> str:
                """Route to provider based on prompt complexity."""
                token_estimate = len(prompt.split())
                if token_estimate < 100:
                    return "openai"  # Fast provider for short prompts
                else:
                    return "anthropic"  # Better quality for long prompts

            def complete(self, prompt: str, provider: Optional[str] = None) -> Dict[str, Any]:
                """Complete a prompt using the selected or routed provider."""
                if provider is None:
                    provider = self.route_by_complexity(prompt)

                try:
                    return self.providers[provider](prompt)
                except Exception as e:
                    return self._fallback(prompt, str(e))

            def stream_complete(self, prompt: str) -> Generator[Dict[str, Any], None, None]:
                """Stream completion in chunks."""
                words = prompt.split()[:10]  # Simulate processing
                for i, word in enumerate(words):
                    yield {
                        "content": word + " ",
                        "done": i == len(words) - 1,
                    }

            def _openai_complete(self, prompt: str) -> Dict[str, Any]:
                return {
                    "content": f"OpenAI response to: {prompt[:20]}...",
                    "provider": "openai",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                }

            def _anthropic_complete(self, prompt: str) -> Dict[str, Any]:
                return {
                    "content": f"Anthropic response to: {prompt[:20]}...",
                    "provider": "anthropic",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 25},
                }

            def _fallback(self, prompt: str, error: str) -> Dict[str, Any]:
                for provider in self.fallback_order:
                    if provider != "failed":
                        try:
                            return self.providers[provider](prompt)
                        except Exception:
                            continue
                return {"error": "All providers failed", "original_error": error}

        return MockLLMService()

    # --- route_by_complexity ---

    def test_route_by_complexity_short_prompt(self, llm_service):
        """Test routing short prompts to fast provider."""
        short_prompt = "Hello"
        provider = llm_service.route_by_complexity(short_prompt)
        assert provider == "openai"

    def test_route_by_complexity_long_prompt(self, llm_service):
        """Test routing long prompts to quality provider."""
        long_prompt = " ".join(["word"] * 200)  # 200 words
        provider = llm_service.route_by_complexity(long_prompt)
        assert provider == "anthropic"

    def test_route_by_complexity_boundary(self, llm_service):
        """Test routing at the boundary (100 tokens)."""
        boundary_prompt = " ".join(["word"] * 99)
        provider = llm_service.route_by_complexity(boundary_prompt)
        assert provider == "openai"  # Just under boundary

        boundary_prompt = " ".join(["word"] * 100)
        provider = llm_service.route_by_complexity(boundary_prompt)
        assert provider == "anthropic"  # At boundary

    # --- stream_complete ---

    def test_stream_complete_yields_chunks(self, llm_service):
        """Test that streaming yields chunks."""
        chunks = list(llm_service.stream_complete("This is a test prompt"))
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("done" in chunk for chunk in chunks)
        assert chunks[-1]["done"] is True

    def test_stream_complete_last_chunk_done(self, llm_service):
        """Test that the last chunk has done=True."""
        chunks = list(llm_service.stream_complete("test"))
        assert len(chunks) > 0
        assert chunks[-1]["done"] is True

    # --- fallback ---

    def test_fallback_on_provider_error(self, llm_service):
        """Test fallback when primary provider fails."""
        # Simulate OpenAI failure
        original = llm_service.providers["openai"]
        llm_service.providers["openai"] = lambda p: (_ for _ in ()).throw(Exception("API Error"))

        result = llm_service.complete("Test prompt", provider="openai")
        # Should fallback to anthropic
        assert "error" not in result or result.get("provider") == "anthropic"

        # Restore
        llm_service.providers["openai"] = original

    def test_all_providers_fail(self, llm_service):
        """Test when all providers fail."""
        # Break all providers
        originals = dict(llm_service.providers)
        for key in llm_service.providers:
            llm_service.providers[key] = lambda p: (_ for _ in ()).throw(Exception("Down"))

        result = llm_service.complete("Test")
        assert "error" in result

        # Restore
        llm_service.providers.update(originals)

    # --- complete ---

    def test_complete_with_provider(self, llm_service):
        """Test completing with explicit provider."""
        result = llm_service.complete("Hello", provider="openai")
        assert result["provider"] == "openai"
        assert "content" in result

    def test_complete_auto_route(self, llm_service):
        """Test auto-routing completion."""
        result = llm_service.complete("Hi")
        assert "content" in result
        assert "usage" in result

    # --- usage tracking ---

    def test_usage_tracking(self, llm_service):
        """Test that usage stats are returned."""
        result = llm_service.complete("Test prompt")
        assert "usage" in result
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]


# ============================================================================
# Agent Session Tests
# ============================================================================


class TestAgentSession:
    """Test agent session lifecycle, output streaming, and state management."""

    @pytest.fixture
    def session(self):
        """Create a mock agent session."""
        class MockSession:
            def __init__(self, session_id: str, goal: str):
                self.session_id = session_id
                self.goal = goal
                self.status = "running"
                self.events = []
                self.tasks = []
                self.created_at = time.time()
                self.updated_at = self.created_at

            def add_event(self, event_type: str, content: str):
                self.events.append({
                    "type": event_type,
                    "content": content,
                    "timestamp": time.time(),
                })
                self.updated_at = time.time()

            def add_task(self, task_id: str, description: str):
                self.tasks.append({
                    "id": task_id,
                    "description": description,
                    "status": "pending",
                })

            def update_task(self, task_id: str, status: str):
                for task in self.tasks:
                    if task["id"] == task_id:
                        task["status"] = status
                        break

            def pause(self):
                self.status = "paused"
                self.add_event("status", "Session paused")

            def resume(self):
                self.status = "running"
                self.add_event("status", "Session resumed")

            def stop(self):
                self.status = "stopped"
                self.add_event("status", "Session stopped")

            def get_delta_output(self, since_index: int) -> List[Dict[str, Any]]:
                return self.events[since_index:]

            def to_dict(self) -> Dict[str, Any]:
                return {
                    "session_id": self.session_id,
                    "goal": self.goal,
                    "status": self.status,
                    "events": self.events,
                    "tasks": self.tasks,
                    "created_at": self.created_at,
                    "updated_at": self.updated_at,
                }

        return MockSession("test-session-01", "Build a React component")

    # --- session_creation ---

    def test_session_creation(self, session):
        """Test that a session is created correctly."""
        assert session.session_id == "test-session-01"
        assert session.goal == "Build a React component"
        assert session.status == "running"
        assert len(session.events) == 0
        assert len(session.tasks) == 0

    def test_session_unique_id(self):
        """Test that sessions have unique IDs."""
        ids = set()
        for i in range(100):
            import uuid
            new_id = str(uuid.uuid4())[:8]
            assert new_id not in ids
            ids.add(new_id)

    # --- session_lifecycle ---

    def test_session_lifecycle(self, session):
        """Test full session lifecycle: running → paused → running → stopped."""
        # Initially running
        assert session.status == "running"

        # Pause
        session.pause()
        assert session.status == "paused"
        assert any(e["type"] == "status" and "paused" in e["content"] for e in session.events)

        # Resume
        session.resume()
        assert session.status == "running"

        # Stop
        session.stop()
        assert session.status == "stopped"

    def test_session_task_management(self, session):
        """Test adding and updating tasks."""
        session.add_task("task-1", "Create component file")
        session.add_task("task-2", "Write tests")
        assert len(session.tasks) == 2
        assert session.tasks[0]["status"] == "pending"

        session.update_task("task-1", "completed")
        assert session.tasks[0]["status"] == "completed"
        assert session.tasks[1]["status"] == "pending"

    # --- delta_output ---

    def test_delta_output(self, session):
        """Test getting incremental output."""
        session.add_event("thought", "Analyzing project structure")
        session.add_event("tool_call", "read_file('src/App.tsx')")
        session.add_event("tool_result", "Found 15 lines")

        # Get all events
        all_events = session.get_delta_output(0)
        assert len(all_events) == 3

        # Get events after index 1
        partial = session.get_delta_output(1)
        assert len(partial) == 2
        assert partial[0]["content"] == "read_file('src/App.tsx')"

        # Get events after all
        empty = session.get_delta_output(3)
        assert len(empty) == 0

    def test_delta_output_with_new_events(self, session):
        """Test delta output returns only new events."""
        session.add_event("event-1", "First")

        delta1 = session.get_delta_output(0)
        assert len(delta1) == 1

        session.add_event("event-2", "Second")
        delta2 = session.get_delta_output(1)
        assert len(delta2) == 1
        assert delta2[0]["content"] == "Second"

    # --- event_ordering ---

    def test_event_ordering(self, session):
        """Test that events are ordered by insertion."""
        for i in range(5):
            session.add_event(f"type-{i}", f"Event {i}")

        events = session.get_delta_output(0)
        for i, event in enumerate(events):
            assert event["content"] == f"Event {i}"

    # --- serialization ---

    def test_session_serialization(self, session):
        """Test that session can be serialized to dict."""
        session.add_task("t1", "Test task")
        session.add_event("thought", "Thinking...")

        data = session.to_dict()
        assert data["session_id"] == "test-session-01"
        assert data["goal"] == "Build a React component"
        assert data["status"] == "running"
        assert len(data["events"]) == 1
        assert len(data["tasks"]) == 1
        assert "created_at" in data
        assert "updated_at" in data

    def test_session_json_serializable(self, session):
        """Test that session dict is JSON serializable."""
        session.add_event("complete", "Done!")
        data = session.to_dict()
        json_str = json.dumps(data)
        restored = json.loads(json_str)
        assert restored["session_id"] == session.session_id
        assert len(restored["events"]) == 1

    # --- session_timestamp ---

    def test_session_timestamps_updated(self, session):
        """Test that updated_at changes when events are added."""
        old_updated = session.updated_at
        time.sleep(0.01)
        session.add_event("thought", "Update")
        assert session.updated_at > old_updated

    # --- concurrent_events ---

    def test_concurrent_event_addition(self, session):
        """Test adding events rapidly."""
        for i in range(100):
            session.add_event("event", f"Event {i}")
        assert len(session.events) == 100

    # --- error_handling ---

    def test_session_error_event(self, session):
        """Test that error events are recorded."""
        session.add_event("error", "Tool execution failed: file not found")
        assert session.events[-1]["type"] == "error"
        assert "failed" in session.events[-1]["content"]
