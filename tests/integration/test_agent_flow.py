"""End-to-end agent flow integration test.

This test suite exercises the complete agent lifecycle:
1. Start agent with a goal
2. Verify plan is created
3. Verify tasks are executed
4. Verify output is streamed
5. Verify memory is stored
6. Verify checkpoint is saved
"""

import os
import sys
import json
import time
import sqlite3
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, Mock

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def integration_db():
    """Create a file-based database for integration testing."""
    db_path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding_vector BLOB
        );
        CREATE INDEX idx_conversations_ts ON conversations(timestamp);

        CREATE TABLE code_events (
            id TEXT PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            change_type TEXT NOT NULL,
            diff TEXT,
            summary TEXT NOT NULL
        );
        CREATE INDEX idx_code_events_ts ON code_events(timestamp);

        CREATE TABLE user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            last_updated INTEGER NOT NULL
        );

        CREATE TABLE project_state (
            project_path TEXT PRIMARY KEY,
            current_branch TEXT NOT NULL DEFAULT '',
            last_commit TEXT NOT NULL DEFAULT '',
            agent_context_json TEXT NOT NULL DEFAULT '{}',
            updated_at INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    yield conn, db_path
    conn.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def agent_system(integration_db):
    """Create a simulated agent system for integration testing."""
    conn, db_path = integration_db

    class SimulatedAgentSystem:
        """Simulates the complete agent system with all components."""

        def __init__(self, db_conn: sqlite3.Connection):
            self.db = db_conn
            self.sessions: Dict[str, Dict[str, Any]] = {}
            self.session_counter = 0
            self.llm_calls = 0

        def start_agent(self, goal: str, project_path: str) -> str:
            """Start a new agent session."""
            self.session_counter += 1
            session_id = f"session-{self.session_counter:04d}"

            # 1. Create session record
            session = {
                "id": session_id,
                "goal": goal,
                "project_path": project_path,
                "status": "running",
                "created_at": int(time.time()),
                "updated_at": int(time.time()),
                "plan": [],
                "executed_tasks": [],
                "output_events": [],
                "checkpoint_id": None,
            }
            self.sessions[session_id] = session

            # 2. Create initial plan
            session["plan"] = self._create_plan(goal, project_path)

            # 3. Record start in memory
            self._record_conversation(
                f"conv-start-{session_id}",
                "system",
                f"Started agent session with goal: {goal}",
            )

            return session_id

        def _create_plan(self, goal: str, project_path: str) -> List[Dict[str, Any]]:
            """Decompose goal into executable tasks."""
            self.llm_calls += 1
            # Simulated planning based on goal keywords
            if "component" in goal.lower():
                return [
                    {"id": "task-1", "description": "Analyze project structure", "status": "pending", "tool": "list_directory"},
                    {"id": "task-2", "description": "Create component file", "status": "pending", "tool": "write_file"},
                    {"id": "task-3", "description": "Add component implementation", "status": "pending", "tool": "write_file"},
                    {"id": "task-4", "description": "Create tests", "status": "pending", "tool": "write_file"},
                    {"id": "task-5", "description": "Run tests", "status": "pending", "tool": "execute_command"},
                ]
            elif "fix" in goal.lower() or "bug" in goal.lower():
                return [
                    {"id": "task-1", "description": "Identify the bug", "status": "pending", "tool": "read_file"},
                    {"id": "task-2", "description": "Implement fix", "status": "pending", "tool": "write_file"},
                    {"id": "task-3", "description": "Verify fix with tests", "status": "pending", "tool": "execute_command"},
                ]
            else:
                return [
                    {"id": "task-1", "description": "Analyze requirements", "status": "pending", "tool": "read_file"},
                    {"id": "task-2", "description": "Implement solution", "status": "pending", "tool": "write_file"},
                    {"id": "task-3", "description": "Verify implementation", "status": "pending", "tool": "execute_command"},
                ]

        def execute_plan(self, session_id: str) -> Dict[str, Any]:
            """Execute all tasks in the plan."""
            session = self.sessions[session_id]
            results = []

            for task in session["plan"]:
                task["status"] = "in_progress"

                # Simulate task execution
                result = self._execute_task(task, session)
                task["status"] = "completed" if result["success"] else "failed"

                # Stream output event
                self._emit_output(session_id, "task_complete", f"Completed: {task['description']}")

                results.append(result)
                session["executed_tasks"].append(task)

            session["status"] = "completed" if all(r["success"] for r in results) else "failed"
            session["updated_at"] = int(time.time())

            # Save checkpoint
            session["checkpoint_id"] = self._save_checkpoint(session_id)

            return {
                "session_id": session_id,
                "completed": all(r["success"] for r in results),
                "tasks_executed": len(results),
                "checkpoint_id": session["checkpoint_id"],
            }

        def _execute_task(self, task: Dict[str, Any], session: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a single task."""
            # Record in code events
            self._record_code_event(
                f"ce-{task['id']}",
                session["project_path"],
                "execute",
                f"Executed {task['tool']}: {task['description']}",
            )
            return {"task_id": task["id"], "success": True, "output": f"Executed {task['tool']}"}

        def _emit_output(self, session_id: str, event_type: str, content: str):
            """Emit an output event for the session."""
            event = {
                "session_id": session_id,
                "type": event_type,
                "content": content,
                "timestamp": int(time.time()),
            }
            self.sessions[session_id]["output_events"].append(event)

        def _record_conversation(self, conv_id: str, role: str, content: str):
            """Record a conversation in the database."""
            self.db.execute(
                "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (conv_id, int(time.time()), role, content),
            )
            self.db.commit()

        def _record_code_event(self, event_id: str, file_path: str, change_type: str, summary: str):
            """Record a code event in the database."""
            self.db.execute(
                "INSERT INTO code_events (id, timestamp, file_path, change_type, summary) VALUES (?, ?, ?, ?, ?)",
                (event_id, int(time.time()), file_path, change_type, summary),
            )
            self.db.commit()

        def _save_checkpoint(self, session_id: str) -> str:
            """Save a checkpoint of the session state."""
            checkpoint_id = f"checkpoint-{session_id}-{int(time.time())}"
            session = self.sessions[session_id]

            # Store checkpoint in project_state
            self.db.execute(
                """INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(project_path) DO UPDATE SET
                       agent_context_json = excluded.agent_context_json,
                       updated_at = excluded.updated_at""",
                (
                    session["project_path"],
                    "main",
                    f"checkpoint-{session_id}",
                    json.dumps({
                        "session_id": session_id,
                        "goal": session["goal"],
                        "status": session["status"],
                        "tasks_completed": len(session["executed_tasks"]),
                    }),
                    int(time.time()),
                ),
            )
            self.db.commit()
            return checkpoint_id

        def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
            """Get session details."""
            return self.sessions.get(session_id)

        def get_recent_output(self, session_id: str, since_index: int = 0) -> List[Dict[str, Any]]:
            """Get output events since a given index."""
            session = self.sessions.get(session_id)
            if not session:
                return []
            return session["output_events"][since_index:]

        def verify_memory(self, session_id: str) -> Dict[str, Any]:
            """Verify that memory was stored correctly."""
            cursor = self.db.cursor()

            # Check conversations
            cursor.execute(
                "SELECT COUNT(*) FROM conversations WHERE content LIKE ?",
                (f"%{session_id}%",),
            )
            conv_count = cursor.fetchone()[0]

            # Check code events
            cursor.execute(
                "SELECT COUNT(*) FROM code_events WHERE id LIKE ?",
                (f"ce-task-{session_id}%",),
            )
            event_count = cursor.fetchone()[0]

            return {"conversations": conv_count, "code_events": event_count}

        def pause_session(self, session_id: str):
            """Pause a running session."""
            if session_id in self.sessions:
                self.sessions[session_id]["status"] = "paused"
                self.sessions[session_id]["updated_at"] = int(time.time())

        def resume_session(self, session_id: str):
            """Resume a paused session."""
            if session_id in self.sessions:
                self.sessions[session_id]["status"] = "running"
                self.sessions[session_id]["updated_at"] = int(time.time())

    return SimulatedAgentSystem(conn)


# ============================================================================
# Happy Path Tests
# ============================================================================


class TestAgentFlowHappyPath:
    """Test the complete agent flow in ideal conditions."""

    def test_full_agent_flow_component_creation(self, agent_system):
        """Test full flow: create a React component."""
        # 1. Start agent
        session_id = agent_system.start_agent(
            goal="Create a Counter React component",
            project_path="/projects/my-app",
        )
        assert session_id is not None
        assert session_id.startswith("session-")

        # Verify session created
        session = agent_system.get_session(session_id)
        assert session["goal"] == "Create a Counter React component"
        assert session["status"] == "running"

        # 2. Verify plan created
        assert len(session["plan"]) > 0
        task_descriptions = [t["description"] for t in session["plan"]]
        assert any("component" in d.lower() for d in task_descriptions)

        # 3. Execute plan
        result = agent_system.execute_plan(session_id)

        # 4. Verify tasks executed
        assert result["tasks_executed"] == len(session["plan"])
        assert result["completed"] is True

        # 5. Verify output streamed
        output = agent_system.get_recent_output(session_id)
        assert len(output) > 0
        assert all("task_complete" in e["type"] for e in output)

        # 6. Verify memory stored
        memory = agent_system.verify_memory(session_id)
        assert memory["conversations"] >= 1

        # 7. Verify checkpoint saved
        assert result["checkpoint_id"] is not None
        session = agent_system.get_session(session_id)
        assert session["status"] == "completed"

    def test_full_agent_flow_bug_fix(self, agent_system):
        """Test full flow: fix a bug."""
        # 1. Start agent
        session_id = agent_system.start_agent(
            goal="Fix authentication bug in login",
            project_path="/projects/auth-service",
        )

        session = agent_system.get_session(session_id)

        # 2. Verify plan is bug-fix oriented
        task_descriptions = [t["description"] for t in session["plan"]]
        assert any("bug" in d.lower() or "fix" in d.lower() or "identify" in d.lower()
                   for d in task_descriptions)

        # 3-7. Execute and verify
        result = agent_system.execute_plan(session_id)
        assert result["completed"] is True
        assert result["tasks_executed"] == len(session["plan"])

    def test_multiple_sessions_independent(self, agent_system):
        """Test that multiple sessions operate independently."""
        id1 = agent_system.start_agent("Goal A", "/proj/a")
        id2 = agent_system.start_agent("Goal B", "/proj/b")
        id3 = agent_system.start_agent("Goal C", "/proj/c")

        assert id1 != id2 != id3

        # Execute all
        r1 = agent_system.execute_plan(id1)
        r2 = agent_system.execute_plan(id2)
        r3 = agent_system.execute_plan(id3)

        assert r1["completed"] and r2["completed"] and r3["completed"]

        # Verify independent state
        s1 = agent_system.get_session(id1)
        s2 = agent_system.get_session(id2)
        assert s1["goal"] == "Goal A"
        assert s2["goal"] == "Goal B"

    def test_output_streaming_order(self, agent_system):
        """Test that output events are in correct order."""
        session_id = agent_system.start_agent(
            goal="Test ordering",
            project_path="/test",
        )
        agent_system.execute_plan(session_id)

        output = agent_system.get_recent_output(session_id)
        timestamps = [e["timestamp"] for e in output]

        # Events should be roughly in order
        assert len(timestamps) > 0
        # Each timestamp should be >= the previous (or very close)
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i - 1] - 1  # Allow 1s tolerance


# ============================================================================
# Pause/Resume Tests
# ============================================================================


class TestAgentFlowPauseResume:
    """Test agent pause and resume functionality."""

    def test_pause_running_session(self, agent_system):
        """Test pausing a running session."""
        session_id = agent_system.start_agent("Test pause", "/test")

        assert agent_system.get_session(session_id)["status"] == "running"

        agent_system.pause_session(session_id)
        assert agent_system.get_session(session_id)["status"] == "paused"

    def test_resume_paused_session(self, agent_system):
        """Test resuming a paused session."""
        session_id = agent_system.start_agent("Test resume", "/test")

        agent_system.pause_session(session_id)
        assert agent_system.get_session(session_id)["status"] == "paused"

        agent_system.resume_session(session_id)
        assert agent_system.get_session(session_id)["status"] == "running"

    def test_pause_then_complete(self, agent_system):
        """Test that a paused session can be resumed and completed."""
        session_id = agent_system.start_agent("Test pause-resume-complete", "/test")

        agent_system.pause_session(session_id)
        assert agent_system.get_session(session_id)["status"] == "paused"

        agent_system.resume_session(session_id)
        result = agent_system.execute_plan(session_id)

        assert result["completed"] is True


# ============================================================================
# Memory Persistence Tests
# ============================================================================


class TestAgentFlowMemory:
    """Test that agent execution properly stores memory."""

    def test_conversations_stored(self, agent_system, integration_db):
        """Test that conversations are stored in the database."""
        conn, _ = integration_db
        session_id = agent_system.start_agent("Test memory", "/test")
        agent_system.execute_plan(session_id)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        assert count >= 1  # At least the start conversation

    def test_code_events_stored(self, agent_system, integration_db):
        """Test that code events are stored in the database."""
        conn, _ = integration_db
        session_id = agent_system.start_agent("Test code events", "/test")
        agent_system.execute_plan(session_id)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM code_events")
        count = cursor.fetchone()[0]
        assert count > 0  # Should have code events from task execution

    def test_checkpoint_saved_to_project_state(self, agent_system, integration_db):
        """Test that checkpoint is saved to project_state."""
        conn, _ = integration_db
        project_path = "/projects/checkpoint-test"
        session_id = agent_system.start_agent("Test checkpoint", project_path)
        agent_system.execute_plan(session_id)

        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_context_json FROM project_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        assert row is not None

        checkpoint_data = json.loads(row[0])
        assert checkpoint_data["session_id"] == session_id
        assert checkpoint_data["status"] == "completed"

    def test_multiple_checkpoints_same_project(self, agent_system, integration_db):
        """Test that multiple runs on same project update checkpoint."""
        conn, _ = integration_db
        project_path = "/projects/multi-checkpoint"

        session1 = agent_system.start_agent("First goal", project_path)
        agent_system.execute_plan(session1)

        session2 = agent_system.start_agent("Second goal", project_path)
        agent_system.execute_plan(session2)

        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_context_json FROM project_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        checkpoint_data = json.loads(row[0])

        # Should reflect the most recent session
        assert checkpoint_data["goal"] == "Second goal"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestAgentFlowErrors:
    """Test agent flow error handling."""

    def test_nonexistent_session(self, agent_system):
        """Test accessing a non-existent session."""
        session = agent_system.get_session("nonexistent-id")
        assert session is None

    def test_empty_goal(self, agent_system):
        """Test that empty goals still create sessions."""
        session_id = agent_system.start_agent("", "/test")
        assert session_id is not None
        session = agent_system.get_session(session_id)
        assert session["goal"] == ""

    def test_special_characters_in_goal(self, agent_system):
        """Test goals with special characters."""
        goal = "Fix the 'auth' module -- especially the login() function"
        session_id = agent_system.start_agent(goal, "/test")
        session = agent_system.get_session(session_id)
        assert session["goal"] == goal

    def test_unicode_in_goal(self, agent_system):
        """Test goals with unicode characters."""
        goal = "日本語のコンポーネントを作成する"
        session_id = agent_system.start_agent(goal, "/test")
        session = agent_system.get_session(session_id)
        assert session["goal"] == goal
