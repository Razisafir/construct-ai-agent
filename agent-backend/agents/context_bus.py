"""Shared Context Bus — pub/sub system for multi-agent communication.

Topics: project_state, file_changes, errors, decisions, completions
Every agent subscribes to relevant topics.
Messages are structured JSON, not free text.

Example::

    bus = ContextBus()
    bus.subscribe(Topic.ERRORS, lambda msg: print(f"Error: {msg.payload}"))
    bus.publish(Topic.ERRORS, AgentMessage(
        id="msg-1", topic=Topic.ERRORS, source_agent="linter",
        payload={"file": "app.py", "line": 42, "message": "Syntax error"}
    ))
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Topic(str, Enum):
    """Enumeration of all valid pub/sub topics on the context bus."""

    PROJECT_STATE = "project_state"
    FILE_CHANGES = "file_changes"
    ERRORS = "errors"
    DECISIONS = "decisions"
    COMPLETIONS = "completions"
    AGENT_STATUS = "agent_status"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"


@dataclass
class AgentMessage:
    """A structured message exchanged between agents on the context bus.

    Attributes:
        id: Unique message identifier (UUID4).
        topic: The topic channel this message is published on.
        source_agent: Name of the agent that produced the message.
        payload: Arbitrary key-value data specific to the message type.
        timestamp: Unix epoch time when the message was created.
        priority: Priority level from 1 (urgent) to 10 (low).
    """

    id: str
    topic: Topic
    source_agent: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    priority: int = 5  # 1=urgent, 10=low

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the message to a JSON-friendly dictionary."""
        return {
            "id": self.id,
            "topic": self.topic.value,
            "source_agent": self.source_agent,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        """Deserialize a message from a dictionary.

        Args:
            data: Dictionary containing message fields.

        Returns:
            A new AgentMessage instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If the topic is invalid.
        """
        return cls(
            id=data["id"],
            topic=Topic(data["topic"]),
            source_agent=data["source_agent"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", time.time()),
            priority=data.get("priority", 5),
        )


@dataclass
class ProjectState:
    """Snapshot of the overall project state shared across all agents.

    Attributes:
        current_goal: The high-level goal currently being pursued.
        active_files: List of files currently being worked on.
        last_error: The most recent error message, if any.
        completion_percentage: Overall completion progress (0.0 to 100.0).
        active_agents: List of currently active agent identifiers.
        pending_tasks: Number of tasks yet to be started.
        completed_tasks: Number of tasks that have been completed.
    """

    current_goal: str
    active_files: List[str]
    last_error: Optional[str] = None
    completion_percentage: float = 0.0
    active_agents: List[str] = field(default_factory=list)
    pending_tasks: int = 0
    completed_tasks: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize project state to a dictionary."""
        return asdict(self)

    def copy(self) -> ProjectState:
        """Return a deep copy of the current state."""
        return ProjectState(
            current_goal=self.current_goal,
            active_files=list(self.active_files),
            last_error=self.last_error,
            completion_percentage=self.completion_percentage,
            active_agents=list(self.active_agents),
            pending_tasks=self.pending_tasks,
            completed_tasks=self.completed_tasks,
        )


class ContextBus:
    """Central pub/sub system for all agent communication.

    The ContextBus is the nervous system of the multi-agent architecture.
    It routes structured messages between agents via named topics,
    maintains a rolling history for audit and debugging, and tracks
    a shared :class:`ProjectState` that all agents can read and update.

    Thread-safety is provided by :class:`asyncio.Lock` so the bus can be
    used safely from multiple async agents concurrently.

    Attributes:
        _subscribers: Mapping from Topic to list of callback functions.
        _history: Rolling deque of recent messages (oldest evicted first).
        _state: Shared project state snapshot.
        _lock: Async lock for state mutation and subscription changes.
    """

    def __init__(self, history_limit: int = 1000) -> None:
        self._subscribers: Dict[
            Topic, List[Callable[[AgentMessage], None]]
        ] = defaultdict(list)
        self._history: deque[AgentMessage] = deque(maxlen=history_limit)
        self._state: ProjectState = ProjectState(
            current_goal="", active_files=[]
        )
        self._lock = asyncio.Lock()
        logger.info(
            "ContextBus initialized (history_limit=%d)", history_limit
        )

    def publish(self, topic: Topic, message: AgentMessage) -> None:
        """Publish a message to all subscribers of *topic*.

        Subscribers are invoked **synchronously** in the order they
        were registered.  Any exception raised by a subscriber is
        logged and suppressed so that one faulty handler does not
        break delivery to the rest.

        The message is also appended to the rolling history and, if
        the topic is :attr:`Topic.PROJECT_STATE`, the shared project
        state is updated automatically from the payload.

        Args:
            topic: The topic channel to publish on.
            message: The :class:`AgentMessage` to deliver.
        """
        if not isinstance(message, AgentMessage):
            raise TypeError(
                f"Expected AgentMessage, got {type(message).__name__}"
            )

        # Enforce topic consistency
        if message.topic != topic:
            logger.warning(
                "Message topic %s does not match publish topic %s; "
                "using publish topic",
                message.topic,
                topic,
            )
            message.topic = topic

        # Store in history
        self._history.append(message)

        # Auto-update project state when relevant
        if topic == Topic.PROJECT_STATE:
            self._apply_state_update(message.payload)

        # Deliver to subscribers
        handlers = list(self._subscribers.get(topic, []))
        if not handlers:
            logger.debug("No subscribers for topic %s", topic.value)

        for handler in handlers:
            try:
                handler(message)
            except Exception:
                logger.exception(
                    "Subscriber %s raised an error handling message %s",
                    getattr(handler, "__name__", repr(handler)),
                    message.id,
                )

        logger.debug(
            "Published message %s to topic %s (%d subscribers)",
            message.id,
            topic.value,
            len(handlers),
        )

    def subscribe(
        self, topic: Topic, handler: Callable[[AgentMessage], None]
    ) -> None:
        """Subscribe *handler* to receive messages on *topic*.

        Args:
            topic: The topic to listen on.
            handler: A callable that accepts a single :class:`AgentMessage`.

        Raises:
            TypeError: If *handler* is not callable.
        """
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler)}")
        self._subscribers[topic].append(handler)
        logger.debug(
            "Subscribed handler %s to topic %s",
            getattr(handler, "__name__", repr(handler)),
            topic.value,
        )

    def unsubscribe(
        self, topic: Topic, handler: Callable[[AgentMessage], None]
    ) -> None:
        """Unsubscribe *handler* from *topic*.

        If the handler is not currently subscribed, this is a no-op.

        Args:
            topic: The topic to unsubscribe from.
            handler: The previously registered callable.
        """
        handlers = self._subscribers.get(topic, [])
        try:
            handlers.remove(handler)
            logger.debug(
                "Unsubscribed handler %s from topic %s",
                getattr(handler, "__name__", repr(handler)),
                topic.value,
            )
        except ValueError:
            logger.warning(
                "Handler %s was not subscribed to topic %s",
                getattr(handler, "__name__", repr(handler)),
                topic.value,
            )

    def get_state(self) -> ProjectState:
        """Return the latest project state snapshot.

        Returns:
            A :class:`ProjectState` instance representing the current
            shared state.  Modifying the returned object does **not**
            affect the bus; use :meth:`update_state` for mutations.
        """
        return self._state.copy()

    def update_state(self, update: Dict[str, Any]) -> None:
        """Update the project state with new key-value pairs.

        Only keys that correspond to :class:`ProjectState` attributes
        are applied; unknown keys are logged at warning level and
        ignored.

        Args:
            update: Dictionary of state fields to overwrite.
        """
        self._apply_state_update(update)
        # Notify subscribers that state changed
        message = AgentMessage(
            id=f"state-{uuid.uuid4().hex[:8]}",
            topic=Topic.PROJECT_STATE,
            source_agent="context_bus",
            payload=self._state.to_dict(),
        )
        self._history.append(message)
        for handler in list(self._subscribers.get(Topic.PROJECT_STATE, [])):
            try:
                handler(message)
            except Exception:
                logger.exception("State subscriber raised an error")

    def _apply_state_update(self, update: Dict[str, Any]) -> None:
        """Internal helper to mutate :attr:`_state` from a dict."""
        valid_fields = {
            f.name for f in self._state.__dataclass_fields__.values()
        }
        for key, value in update.items():
            if key in valid_fields:
                setattr(self._state, key, value)
                logger.debug("ProjectState.%s updated", key)
            else:
                logger.warning(
                    "Ignoring unknown ProjectState field: %s", key
                )

    def get_history(
        self,
        topic: Optional[Topic] = None,
        limit: int = 100,
        min_priority: Optional[int] = None,
    ) -> List[AgentMessage]:
        """Return recent messages, optionally filtered.

        Messages are returned newest-first.

        Args:
            topic: If given, only messages on this topic are included.
            limit: Maximum number of messages to return.
            min_priority: If given, only messages with priority <= this
                value (i.e. equal or higher urgency) are included.

        Returns:
            A list of :class:`AgentMessage` objects matching the filters.
        """
        results: List[AgentMessage] = []
        # Iterate from newest (right side of deque) to oldest
        for msg in reversed(self._history):
            if topic is not None and msg.topic != topic:
                continue
            if min_priority is not None and msg.priority > min_priority:
                continue
            results.append(msg)
            if len(results) >= limit:
                break
        return results

    async def publish_async(
        self, topic: Topic, message: AgentMessage
    ) -> None:
        """Async publish that awaits all handlers concurrently.

        This is the async-safe variant of :meth:`publish`.  It acquires
        the internal lock, stores the message, then dispatches to all
        subscribers using ``await`` so that slow handlers do not block
        each other.

        Args:
            topic: The topic channel to publish on.
            message: The :class:`AgentMessage` to deliver.
        """
        async with self._lock:
            if not isinstance(message, AgentMessage):
                raise TypeError(
                    f"Expected AgentMessage, got {type(message).__name__}"
                )

            if message.topic != topic:
                message.topic = topic

            self._history.append(message)

            if topic == Topic.PROJECT_STATE:
                self._apply_state_update(message.payload)

            handlers = list(self._subscribers.get(topic, []))

        # Deliver outside the lock so we don't block other publishers
        if not handlers:
            logger.debug("No subscribers for topic %s", topic.value)
            return

        async def _invoke(
            h: Callable[[AgentMessage], None],
        ) -> None:
            try:
                result = h(message)
                if asyncio.isfuture(result) or asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(
                    "Async subscriber %s raised an error",
                    getattr(h, "__name__", repr(h)),
                )

        await asyncio.gather(
            *[_invoke(h) for h in handlers], return_exceptions=True
        )

        logger.debug(
            "Async-published message %s to topic %s (%d subscribers)",
            message.id,
            topic.value,
            len(handlers),
        )

    def clear_history(self) -> None:
        """Remove all messages from the history deque.

        Subscriptions and project state are left untouched.
        """
        self._history.clear()
        logger.info("Message history cleared")

    def clear_subscribers(self, topic: Optional[Topic] = None) -> None:
        """Remove all subscribers, optionally for a single topic.

        Args:
            topic: If given, only subscribers for this topic are removed.
                Otherwise **all** subscribers for **all** topics are removed.
        """
        if topic is not None:
            count = len(self._subscribers.get(topic, []))
            self._subscribers[topic].clear()
            logger.info(
                "Cleared %d subscribers for topic %s", count, topic.value
            )
        else:
            total = sum(len(h) for h in self._subscribers.values())
            self._subscribers.clear()
            logger.info("Cleared all %d subscribers", total)

    def subscriber_count(self, topic: Optional[Topic] = None) -> int:
        """Return the number of registered subscribers.

        Args:
            topic: If given, count only subscribers for this topic.
                Otherwise count subscribers across all topics.

        Returns:
            Integer subscriber count.
        """
        if topic is not None:
            return len(self._subscribers.get(topic, []))
        return sum(len(h) for h in self._subscribers.values())


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

async def _async_demo() -> None:
    """Run the async demonstration of ContextBus."""
    bus = ContextBus(history_limit=100)

    received: List[str] = []

    def on_file_change(msg: AgentMessage) -> None:
        received.append(f"[FILE] {msg.payload.get('file', '?')}")

    def on_error(msg: AgentMessage) -> None:
        received.append(f"[ERROR] {msg.payload.get('message', '?')}")

    bus.subscribe(Topic.FILE_CHANGES, on_file_change)
    bus.subscribe(Topic.ERRORS, on_error)

    # Publish some messages
    bus.publish(
        Topic.FILE_CHANGES,
        AgentMessage(
            id="m1",
            topic=Topic.FILE_CHANGES,
            source_agent="coder",
            payload={"file": "app.py", "action": "modified"},
        ),
    )
    bus.publish(
        Topic.ERRORS,
        AgentMessage(
            id="m2",
            topic=Topic.ERRORS,
            source_agent="linter",
            payload={"file": "app.py", "line": 10, "message": "Unused import"},
            priority=3,
        ),
    )

    # Update state
    bus.update_state(
        {
            "current_goal": "Build REST API",
            "active_files": ["app.py", "models.py"],
            "completion_percentage": 35.0,
        }
    )

    state = bus.get_state()
    print(f"Current goal: {state.current_goal}")
    print(f"Active files: {state.active_files}")
    print(f"Completion: {state.completion_percentage}%")
    print(f"Messages received: {received}")

    history = bus.get_history(topic=Topic.FILE_CHANGES)
    print(f"File change history count: {len(history)}")

    # Test async publish
    async def async_handler(msg: AgentMessage) -> None:
        await asyncio.sleep(0.01)
        received.append(f"[ASYNC] {msg.id}")

    bus.subscribe(Topic.COMPLETIONS, async_handler)
    await bus.publish_async(
        Topic.COMPLETIONS,
        AgentMessage(
            id="m3",
            topic=Topic.COMPLETIONS,
            source_agent="tester",
            payload={"test": "all_passed"},
        ),
    )
    print(f"Messages after async: {received}")

    # Cleanup
    bus.unsubscribe(Topic.FILE_CHANGES, on_file_change)
    print(f"Subscribers after unsubscribe: {bus.subscriber_count()}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print("=" * 60)
    print("ContextBus Demo")
    print("=" * 60)
    asyncio.run(_async_demo())
