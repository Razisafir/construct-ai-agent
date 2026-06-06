"""
Multi-Agent Orchestrator — Foundation for Phase 5 multi-agent collaboration.

Coordinates multiple specialized agents (Planner, Coder, Tester, Reviewer,
Security, DevOps) working together on complex tasks with dependency tracking,
parallel execution, and inter-agent communication.

This is FOUNDATION ONLY — not wired into UI yet. UI integration comes in Phase 5.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and data models
# ---------------------------------------------------------------------------


class AgentRole(Enum):
    """Specialized roles that agents can assume within the orchestrator."""

    PLANNER = "planner"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    SECURITY = "security"
    DEVOPS = "devops"


@dataclass
class AgentTask:
    """
    A single unit of work assigned to an agent.

    Tasks can declare dependencies on other tasks by ID; a task will only
    be scheduled for execution once all of its dependencies have completed
    successfully.
    """

    id: str
    role: AgentRole
    description: str
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the task to a JSON-friendly dictionary."""
        return {
            "id": self.id,
            "role": self.role.value,
            "description": self.description,
            "dependencies": self.dependencies,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "artifacts": self.artifacts,
        }

    @property
    def duration_s(self) -> Optional[float]:
        """Return task duration in seconds, or None if not yet completed."""
        if self.started_at is not None and self.completed_at is not None:
            return round(self.completed_at - self.started_at, 3)
        return None


