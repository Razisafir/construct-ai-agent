"""
Agent Orchestrator -- Manage multiple specialized agents working together.

Communication protocol:
- Structured messages (not raw text)
- Types: request, response, clarification, delegation, completion, conflict
- Shared context: all agents read from same memory + project state
- Conflict resolution: orchestrator mediates disagreements

Teams are ephemeral -- created per goal and disbanded on completion.
The message bus enables loose coupling between agents.

Concurrency:
- Semaphore-based LLM concurrency (max 30 concurrent calls)
- Priority-based task scheduling (user-facing > background > maintenance)
- Parallel agent execution with asyncio.gather
- Shared HTTP connection pool for tool calls
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Priority levels for task scheduling
# ---------------------------------------------------------------------------


class TaskPriority(Enum):
    """Priority levels for orchestrated tasks."""

    USER_FACING = 0    # Immediate user requests -- highest priority
    BACKGROUND = 1     # Autonomous mode tasks
    MAINTENANCE = 2    # Cleanup, learning, optimization -- lowest priority


@dataclass(order=True)
class PrioritizedTask:
    """
    A task wrapper that enables priority-queue ordering.

    Lower *priority* values are processed first.  When two tasks share the
    same priority the older *created_at* timestamp wins (FIFO within tier).
    """

    priority: int
    created_at: float = field(compare=True)
    task: Callable = field(compare=False)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8], compare=False)
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        """Ensure created_at is set if not provided."""
        if self.created_at is None:
            self.created_at = time.monotonic()


# ---------------------------------------------------------------------------
# Message protocol
# ---------------------------------------------------------------------------


class MessageType(Enum):
    """Structured message types for agent communication."""

    REQUEST = "request"
    RESPONSE = "response"
    CLARIFICATION = "clarification"
    DELEGATION = "delegation"
    COMPLETION = "completion"
    CONFLICT = "conflict"
    BROADCAST = "broadcast"


@dataclass
class AgentMessage:
    """A structured message exchanged between agents.

    Attributes:
        msg_type: The kind of message (request, response, etc.)
        from_agent: Sender agent identifier
        to_agent: Recipient agent identifier; None means broadcast
        content: Human-readable message body
        timestamp: Unix timestamp when the message was created
        context: Arbitrary key-value context carried with the message
        msg_id: Unique message identifier for tracking
    """

    msg_type: MessageType
    from_agent: str
    to_agent: Optional[str]
    content: str
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to a plain dictionary."""
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "timestamp": self.timestamp,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Deserialize a message from a dictionary."""
        return cls(
            msg_type=MessageType(data.get("msg_type", "request")),
            from_agent=data["from_agent"],
            to_agent=data.get("to_agent"),
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            context=data.get("context", {}),
            msg_id=data.get("msg_id", str(uuid.uuid4())[:8]),
        )


# ---------------------------------------------------------------------------
# Role and team definitions
# ---------------------------------------------------------------------------


@dataclass
class AgentRole:
    """Definition of a specialized agent role.

    Attributes:
        id: Unique role identifier (e.g. "code_engineer")
        name: Human-readable role name
        description: What this role is responsible for
        system_prompt: LLM system prompt for this role
        tools: List of tool names this role can invoke
        triggers: Event keywords that should activate this role
        personality: Short personality description for prompt engineering
    """

    id: str
    name: str
    description: str
    system_prompt: str
    tools: List[str]
    triggers: List[str]
    personality: str

    def to_system_message(self) -> str:
        """Build the full system message for this role."""
        return (
            f"{self.system_prompt}\n\n"
            f"Personality: {self.personality}\n"
            f"Available tools: {', '.join(self.tools)}\n"
            f"You respond using structured messages with type, content, and optional context."
        )


@dataclass
class AgentTeam:
    """A team of agents collaborating toward a shared goal.

    Attributes:
        id: Unique team identifier
        goal: High-level goal description
        agents: List of agent roles in this team
        messages: Shared message bus (all team messages)
        status: Current lifecycle state
        created_at: Team creation timestamp
        completed_at: Completion timestamp (None until finished)
        results: Accumulated outputs from team agents
    """

    id: str
    goal: str
    agents: List[AgentRole] = field(default_factory=list)
    messages: List[AgentMessage] = field(default_factory=list)
    status: str = "forming"  # forming | active | paused | completed | failed
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    results: Dict[str, Any] = field(default_factory=dict)

    def agent_ids(self) -> List[str]:
        """Return IDs of all agents in the team."""
        return [a.id for a in self.agents]

    def last_message(self) -> Optional[AgentMessage]:
        """Return the most recent message on the bus."""
        if not self.messages:
            return None
        return self.messages[-1]

    def messages_for_agent(self, agent_id: str) -> List[AgentMessage]:
        """Return messages addressed to a specific agent or broadcast."""
        return [
            m
            for m in self.messages
            if m.to_agent == agent_id or m.to_agent is None
        ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AgentOrchestrator:
    """
    Manage multiple specialized agents working toward a common goal.

    The orchestrator:
    - Creates ephemeral teams for each goal
    - Routes messages between agents via a shared message bus
    - Mediates conflicts using the LLM service
    - Merges individual agent outputs into a final result
    - Handles team lifecycle from formation to disbandment
    - Enforces concurrency limits via semaphore (max 30 parallel LLM calls)
    - Schedules tasks by priority (user-facing > background > maintenance)
    """

    # Concurrency limits
    DEFAULT_MAX_CONCURRENT_LLM: int = 30
    HTTP_CONNECTOR_LIMIT: int = 50

    def __init__(
        self,
        llm_service: Any,
        tool_registry: Any,
        memory_client: Optional[Any] = None,
        max_concurrent_llm: int = DEFAULT_MAX_CONCURRENT_LLM,
    ):
        self.llm = llm_service
        self.tools = tool_registry
        self.memory = memory_client
        self.teams: Dict[str, AgentTeam] = {}
        self._message_handlers: List[Callable[[AgentMessage], None]] = []
        self._role_cache: Dict[str, AgentRole] = {}

        # Concurrency control: semaphore caps parallel LLM calls
        self._llm_semaphore = asyncio.Semaphore(max_concurrent_llm)

        # Priority-based task queue
        self._priority_queue: asyncio.PriorityQueue[PrioritizedTask] = asyncio.PriorityQueue()
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._queue_running = False

        # Shared HTTP session with connection pooling
        self._http_session: Optional[aiohttp.ClientSession] = None

        logger.info(
            "AgentOrchestrator initialised (max_concurrent_llm=%d)",
            max_concurrent_llm,
        )

    # -- HTTP session (connection pooling) ----------------------------------

    @property
    def _http(self) -> aiohttp.ClientSession:
        """Lazy-initialise the shared aiohttp session with a connection pool."""
        if self._http_session is None or self._http_session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.HTTP_CONNECTOR_LIMIT,
                limit_per_host=20,
                ttl_dns_cache=300,
                use_dns_cache=True,
            )
            timeout = aiohttp.ClientTimeout(total=120)
            self._http_session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
            )
            logger.debug(
                "Orchestrator HTTP session created: limit=%d", self.HTTP_CONNECTOR_LIMIT
            )
        return self._http_session

    async def close(self) -> None:
        """Close the shared HTTP session and stop the queue processor."""
        self._queue_running = False
        if self._queue_processor_task and not self._queue_processor_task.done():
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None
        logger.info("AgentOrchestrator closed")

    # -- Priority queue management ------------------------------------------

    async def enqueue_task(
        self,
        task: Callable,
        priority: TaskPriority = TaskPriority.BACKGROUND,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a task to the priority queue.

        Parameters
        ----------
        task:
            Callable to execute (may be sync or async).
        priority:
            Task priority tier.
        metadata:
            Optional dict with extra context for the task.

        Returns
        -------
        str
            The generated task ID.
        """
        pt = PrioritizedTask(
            priority=priority.value,
            created_at=time.monotonic(),
            task=task,
            metadata=metadata or {},
        )
        await self._priority_queue.put(pt)
        logger.debug(
            "Enqueued task %s (priority=%s)",
            pt.task_id,
            priority.name,
        )
        return pt.task_id

    async def start_queue_processor(self) -> None:
        """Start the background task that drains the priority queue."""
        if self._queue_running:
            return
        self._queue_running = True
        self._queue_processor_task = asyncio.create_task(self._process_queue())
        logger.info("Priority queue processor started")

    async def _process_queue(self) -> None:
        """Background loop: consume tasks from the priority queue."""
        while self._queue_running:
            try:
                pt: PrioritizedTask = await asyncio.wait_for(
                    self._priority_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            logger.debug(
                "Processing task %s (priority=%d)",
                pt.task_id,
                pt.priority,
            )
            try:
                if asyncio.iscoroutinefunction(pt.task):
                    await pt.task()
                else:
                    pt.task()
            except Exception:
                logger.exception("Task %s failed", pt.task_id)

    # -- Message bus --------------------------------------------------------

    def register_message_handler(
        self, handler: Callable[[AgentMessage], None]
    ) -> None:
        """Register a callback invoked for every message sent."""
        self._message_handlers.append(handler)
        logger.debug("Registered message handler %s", handler.__name__)

    def _notify_handlers(self, msg: AgentMessage) -> None:
        """Invoke all registered message handlers."""
        for handler in self._message_handlers:
            try:
                handler(msg)
            except Exception:
                logger.exception("Message handler %s failed", handler)

    # -- Team lifecycle -----------------------------------------------------

    def create_team(
        self,
        goal: str,
        required_roles: Optional[List[str]] = None,
    ) -> AgentTeam:
        """Create a team of specialized agents for a goal.

        Args:
            goal: High-level description of what the team should accomplish
            required_roles: List of role IDs to include; defaults to a standard
                set of code engineer + test engineer + security auditor

        Returns:
            The newly created AgentTeam instance
        """
        team_id = f"team_{uuid.uuid4().hex[:8]}"
        team = AgentTeam(id=team_id, goal=goal)

        if required_roles is None:
            required_roles = ["code_engineer", "test_engineer", "security_auditor"]

        for role_name in required_roles:
            try:
                role = self._load_role(role_name)
                team.agents.append(role)
                logger.info("Added role '%s' to team %s", role_name, team_id)
            except FileNotFoundError:
                logger.warning("Role '%s' not found; skipping", role_name)

        if not team.agents:
            raise ValueError(
                f"No valid roles could be loaded for team {team_id}. "
                f"Requested: {required_roles}"
            )

        team.status = "active"
        self.teams[team_id] = team

        # Announce team formation
        self.broadcast(
            team_id=team_id,
            from_agent="orchestrator",
            content=f"Team formed for goal: {goal}. Members: {', '.join(team.agent_ids())}",
            context={"event": "team_formed", "agent_ids": team.agent_ids()},
        )
        return team

    def assign_task(
        self,
        team_id: str,
        agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Assign a task to a specific agent in the team.

        Args:
            team_id: Target team identifier
            agent_id: Target agent role ID
            task: Task description
            context: Optional additional context

        Returns:
            The delegation message that was sent
        """
        team = self._get_team(team_id)
        if agent_id not in team.agent_ids():
            raise ValueError(
                f"Agent '{agent_id}' not in team {team_id}. "
                f"Available: {team.agent_ids()}"
            )

        msg = AgentMessage(
            msg_type=MessageType.DELEGATION,
            from_agent="orchestrator",
            to_agent=agent_id,
            content=task,
            context=context or {},
        )
        self.send_message(team_id, msg)
        return msg

    def broadcast(
        self,
        team_id: str,
        from_agent: str,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Broadcast a message to all agents in the team.

        Args:
            team_id: Target team identifier
            from_agent: Sender agent identifier
            content: Message body
            context: Optional additional context

        Returns:
            The broadcast message that was sent
        """
        msg = AgentMessage(
            msg_type=MessageType.BROADCAST,
            from_agent=from_agent,
            to_agent=None,  # broadcast
            content=content,
            context=context or {},
        )
        self.send_message(team_id, msg)
        return msg

    def send_message(self, team_id: str, msg: AgentMessage) -> None:
        """Send a message between agents via the team message bus.

        Args:
            team_id: Target team identifier
            msg: The message to append to the bus
        """
        team = self._get_team(team_id)
        team.messages.append(msg)
        self._notify_handlers(msg)
        logger.debug(
            "[%s] %s -> %s: %s (%s)",
            team_id,
            msg.from_agent,
            msg.to_agent or "*",
            msg.msg_type.value,
            msg.msg_id,
        )

    def get_team_status(self, team_id: str) -> Dict[str, Any]:
        """Get status of all agents in the team.

        Args:
            team_id: Target team identifier

        Returns:
            Dictionary with team metadata and per-agent stats
        """
        team = self._get_team(team_id)
        agent_stats: Dict[str, Any] = {}
        for aid in team.agent_ids():
            msgs = team.messages_for_agent(aid)
            agent_stats[aid] = {
                "message_count": len(msgs),
                "last_message": msgs[-1].to_dict() if msgs else None,
                "status": "active" if msgs else "idle",
            }

        return {
            "team_id": team.id,
            "goal": team.goal,
            "status": team.status,
            "agent_count": len(team.agents),
            "message_count": len(team.messages),
            "agents": agent_stats,
            "created_at": team.created_at,
            "elapsed": time.time() - team.created_at,
        }

    # -- Parallel execution -------------------------------------------------

    async def execute_parallel(
        self,
        team_id: str,
        tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks across agents in parallel with concurrency control.

        Each task dict must contain at least an ``agent_id`` key.  The
        semaphore ensures at most *max_concurrent_llm* LLM calls are
        in flight simultaneously.

        Parameters
        ----------
        team_id:
            Identifier of the team whose agents will run the tasks.
        tasks:
            List of task dictionaries.  Each dict must include:
            - ``agent_id``: str -- target agent role ID
            - ``task``: str -- task description
            - Optional extra keys are passed through to the context.

        Returns
        -------
        list[dict]
            Results in the same order as *tasks*.  Failed tasks are
            represented by ``{"error": "..."}`` dicts rather than
            raising exceptions.
        """
        team = self._get_team(team_id)
        valid_agents = set(team.agent_ids())

        async def _execute_single(task_def: Dict[str, Any]) -> Dict[str, Any]:
            """Execute one task under the LLM semaphore."""
            agent_id = task_def.get("agent_id", "")
            if agent_id not in valid_agents:
                return {
                    "error": f"Agent '{agent_id}' not in team {team_id}",
                    "agent_id": agent_id,
                }

            async with self._llm_semaphore:
                # Build delegation message
                msg = AgentMessage(
                    msg_type=MessageType.DELEGATION,
                    from_agent="orchestrator",
                    to_agent=agent_id,
                    content=task_def.get("task", ""),
                    context={k: v for k, v in task_def.items() if k not in ("agent_id", "task")},
                )
                self.send_message(team_id, msg)

                # Invoke LLM via the service
                try:
                    from core.llm_service import Message, assemble_messages
                    messages = assemble_messages(
                        user_prompt=task_def.get("task", ""),
                    )
                    # Use complete() for reliability (stream_complete has
                    # circuit-breaker compatibility issues in some configs)
                    response_text = await self.llm.complete(messages)

                    # Send completion message
                    completion_msg = AgentMessage(
                        msg_type=MessageType.COMPLETION,
                        from_agent=agent_id,
                        to_agent="orchestrator",
                        content=response_text,
                        context={"task_id": task_def.get("task_id", ""), "status": "done"},
                    )
                    self.send_message(team_id, completion_msg)

                    return {
                        "agent_id": agent_id,
                        "task": task_def.get("task", ""),
                        "result": response_text,
                        "status": "completed",
                    }
                except Exception as exc:
                    logger.exception("Parallel task failed for agent %s", agent_id)
                    return {
                        "agent_id": agent_id,
                        "task": task_def.get("task", ""),
                        "error": str(exc),
                        "status": "failed",
                    }

        # Launch all tasks concurrently, respecting the semaphore
        results = await asyncio.gather(
            *[_execute_single(t) for t in tasks],
            return_exceptions=True,
        )

        # Normalize exceptions into error dicts
        normalized: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, Exception):
                normalized.append({"error": str(r), "status": "failed"})
            else:
                normalized.append(r)
        return normalized

    async def execute_agent_task(
        self,
        team_id: str,
        agent_id: str,
        task: str,
        priority: TaskPriority = TaskPriority.BACKGROUND,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute a single agent task with priority and concurrency control.

        This is a convenience wrapper around the semaphore that also
        integrates with the priority queue for scheduling.

        Parameters
        ----------
        team_id:
            Target team identifier.
        agent_id:
            Target agent role ID.
        task:
            Task description.
        priority:
            Scheduling priority.
        context:
            Optional additional context.

        Returns
        -------
        str
            The agent's response text.
        """
        async def _run() -> str:
            async with self._llm_semaphore:
                from core.llm_service import Message, assemble_messages
                messages = assemble_messages(user_prompt=task)
                return await self.llm.complete(messages)

        if priority == TaskPriority.USER_FACING:
            # User-facing tasks run immediately with semaphore
            return await _run()

        # Background / maintenance tasks go through the priority queue
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _wrapped() -> None:
            try:
                result = await _run()
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)

        await self.enqueue_task(_wrapped, priority=priority, metadata=context)
        return await future

    # -- Conflict resolution ------------------------------------------------

    def resolve_conflict(
        self,
        team_id: str,
        agent_a: str,
        agent_b: str,
        issue: str,
    ) -> str:
        """Mediate a disagreement between two agents using LLM analysis.

        Args:
            team_id: Target team identifier
            agent_a: First agent's role ID
            agent_b: Second agent's role ID
            issue: Description of the disagreement

        Returns:
            The orchestrator's resolution recommendation
        """
        team = self._get_team(team_id)
        logger.info(
            "Resolving conflict in %s between %s and %s: %s",
            team_id,
            agent_a,
            agent_b,
            issue,
        )

        # Build context from recent messages
        recent_msgs = [
            m for m in team.messages[-20:]
            if m.from_agent in (agent_a, agent_b)
        ]
        context_lines = "\n".join(
            f"[{m.from_agent}] {m.content[:200]}"
            for m in recent_msgs
        )

        # Use LLM to analyze both positions and suggest resolution
        resolution_prompt = (
            f"You are a neutral mediator resolving a disagreement between two AI agents.\n\n"
            f"Team goal: {team.goal}\n"
            f"Issue: {issue}\n\n"
            f"Recent context:\n{context_lines}\n\n"
            f"Agent A ({agent_a}) and Agent B ({agent_b}) disagree.\n\n"
            f"Analyze both positions objectively. Consider:"
            f"1. Which position better serves the team goal?\n"
            f"2. Is there a compromise that incorporates both viewpoints?\n"
            f"3. What are the risks of each approach?\n\n"
            f"Provide a clear, actionable resolution."
        )

        try:
            resolution = self.llm.complete(resolution_prompt)
        except Exception as exc:
            logger.exception("LLM conflict resolution failed")
            resolution = (
                f"Unable to resolve automatically due to error: {exc}. "
                f"Fallback: defer to {agent_a}'s approach as primary, "
                f"with {agent_b}'s concerns documented as follow-up items."
            )

        # Log the conflict and resolution
        conflict_msg = AgentMessage(
            msg_type=MessageType.CONFLICT,
            from_agent="orchestrator",
            to_agent=None,
            content=f"Conflict between {agent_a} and {agent_b}: {issue}",
            context={
                "agent_a": agent_a,
                "agent_b": agent_b,
                "issue": issue,
                "resolution": resolution,
            },
        )
        self.send_message(team_id, conflict_msg)
        return resolution

    # -- Result merging -----------------------------------------------------

    def merge_results(self, team_id: str) -> Dict[str, Any]:
        """Merge outputs from all team agents into a final unified result.

        Args:
            team_id: Target team identifier

        Returns:
            Merged result dictionary
        """
        team = self._get_team(team_id)
        logger.info("Merging results for team %s", team_id)

        # Gather completion messages
        completions = [
            m for m in team.messages
            if m.msg_type == MessageType.COMPLETION
        ]

        per_agent: Dict[str, List[str]] = {}
        for c in completions:
            per_agent.setdefault(c.from_agent, []).append(c.content)

        # Build merged result
        merged = {
            "team_id": team_id,
            "goal": team.goal,
            "agent_count": len(team.agents),
            "completions": {aid: texts for aid, texts in per_agent.items()},
            "merged_summary": self._generate_summary(team, per_agent),
            "message_count": len(team.messages),
            "elapsed_seconds": time.time() - team.created_at,
        }

        team.results = merged
        team.status = "completed"
        team.completed_at = time.time()
        return merged

    def _generate_summary(
        self,
        team: AgentTeam,
        per_agent: Dict[str, List[str]],
    ) -> str:
        """Generate a natural-language summary of merged results."""
        lines = [f"Team '{team.id}' results for goal: {team.goal}"]
        for aid, texts in per_agent.items():
            lines.append(f"\n--- {aid} ---")
            for t in texts:
                lines.append(t[:500])
        return "\n".join(lines)

    # -- Cleanup -----------------------------------------------------------

    def disband_team(self, team_id: str) -> Dict[str, Any]:
        """Clean up a completed team.

        Persists final results to memory if available, then removes
        the team from active management.

        Args:
            team_id: Target team identifier

        Returns:
            Final team results (if any)
        """
        team = self._get_team(team_id)
        logger.info("Disbanding team %s", team_id)

        # Persist to long-term memory if available
        if self.memory is not None and team.results:
            try:
                self.memory.store(
                    key=f"team_result:{team_id}",
                    value=team.results,
                    tags=["team_result", team.status],
                )
            except Exception:
                logger.exception("Failed to persist team %s results", team_id)

        team.status = "completed" if team.status != "failed" else "failed"
        team.completed_at = team.completed_at or time.time()
        results = team.results

        del self.teams[team_id]
        logger.info("Team %s disbanded", team_id)
        return results

    # -- Internal helpers ---------------------------------------------------

    def _get_team(self, team_id: str) -> AgentTeam:
        """Retrieve a team by ID, raising if missing."""
        if team_id not in self.teams:
            raise KeyError(f"Team '{team_id}' not found. Active: {list(self.teams.keys())}")
        return self.teams[team_id]

    def _load_role(self, role_name: str) -> AgentRole:
        """Load a predefined agent role from the roles directory.

        Three strategies (in order):
        1. Cached role (fast path)
        2. Direct Python import of agents.roles.<name> (works in PyInstaller
           bundles where .py files are compiled into the archive)
        3. Dynamic import from roles/ directory on disk (dev mode)
        4. Fallback via ROLE_MAP from the roles package

        Args:
            role_name: Role identifier (matches filename without .py)

        Returns:
            The loaded AgentRole instance
        """
        # Return from cache if available
        if role_name in self._role_cache:
            return self._role_cache[role_name]

        # Strategy 1: Direct Python import (works in PyInstaller bundles)
        try:
            import importlib as _il
            module = _il.import_module(f".roles.{role_name}", package="agents")
            if hasattr(module, "ROLE"):
                role: AgentRole = module.ROLE  # type: ignore[no-redef]
                self._role_cache[role_name] = role
                logger.debug("Loaded role '%s' via direct import", role_name)
                return role
        except ImportError:
            pass  # Module not found, try next strategy
        except Exception as exc:
            logger.debug("Direct import failed for role '%s': %s", role_name, exc)

        # Strategy 2: Dynamic import from roles/ directory on disk (dev mode)
        roles_dir = os.path.join(os.path.dirname(__file__), "roles")
        role_file = os.path.join(roles_dir, f"{role_name}.py")

        if os.path.isfile(role_file):
            spec = importlib.util.spec_from_file_location(
                f"agents.roles.{role_name}", role_file
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                role: AgentRole = module.ROLE  # type: ignore[no-redef]
                self._role_cache[role_name] = role
                logger.debug("Loaded role '%s' from file: %s", role_name, role_file)
                return role

        # Strategy 3: Fallback via ROLE_MAP from the roles package
        try:
            from .roles import ROLE_MAP

            if role_name in ROLE_MAP:
                role: AgentRole = ROLE_MAP[role_name]  # type: ignore[no-redef]
                self._role_cache[role_name] = role
                logger.debug("Loaded role '%s' from ROLE_MAP", role_name)
                return role
        except Exception:
            logger.debug("ROLE_MAP fallback failed for role '%s'", role_name)

        # Strategy 4: Last resort — try uppercase attribute on package
        try:
            from . import roles as roles_pkg

            if hasattr(roles_pkg, role_name.upper()):
                role: AgentRole = getattr(roles_pkg, role_name.upper())  # type: ignore[no-redef]
                self._role_cache[role_name] = role
                logger.debug("Loaded role '%s' via package attribute", role_name)
                return role
        except Exception:
            logger.debug("Package attribute fallback failed for role '%s'", role_name)

        raise FileNotFoundError(
            f"Role '{role_name}' not found. Tried: direct import, "
            f"file load ({role_file}), ROLE_MAP, and package attributes"
        )

    def list_active_teams(self) -> List[str]:
        """Return IDs of all currently active teams."""
        return [
            tid
            for tid, team in self.teams.items()
            if team.status in ("forming", "active")
        ]

    def pause_team(self, team_id: str) -> None:
        """Pause an active team (stop processing but retain state)."""
        team = self._get_team(team_id)
        team.status = "paused"
        logger.info("Team %s paused", team_id)

    def resume_team(self, team_id: str) -> None:
        """Resume a paused team."""
        team = self._get_team(team_id)
        if team.status != "paused":
            raise ValueError(f"Team {team_id} is not paused (status={team.status})")
        team.status = "active"
        logger.info("Team %s resumed", team_id)

    # -- Orchestrator status ------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return orchestrator status including queue and concurrency info."""
        return {
            "active_teams": len(self.teams),
            "team_ids": list(self.teams.keys()),
            "queue_size": self._priority_queue.qsize(),
            "max_concurrent_llm": self._llm_semaphore._value,
            "llm_semaphore_locked": self._llm_semaphore.locked(),
            "http_session_active": self._http_session is not None and not self._http_session.closed,
        }
