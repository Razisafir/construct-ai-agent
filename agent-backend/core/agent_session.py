"""
Agent session management — in-memory session store.

Provides CRUD operations for agent sessions and output log retrieval
with delta-based polling support (since-last-check semantics).

Usage::

    from core.agent_session import SessionStore

    store = SessionStore()
    session = store.create_session("Add auth to the API", "/projects/myapp")
    events = store.get_session_output(session.id)  # since last call
"""

import time
import logging
from typing import Dict, List, Optional

from core.executor import AgentSession, AgentStatus

logger = logging.getLogger(__name__)


class SessionStore:
    """
    In-memory store for agent sessions with output log tracking.

    Each session's output log can be polled incrementally using
    ``get_session_output``, which tracks the last-read position per
    session.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, AgentSession] = {}
        # Tracks the last output index returned per session ID
        self._output_positions: Dict[str, int] = {}

    # -- CRUD operations ----------------------------------------------------

    def create_session(self, goal: str, project_path: str = ".") -> AgentSession:
        """
        Create a new agent session.

        Parameters
        ----------
        goal:
            The user's goal description.
        project_path:
            Absolute or relative path to the project directory.

        Returns
        -------
        AgentSession
            The newly created session.
        """
        session = AgentSession(
            id=self._generate_id(),
            goal=goal,
            project_path=project_path,
        )
        self._sessions[session.id] = session
        self._output_positions[session.id] = 0
        logger.info("Created session %s: %s", session.id, goal)
        return session

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        Get a session by ID.

        Parameters
        ----------
        session_id:
            The session's unique identifier.

        Returns
        -------
        AgentSession or None
            The session if found.
        """
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[AgentSession]:
        """
        List all sessions, most recently updated first.

        Returns
        -------
        list[AgentSession]
            All stored sessions ordered by ``updated_at`` descending.
        """
        return sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its tracked output position.

        Parameters
        ----------
        session_id:
            The session's unique identifier.

        Returns
        -------
        bool
            *True* if the session existed and was deleted.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._output_positions.pop(session_id, None)
            logger.info("Deleted session %s", session_id)
            return True
        return False

    # -- Output log (delta / since-last-check) ------------------------------

    def get_session_output(self, session_id: str) -> List[dict]:
        """
        Get new output events since the last call for this session.

        Uses a tracked cursor so each call returns only events that
        have not been seen before.  Pass ``reset=True`` to the
        underlying mechanism if you want all events.

        Parameters
        ----------
        session_id:
            The session's unique identifier.

        Returns
        -------
        list[dict]
            New output events (may be empty if nothing new).
        """
        session = self._sessions.get(session_id)
        if not session:
            return []

        last_pos = self._output_positions.get(session_id, 0)
        current_len = len(session.output_log)

        if last_pos >= current_len:
            return []

        new_events = session.output_log[last_pos:current_len]
        self._output_positions[session_id] = current_len

        return [
            {
                "session_id": session_id,
                "type": e.get("type", "unknown"),
                "content": e.get("content", ""),
                "timestamp": e.get("timestamp", 0),
            }
            for e in new_events
        ]

    def get_all_output(self, session_id: str) -> List[dict]:
        """
        Get the complete output log for a session.

        Parameters
        ----------
        session_id:
            The session's unique identifier.

        Returns
        -------
        list[dict]
            All output events for the session.
        """
        session = self._sessions.get(session_id)
        if not session:
            return []

        return [
            {
                "session_id": session_id,
                "type": e.get("type", "unknown"),
                "content": e.get("content", ""),
                "timestamp": e.get("timestamp", 0),
            }
            for e in session.output_log
        ]

    def reset_output_cursor(self, session_id: str) -> bool:
        """
        Reset the output cursor to the beginning for a session.

        The next ``get_session_output`` call will return all events.

        Parameters
        ----------
        session_id:
            The session's unique identifier.

        Returns
        -------
        bool
            *True* if the session existed.
        """
        if session_id in self._sessions:
            self._output_positions[session_id] = 0
            return True
        return False

    # -- Stats --------------------------------------------------------------

    def get_stats(self) -> dict:
        """
        Return aggregate statistics about all sessions.

        Returns
        -------
        dict
            ``total_sessions``, counts by status, average tasks per session.
        """
        total = len(self._sessions)
        if total == 0:
            return {"total_sessions": 0}

        status_counts: Dict[str, int] = {}
        total_tasks = 0
        for s in self._sessions.values():
            sv = s.status.value
            status_counts[sv] = status_counts.get(sv, 0) + 1
            total_tasks += len(s.tasks)

        return {
            "total_sessions": total,
            "by_status": status_counts,
            "avg_tasks": round(total_tasks / total, 1),
            "total_output_events": sum(
                len(s.output_log) for s in self._sessions.values()
            ),
        }

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    def _generate_id() -> str:
        """Generate a short unique session ID (8 hex chars)."""
        import secrets

        return secrets.token_hex(4)


# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------

_default_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Return the default session store singleton."""
    global _default_store
    if _default_store is None:
        _default_store = SessionStore()
    return _default_store