@dataclass
class AgentMessage:
    """
    A message exchanged between agents.

    Messages can be directed (``to_role`` is set) or broadcast
    (``to_role`` is None). The message log is retained for the UI
    timeline visualization in Phase 5.
    """

    from_role: AgentRole
    to_role: Optional[AgentRole]  # None = broadcast
    content: str
    message_type: str = "info"  # "info" | "request" | "result" | "warning" | "error"
    task_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the message to a JSON-friendly dictionary."""
        return {
            "from_role": self.from_role.value,
            "to_role": self.to_role.value if self.to_role else None,
            "content": self.content,
            "message_type": self.message_type,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Multi-Agent Orchestrator
# ---------------------------------------------------------------------------


class MultiAgentOrchestrator:
    """
    Orchestrates multiple specialized agents working on a complex task.

    Example workflow — ``"Build a secure web app with auth"``:

    1. **Planner** creates a task breakdown (auth system, database, API, frontend).
    2. **Security** reviews the plan for security issues.
    3. **Coder** implements each component (respecting dependency order).
    4. **Tester** writes and runs tests for each component.
    5. **Reviewer** performs a final code review.
    6. **Security** runs a security scan on the completed code.

    Foundation only — not wired into UI.  Phase 5 will add:

    - Real-time agent visualization
    - Agent conflict resolution UI
    - Manual override controls
    - Artifact browsing

    Parameters
    ----------
    llm_provider:
        An optional LLM service instance.  If *None*, the orchestrator
        operates in **mock mode** and returns stub responses that
        demonstrate the workflow.
    """

    def __init__(self, llm_provider: Any = None) -> None:
        self.llm_provider = llm_provider
        self.tasks: Dict[str, AgentTask] = {}
        self.messages: List[AgentMessage] = []
        self.execution_log: List[Dict[str, Any]] = []
        self._task_counter: int = 0

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def create_task(
        self,
        role: AgentRole,
        description: str,
        dependencies: Optional[List[str]] = None,
    ) -> AgentTask:
        """
        Create a new :class:`AgentTask` and register it with the orchestrator.

        Parameters
        ----------
        role:
            The agent role responsible for this task.
        description:
            Human-readable description of what the task entails.
        dependencies:
            List of task IDs that must complete before this task can start.

        Returns
        -------
        AgentTask
            The newly created (and registered) task.
        """
        self._task_counter += 1
        task_id = f"task-{self._task_counter:03d}-{uuid.uuid4().hex[:6]}"
        task = AgentTask(
            id=task_id,
            role=role,
            description=description,
            dependencies=dependencies or [],
        )
        self.tasks[task_id] = task
        logger.info("Created task %s [%s]: %s", task_id, role.value, description)
        return task

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def execute_complex_task(self, user_request: str) -> Dict[str, Any]:
        """
        Execute a complex multi-agent task from start to finish.

        This is the primary public API.  It coordinates the full pipeline:

        1. **Planner** breaks the request into ordered sub-tasks.
        2. **Security** reviews the plan for risks.
        3. Tasks are executed in dependency order (parallel where possible).
        4. **Tester** verifies the implementation.
        5. **Reviewer** performs a final code review.
        6. **Security** runs a final security scan.

        Parameters
        ----------
        user_request:
            The high-level user request (e.g. "Build a secure REST API with auth").

        Returns
        -------
        dict
            A structured result containing the plan, task outcomes,
            test results, review feedback, security scan results, and
            an overall status.
        """
        start_time = time.time()
        self._log("orchestrator", "started", {"request": user_request})

        try:
            # Step 1 — Planner creates the task breakdown
            self._log("planner", "started", {"request": user_request})
            plan = await self._run_planner(user_request)
            self._log("planner", "completed", {"task_count": len(plan)})
            self._send_message(
                AgentRole.PLANNER,
                None,
                f"Plan created with {len(plan)} tasks",
                message_type="result",
            )

            # Step 2 — Security reviews the plan
            self._log("security", "plan_review_started", {})
            security_review = await self._run_security_review(plan)
            self._log("security", "plan_review_completed", security_review)
            if security_review.get("issues"):
                self._send_message(
                    AgentRole.SECURITY,
                    AgentRole.PLANNER,
                    f"Security review found {len(security_review['issues'])} issues",
                    message_type="warning",
                )

            # Step 3 — Execute all tasks (respecting dependencies)
            self._log("executor", "started", {"task_count": len(plan)})
            execution_results = await self._execute_tasks(plan)
            self._log("executor", "completed", execution_results)

            # Step 4 — Tester verifies the implementation
            self._log("tester", "started", {})
            test_results = await self._run_tests(execution_results)
            self._log("tester", "completed", test_results)
            self._send_message(
                AgentRole.TESTER,
                None,
                f"Testing complete: {test_results.get('passed', 0)} passed, "
                f"{test_results.get('failed', 0)} failed",
                message_type="result",
            )

            # Step 5 — Reviewer performs final code review
            self._log("reviewer", "started", {})
            review_results = await self._run_review(execution_results)
            self._log("reviewer", "completed", review_results)

            # Step 6 — Security runs final scan
            self._log("security", "final_scan_started", {})
            final_security = await self._run_security_scan(execution_results)
            self._log("security", "final_scan_completed", final_security)

            # Determine overall status
            failed_tasks = [
                t.to_dict()
                for t in self.tasks.values()
                if t.status == "failed"
            ]
            overall_status = "completed" if not failed_tasks else "completed_with_failures"

            elapsed = round(time.time() - start_time, 3)
            self._log("orchestrator", "finished", {"status": overall_status, "elapsed_s": elapsed})

            return {
                "status": overall_status,
                "request": user_request,
                "plan": [t.to_dict() for t in plan],
                "security_review": security_review,
                "execution_results": execution_results,
                "test_results": test_results,
                "review_results": review_results,
                "final_security_scan": final_security,
                "failed_tasks": failed_tasks,
                "messages": [m.to_dict() for m in self.messages],
                "elapsed_s": elapsed,
            }

        except Exception as exc:
            elapsed = round(time.time() - start_time, 3)
            logger.exception("Orchestrator failed: %s", exc)
            self._log("orchestrator", "failed", {"error": str(exc), "elapsed_s": elapsed})
            return {
                "status": "failed",
                "request": user_request,
                "error": str(exc),
                "elapsed_s": elapsed,
                "partial_tasks": [t.to_dict() for t in self.tasks.values()],
                "messages": [m.to_dict() for m in self.messages],
            }

    # ------------------------------------------------------------------
    # Planner agent
    # ------------------------------------------------------------------

    async def _run_planner(self, request: str) -> List[AgentTask]:
        """
        Break a high-level request into an ordered list of sub-tasks.

        If :attr:`llm_provider` is available, the planner uses it to
        intelligently decompose the request.  Otherwise a heuristic-based
        mock decomposition is returned.

        Parameters
        ----------
        request:
            The user's high-level request.

        Returns
        -------
        list[AgentTask]
            Ordered list of tasks with dependency links.
        """
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                prompt = (
                    "You are a planning agent. Break the following request into "
                    "ordered sub-tasks. For each task specify: role (one of: "
                    "planner, coder, tester, reviewer, security, devops), "
                    "description, and dependencies (0-based indices of tasks "
                    "that must complete first).\n\n"
                    f"Request: {request}\n\n"
                    "Respond with a JSON array. Example:\n"
                    '[{"role": "coder", "description": "Implement auth module", '
                    '"dependencies": []}, ...]'
                )
                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                tasks_data = json.loads(response)
                return self._build_tasks_from_plan(tasks_data)
            except Exception as exc:
                logger.warning("LLM planner failed, falling back to mock: %s", exc)

        # Mock / fallback planner
        return self._mock_plan(request)

    def _build_tasks_from_plan(self, tasks_data: List[Dict[str, Any]]) -> List[AgentTask]:
        """
        Convert a raw LLM plan into :class:`AgentTask` objects with resolved
        dependency IDs.

        Parameters
        ----------
        tasks_data:
            List of dicts with keys ``role``, ``description``, ``dependencies``
            (0-based indices).

        Returns
        -------
        list[AgentTask]
        """
        created: List[AgentTask] = []
        id_map: Dict[int, str] = {}

        for idx, item in enumerate(tasks_data):
            role = AgentRole(item.get("role", "coder"))
            dep_indices = item.get("dependencies", [])
            dep_ids = [id_map[i] for i in dep_indices if i in id_map]
            task = self.create_task(role, item["description"], dep_ids)
            id_map[idx] = task.id
            created.append(task)

        return created

    def _mock_plan(self, request: str) -> List[AgentTask]:
        """
        Generate a mock plan with heuristic task decomposition.

        This is used when no LLM provider is configured, or as a fallback
        when the LLM call fails.

        Parameters
        ----------
        request:
            The user's high-level request.

        Returns
        -------
        list[AgentTask]
        """
        request_lower = request.lower()

        # Step 1: Design / architecture (planner)
        t1 = self.create_task(
            AgentRole.PLANNER,
            f"Design architecture for: {request}",
        )

        # Step 2: Core implementation (coder) — depends on design
        t2 = self.create_task(
            AgentRole.CODER,
            f"Implement core functionality for: {request}",
            dependencies=[t1.id],
        )

        # Step 3: Infrastructure / DevOps — depends on design
        t3 = self.create_task(
            AgentRole.DEVOPS,
            f"Set up deployment and CI/CD for: {request}",
            dependencies=[t1.id],
        )

        # Step 4: Additional feature work — depends on core
        if "auth" in request_lower or "security" in request_lower or "secure" in request_lower:
            t4 = self.create_task(
                AgentRole.CODER,
                "Implement authentication and authorization system",
                dependencies=[t2.id],
            )
        elif "api" in request_lower or "rest" in request_lower:
            t4 = self.create_task(
                AgentRole.CODER,
                "Implement API endpoints and request validation",
                dependencies=[t2.id],
            )
        else:
            t4 = self.create_task(
                AgentRole.CODER,
                f"Implement additional features for: {request}",
                dependencies=[t2.id],
            )

        # Step 5: Write tests — depends on core + additional
        t5 = self.create_task(
            AgentRole.TESTER,
            f"Write and run tests for: {request}",
            dependencies=[t2.id, t4.id],
        )

        # Step 6: Code review — depends on all code tasks
        t6 = self.create_task(
            AgentRole.REVIEWER,
            f"Review code quality for: {request}",
            dependencies=[t2.id, t4.id],
        )

        # Step 7: Final security scan — depends on review
        t7 = self.create_task(
            AgentRole.SECURITY,
            f"Run security scan on final code for: {request}",
            dependencies=[t6.id],
        )

        return [t1, t2, t3, t4, t5, t6, t7]

    # ------------------------------------------------------------------
    # Security review of plan
    # ------------------------------------------------------------------

    async def _run_security_review(self, plan: List[AgentTask]) -> Dict[str, Any]:
        """
        Have the security agent review the task plan for potential risks.

        Parameters
        ----------
        plan:
            The list of planned tasks.

        Returns
        -------
        dict
            ``approved`` flag, list of ``issues``, and ``recommendations``.
        """
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                plan_summary = json.dumps(
                    [t.to_dict() for t in plan], indent=2
                )
                prompt = (
                    "You are a security reviewer. Review the following task plan "
                    "for security risks. Identify any issues and provide "
                    "recommendations.\n\n"
                    f"Plan:\n{plan_summary}\n\n"
                    'Respond with JSON: {"approved": true/false, '
                    '"issues": [...], "recommendations": [...]}'
                )
                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                return json.loads(response)
            except Exception as exc:
                logger.warning("LLM security review failed, using mock: %s", exc)

        # Mock security review
        issues: List[str] = []
        recommendations: List[str] = []
        plan_descriptions = " ".join(t.description.lower() for t in plan)

        if "auth" not in plan_descriptions and "authentication" not in plan_descriptions:
            if any("auth" in t.description.lower() or "secure" in t.description.lower() for t in plan):
                pass  # auth is covered
            else:
                issues.append("No authentication task in plan")
                recommendations.append(
                    "Add an authentication/authorization task"
                )

        if "test" not in plan_descriptions:
            issues.append("No testing task in plan")
            recommendations.append("Add a testing task before deployment")

        approved = len(issues) == 0
        return {
            "approved": approved,
            "issues": issues,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Task execution engine
    # ------------------------------------------------------------------

    async def _execute_tasks(self, plan: List[AgentTask]) -> Dict[str, Any]:
        """
        Execute all tasks respecting dependency order.

        Tasks whose dependencies are all met run in parallel using
        :func:`asyncio.gather`.  The loop continues until every task
        has been processed or no further progress is possible (deadlock).

        Parameters
        ----------
        plan:
            The ordered list of tasks to execute.

        Returns
        -------
        dict
            ``completed``, ``failed``, ``skipped`` counts and per-task
            results keyed by task ID.
        """
        completed_count = 0
        failed_count = 0
        skipped_count = 0
        task_results: Dict[str, Any] = {}

        remaining = set(t.id for t in plan)
        max_iterations = len(plan) + 1  # guard against infinite loops

        for iteration in range(max_iterations):
            if not remaining:
                break

            # Find tasks whose dependencies are all met
            ready = [
                tid
                for tid in remaining
                if self._dependencies_met(self.tasks[tid])
            ]

            if not ready:
                # Deadlock: remaining tasks have unresolvable dependencies
                logger.warning(
                    "Deadlock detected: %d tasks cannot proceed", len(remaining)
                )
                for tid in remaining:
                    task = self.tasks[tid]
                    task.status = "failed"
                    task.error = "Unresolvable dependency (deadlock)"
                    task.completed_at = time.time()
                    failed_count += 1
                    task_results[tid] = task.to_dict()
                    self._log(
                        "executor",
                        "task_deadlocked",
                        {"task_id": tid, "dependencies": task.dependencies},
                    )
                break

            # Execute ready tasks in parallel
            async def _run_single(task_id: str) -> tuple:
                task = self.tasks[task_id]
                return task_id, await self._execute_single_task(task)

            results = await asyncio.gather(
                *[_run_single(tid) for tid in ready],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    # Shouldn't happen since _execute_single_task catches
                    # errors, but handle defensively
                    logger.error("Unexpected task execution error: %s", result)
                    failed_count += 1
                    continue

                task_id, task_result = result
                task = self.tasks[task_id]
                remaining.discard(task_id)

                if task.status == "completed":
                    completed_count += 1
                    task_results[task_id] = task_result
                elif task.status == "failed":
                    failed_count += 1
                    task_results[task_id] = task_result
                    # Mark dependent tasks as skipped
                    for other_id in list(remaining):
                        other = self.tasks[other_id]
                        if task_id in other.dependencies:
                            other.status = "failed"
                            other.error = f"Dependency {task_id} failed"
                            other.completed_at = time.time()
                            remaining.discard(other_id)
                            skipped_count += 1
                            task_results[other_id] = other.to_dict()

        return {
            "completed": completed_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "results": task_results,
        }

    async def _execute_single_task(self, task: AgentTask) -> Dict[str, Any]:
        """
        Execute one task using the appropriate agent role.

        Parameters
        ----------
        task:
            The task to execute.

        Returns
        -------
        dict
            Serialized task result.
        """
        task.status = "running"
        task.started_at = time.time()
        self._log(
            task.role.value,
            "task_started",
            {"task_id": task.id, "description": task.description},
        )
        self._send_message(
            task.role,
            None,
            f"Starting: {task.description}",
            message_type="info",
            task_id=task.id,
        )

        try:
            # Route to the appropriate agent handler
            if task.role == AgentRole.PLANNER:
                result = await self._agent_planner(task)
            elif task.role == AgentRole.CODER:
                result = await self._agent_coder(task)
            elif task.role == AgentRole.TESTER:
                result = await self._agent_tester(task)
            elif task.role == AgentRole.REVIEWER:
                result = await self._agent_reviewer(task)
            elif task.role == AgentRole.SECURITY:
                result = await self._agent_security(task)
            elif task.role == AgentRole.DEVOPS:
                result = await self._agent_devops(task)
            else:
                result = {"output": f"Unknown role: {task.role.value}"}

            task.result = result
            task.status = "completed"
            task.completed_at = time.time()
            self._log(
                task.role.value,
                "task_completed",
                {"task_id": task.id, "duration_s": task.duration_s},
            )
            self._send_message(
                task.role,
                None,
                f"Completed: {task.description}",
                message_type="result",
                task_id=task.id,
            )

        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            task.completed_at = time.time()
            logger.error("Task %s failed: %s", task.id, exc)
            self._log(
                task.role.value,
                "task_failed",
                {"task_id": task.id, "error": str(exc)},
            )
            self._send_message(
                task.role,
                None,
                f"Failed: {task.description} — {exc}",
                message_type="error",
                task_id=task.id,
            )

        return task.to_dict()

    # ------------------------------------------------------------------
    # Individual agent role handlers (mock when no LLM)
    # ------------------------------------------------------------------

    async def _agent_planner(self, task: AgentTask) -> Dict[str, Any]:
        """Planner agent handler — produces architecture/design documents."""
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                prompt = (
                    "You are a planning agent. Produce a concise technical "
                    "design for the following task:\n\n"
                    f"{task.description}\n\n"
                    "Include: architecture overview, key components, data models."
                )
                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                task.artifacts = ["docs/architecture.md"]
                return {"design": response, "artifacts": task.artifacts}
            except Exception as exc:
                logger.warning("LLM planner agent failed, using mock: %s", exc)

        # Mock
        await asyncio.sleep(0.1)  # simulate work
        task.artifacts = ["docs/architecture.md"]
        return {
            "design": f"Architecture design for: {task.description}",
            "components": ["core", "api", "database", "frontend"],
            "artifacts": task.artifacts,
        }

    async def _agent_coder(self, task: AgentTask) -> Dict[str, Any]:
        """Coder agent handler — produces source code files."""
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                # Gather context from completed dependencies
                dep_context = self._collect_dependency_results(task)
                prompt = (
                    "You are a coding agent. Implement the following task:\n\n"
                    f"{task.description}\n\n"
                )
                if dep_context:
                    prompt += f"Context from previous tasks:\n{dep_context}\n\n"
                prompt += "Write clean, production-ready code."

                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                task.artifacts = ["src/module.py"]
                return {"code": response, "artifacts": task.artifacts}
            except Exception as exc:
                logger.warning("LLM coder agent failed, using mock: %s", exc)

        # Mock
        await asyncio.sleep(0.15)
        task.artifacts = ["src/module.py", "src/module_test.py"]
        return {
            "code": f"# Implementation for: {task.description}\npass\n",
            "files_created": task.artifacts,
            "artifacts": task.artifacts,
        }

    async def _agent_tester(self, task: AgentTask) -> Dict[str, Any]:
        """Tester agent handler — writes and executes tests."""
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                dep_context = self._collect_dependency_results(task)
                prompt = (
                    "You are a testing agent. Write comprehensive tests for:\n\n"
                    f"{task.description}\n\n"
                )
                if dep_context:
                    prompt += f"Code to test:\n{dep_context}\n\n"
                prompt += "Write unit and integration tests."

                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                task.artifacts = ["tests/test_module.py"]
                return {"tests": response, "artifacts": task.artifacts}
            except Exception as exc:
                logger.warning("LLM tester agent failed, using mock: %s", exc)

        # Mock
        await asyncio.sleep(0.12)
        task.artifacts = ["tests/test_module.py"]
        return {
            "tests_written": 5,
            "passed": 4,
            "failed": 1,
            "failures": ["test_edge_case_3: AssertionError on line 42"],
            "artifacts": task.artifacts,
        }

    async def _agent_reviewer(self, task: AgentTask) -> Dict[str, Any]:
        """Reviewer agent handler — performs code review."""
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                dep_context = self._collect_dependency_results(task)
                prompt = (
                    "You are a code reviewer. Review the following code for "
                    "quality, readability, and best practices:\n\n"
                    f"{task.description}\n\n"
                )
                if dep_context:
                    prompt += f"Code:\n{dep_context}\n\n"
                prompt += (
                    "Provide: overall score (1-10), issues found, "
                    "and improvement suggestions."
                )

                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                task.artifacts = ["docs/review.md"]
                return {"review": response, "artifacts": task.artifacts}
            except Exception as exc:
                logger.warning("LLM reviewer agent failed, using mock: %s", exc)

        # Mock
        await asyncio.sleep(0.1)
        task.artifacts = ["docs/review.md"]
        return {
            "score": 7,
            "issues": [
                "Missing docstrings on 3 functions",
                "Consider using type hints consistently",
            ],
            "suggestions": [
                "Add comprehensive docstrings",
                "Use dataclasses for configuration objects",
            ],
            "artifacts": task.artifacts,
        }

    async def _agent_security(self, task: AgentTask) -> Dict[str, Any]:
        """Security agent handler — performs security analysis."""
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                dep_context = self._collect_dependency_results(task)
                prompt = (
                    "You are a security analyst. Perform a security review of:\n\n"
                    f"{task.description}\n\n"
                )
                if dep_context:
                    prompt += f"Code to analyze:\n{dep_context}\n\n"
                prompt += (
                    "Check for: injection vulnerabilities, auth issues, "
                    "data exposure, insecure defaults."
                )

                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                task.artifacts = ["docs/security_report.md"]
                return {"scan": response, "artifacts": task.artifacts}
            except Exception as exc:
                logger.warning("LLM security agent failed, using mock: %s", exc)

        # Mock
        await asyncio.sleep(0.1)
        task.artifacts = ["docs/security_report.md"]
        return {
            "vulnerabilities_found": 0,
            "warnings": [
                "Consider adding rate limiting to API endpoints",
                "Ensure all user inputs are validated server-side",
            ],
            "severity": "low",
            "artifacts": task.artifacts,
        }

    async def _agent_devops(self, task: AgentTask) -> Dict[str, Any]:
        """DevOps agent handler — sets up deployment and CI/CD."""
        if self.llm_provider is not None:
            try:
                from core.llm_service import Message

                dep_context = self._collect_dependency_results(task)
                prompt = (
                    "You are a DevOps engineer. Set up deployment for:\n\n"
                    f"{task.description}\n\n"
                )
                if dep_context:
                    prompt += f"Context:\n{dep_context}\n\n"
                prompt += (
                    "Provide: Dockerfile, CI/CD pipeline config, "
                    "and deployment instructions."
                )

                messages = [Message(role="user", content=prompt)]
                response = await self.llm_provider.complete(messages)
                task.artifacts = ["Dockerfile", ".github/workflows/ci.yml"]
                return {"devops": response, "artifacts": task.artifacts}
            except Exception as exc:
                logger.warning("LLM devops agent failed, using mock: %s", exc)

        # Mock
        await asyncio.sleep(0.1)
        task.artifacts = ["Dockerfile", ".github/workflows/ci.yml", "docker-compose.yml"]
        return {
            "dockerfile": "FROM python:3.12-slim\nCOPY . /app\nWORKDIR /app\n",
            "ci_pipeline": "CI/CD pipeline configured with lint, test, and deploy stages",
            "artifacts": task.artifacts,
        }

    # ------------------------------------------------------------------
    # Tester pipeline
    # ------------------------------------------------------------------

    async def _run_tests(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the testing phase on the execution results.

        Collects all completed coder tasks and delegates to the tester
        agent for verification.

        Parameters
        ----------
        results:
            The execution results from :meth:`_execute_tasks`.

        Returns
        -------
        dict
            ``total``, ``passed``, ``failed`` counts, ``failures`` list,
            and ``coverage`` estimate.
        """
        coder_tasks = [
            t for t in self.tasks.values()
            if t.role == AgentRole.CODER and t.status == "completed"
        ]

        if not coder_tasks:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "failures": [],
                "coverage": "0%",
                "note": "No coder tasks completed — nothing to test",
            }

        all_passed = 0
        all_failed = 0
        all_failures: List[str] = []

        for coder_task in coder_tasks:
            test_task = self.create_task(
                AgentRole.TESTER,
                f"Test implementation of: {coder_task.description}",
                dependencies=[coder_task.id],
            )
            test_result = await self._execute_single_task(test_task)
            result_data = test_result.get("result", {})
            all_passed += result_data.get("passed", 0)
            all_failed += result_data.get("failed", 0)
            all_failures.extend(result_data.get("failures", []))

        coverage = (
            f"{round(all_passed / max(all_passed + all_failed, 1) * 100)}%"
        )

        return {
            "total": all_passed + all_failed,
            "passed": all_passed,
            "failed": all_failed,
            "failures": all_failures,
            "coverage": coverage,
        }

    # ------------------------------------------------------------------
    # Reviewer pipeline
    # ------------------------------------------------------------------

    async def _run_review(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the code review phase.

        Parameters
        ----------
        results:
            The execution results from :meth:`_execute_tasks`.

        Returns
        -------
        dict
            ``overall_score``, ``issues``, ``suggestions``, and per-task
            reviews.
        """
        reviewable_tasks = [
            t for t in self.tasks.values()
            if t.role in (AgentRole.CODER, AgentRole.DEVOPS)
            and t.status == "completed"
        ]

        if not reviewable_tasks:
            return {
                "overall_score": 0,
                "issues": [],
                "suggestions": [],
                "reviews": [],
                "note": "No code tasks to review",
            }

        reviews: List[Dict[str, Any]] = []
        total_score = 0

        for target_task in reviewable_tasks:
            review_task = self.create_task(
                AgentRole.REVIEWER,
                f"Review code for: {target_task.description}",
                dependencies=[target_task.id],
            )
            review_result = await self._execute_single_task(review_task)
            result_data = review_result.get("result", {})
            score = result_data.get("score", 0)
            total_score += score
            reviews.append({
                "target_task_id": target_task.id,
                "score": score,
                "issues": result_data.get("issues", []),
                "suggestions": result_data.get("suggestions", []),
            })

        all_issues: List[str] = []
        all_suggestions: List[str] = []
        for r in reviews:
            all_issues.extend(r.get("issues", []))
            all_suggestions.extend(r.get("suggestions", []))

        overall_score = (
            round(total_score / len(reviews), 1) if reviews else 0
        )

        return {
            "overall_score": overall_score,
            "issues": all_issues,
            "suggestions": all_suggestions,
            "reviews": reviews,
        }

    # ------------------------------------------------------------------
    # Security scan pipeline
    # ------------------------------------------------------------------

    async def _run_security_scan(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a final security scan on all completed code tasks.

        Parameters
        ----------
        results:
            The execution results from :meth:`_execute_tasks`.

        Returns
        -------
        dict
            ``total_vulnerabilities``, ``severity``, ``vulnerabilities``,
            and ``warnings``.
        """
        code_tasks = [
            t for t in self.tasks.values()
            if t.role in (AgentRole.CODER, AgentRole.DEVOPS)
            and t.status == "completed"
        ]

        if not code_tasks:
            return {
                "total_vulnerabilities": 0,
                "severity": "none",
                "vulnerabilities": [],
                "warnings": [],
                "note": "No code tasks to scan",
            }

        scan_task = self.create_task(
            AgentRole.SECURITY,
            "Final security scan on all completed code",
            dependencies=[t.id for t in code_tasks],
        )
        scan_result = await self._execute_single_task(scan_task)
        result_data = scan_result.get("result", {})

        return {
            "total_vulnerabilities": result_data.get("vulnerabilities_found", 0),
            "severity": result_data.get("severity", "unknown"),
            "vulnerabilities": [],
            "warnings": result_data.get("warnings", []),
            "scanned_tasks": [t.id for t in code_tasks],
            "artifacts": result_data.get("artifacts", []),
        }

    # ------------------------------------------------------------------
    # Dependency helpers
    # ------------------------------------------------------------------

    def _dependencies_met(self, task: AgentTask) -> bool:
        """
        Check whether all dependencies of a task are completed.

        Parameters
        ----------
        task:
            The task to check.

        Returns
        -------
        bool
            *True* if every dependency has status ``"completed"``.
        """
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if dep_task is None:
                logger.warning(
                    "Task %s has unknown dependency %s", task.id, dep_id
                )
                return False
            if dep_task.status != "completed":
                return False
        return True

    def _collect_dependency_results(self, task: AgentTask) -> str:
        """
        Collect and format the results of a task's completed dependencies.

        This provides context to agent role handlers so they can build on
        prior work.

        Parameters
        ----------
        task:
            The task whose dependencies should be collected.

        Returns
        -------
        str
            Concatenated results from dependency tasks.
        """
        parts: List[str] = []
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if dep_task and dep_task.status == "completed" and dep_task.result:
                parts.append(
                    f"[{dep_task.role.value} — {dep_id}]: "
                    f"{json.dumps(dep_task.result, default=str)[:500]}"
                )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Inter-agent messaging
    # ------------------------------------------------------------------

    def _send_message(
        self,
        from_role: AgentRole,
        to_role: Optional[AgentRole],
        content: str,
        message_type: str = "info",
        task_id: Optional[str] = None,
    ) -> None:
        """
        Record a message between agents.

        Parameters
        ----------
        from_role:
            The sending agent's role.
        to_role:
            The receiving agent's role, or *None* for broadcast.
        content:
            Message body.
        message_type:
            One of ``"info"``, ``"request"``, ``"result"``, ``"warning"``,
            ``"error"``.
        task_id:
            Optional associated task ID.
        """
        msg = AgentMessage(
            from_role=from_role,
            to_role=to_role,
            content=content,
            message_type=message_type,
            task_id=task_id,
        )
        self.messages.append(msg)
        direction = (
            f"{from_role.value} → {to_role.value}"
            if to_role
            else f"{from_role.value} → broadcast"
        )
        logger.debug("Message [%s]: %s", direction, content[:100])

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(
        self, source: str, event: str, data: Dict[str, Any]
    ) -> None:
        """
        Append a structured entry to the execution log.

        Parameters
        ----------
        source:
            Origin of the event (e.g. ``"planner"``, ``"executor"``).
        event:
            Event name (e.g. ``"started"``, ``"completed"``, ``"failed"``).
        data:
            Arbitrary JSON-serializable payload.
        """
        entry = {
            "timestamp": time.time(),
            "source": source,
            "event": event,
            "data": data,
        }
        self.execution_log.append(entry)
        logger.debug("[%s] %s: %s", source, event, json.dumps(data, default=str)[:200])

    # ------------------------------------------------------------------
    # Public status / introspection
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Return a snapshot of the orchestrator's current state.

        Returns
        -------
        dict
            Task counts by status, role distribution, message count,
            and elapsed time since first task started.
        """
        status_counts: Dict[str, int] = {}
        role_counts: Dict[str, int] = {}

        for task in self.tasks.values():
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
            role_counts[task.role.value] = role_counts.get(task.role.value, 0) + 1

        first_start = None
        for task in self.tasks.values():
            if task.started_at is not None:
                if first_start is None or task.started_at < first_start:
                    first_start = task.started_at

        elapsed: Optional[float] = None
        if first_start is not None:
            elapsed = round(time.time() - first_start, 3)

        return {
            "total_tasks": len(self.tasks),
            "by_status": status_counts,
            "by_role": role_counts,
            "message_count": len(self.messages),
            "log_entries": len(self.execution_log),
            "elapsed_s": elapsed,
        }

    def get_log(self) -> List[Dict[str, Any]]:
        """
        Return the complete execution log.

        Returns
        -------
        list[dict]
            All log entries in chronological order.
        """
        return list(self.execution_log)

    def get_messages(
        self,
        role: Optional[AgentRole] = None,
        message_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return messages, optionally filtered by role or type.

        Parameters
        ----------
        role:
            If set, return only messages where ``from_role`` or
            ``to_role`` matches.
        message_type:
            If set, return only messages of this type.

        Returns
        -------
        list[dict]
            Filtered message dictionaries.
        """
        filtered = self.messages
        if role is not None:
            filtered = [
                m for m in filtered
                if m.from_role == role or m.to_role == role
            ]
        if message_type is not None:
            filtered = [
                m for m in filtered if m.message_type == message_type
            ]
        return [m.to_dict() for m in filtered]

    def reset(self) -> None:
        """
        Reset the orchestrator to a clean state.

        Clears all tasks, messages, and log entries.  Useful for
        running multiple orchestrations within the same process.
        """
        self.tasks.clear()
        self.messages.clear()
        self.execution_log.clear()
        self._task_counter = 0
        logger.info("Orchestrator reset to clean state")
