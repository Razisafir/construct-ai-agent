"""
REAL integration tests for the agent session system.

Tests the full agent lifecycle with a running backend over real HTTP.
No mocks — every call hits the actual FastAPI application.

Endpoints tested:
    POST /api/agent/start          — Start a new agent session
    GET  /api/agent/{id}/events    — Poll session events
    GET  /api/agent/{id}/status    — Get session status
    POST /api/agent/{id}/pause     — Pause a session
    POST /api/agent/{id}/resume    — Resume a paused session
    POST /api/agent/{id}/stop      — Stop a session

Plus the executor-based agent endpoints:
    POST /agent/start              — Start via executor
    GET  /agent/{id}/status        — Get executor session status
    POST /agent/{id}/pause         — Pause executor session
    POST /agent/{id}/resume        — Resume executor session
    POST /agent/{id}/stop          — Stop executor session
    GET  /agent/{id}/output        — Get session output
    GET  /agent/sessions           — List all sessions
"""

import pytest
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture
async def client():
    """Yield an async HTTP client connected to the running backend."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as c:
        yield c


# ---------------------------------------------------------------------------
# In-memory agent session endpoints  (/api/agent/*)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_full_lifecycle(client):
    """Complete agent lifecycle: start → get events → verify completion."""
    session_id = f"integration-{int(time.time())}"
    goal = "Create a React todo list component"

    # Start
    start_resp = await client.post("/api/agent/start", json={
        "session_id": session_id,
        "goal": goal,
        "project_path": ".",
        "mode": "interactive",
    })
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["status"] == "started"
    assert start_data["session_id"] == session_id

    # Poll for events (up to 15 seconds)
    event_types_found = set()
    for _ in range(30):
        events_resp = await client.get(f"/api/agent/{session_id}/events", params={"after": 0})
        if events_resp.status_code == 200:
            events = events_resp.json()
            for e in events:
                event_types_found.add(e["type"])

        status_resp = await client.get(f"/api/agent/{session_id}/status")
        if status_resp.status_code == 200:
            if status_resp.json()["status"] in ("completed", "stopped", "failed"):
                break
        time.sleep(0.5)

    # Verify we got meaningful events
    assert "thought" in event_types_found, f"Expected thought events, got: {event_types_found}"

    # Status should show goal
    status_resp = await client.get(f"/api/agent/{session_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["goal"] == goal
    assert "session_id" in status_data

    # Cleanup
    await client.post(f"/api/agent/{session_id}/stop")


@pytest.mark.asyncio
async def test_agent_pause_and_resume(client):
    """Agent can be paused and resumed."""
    session_id = f"pause-test-{int(time.time())}"

    start_resp = await client.post("/api/agent/start", json={
        "session_id": session_id,
        "goal": "Write a Python function to sort a list",
        "project_path": ".",
        "mode": "interactive",
    })
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "started"

    # Give it a moment to start
    time.sleep(0.5)

    # Pause
    pause_resp = await client.post(f"/api/agent/{session_id}/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"

    # Verify paused
    status_resp = await client.get(f"/api/agent/{session_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "paused"

    # Resume
    resume_resp = await client.post(f"/api/agent/{session_id}/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "running"

    # Cleanup
    await client.post(f"/api/agent/{session_id}/stop")


@pytest.mark.asyncio
async def test_concurrent_agent_sessions(client):
    """Multiple agent sessions can run concurrently."""
    sessions = []
    for i in range(3):
        sid = f"concurrent-{int(time.time())}-{i}"
        resp = await client.post("/api/agent/start", json={
            "session_id": sid,
            "goal": f"Task {i}: create component",
            "project_path": ".",
            "mode": "interactive",
        })
        assert resp.status_code == 200
        sessions.append(sid)
        time.sleep(0.2)

    # All should exist
    for sid in sessions:
        status_resp = await client.get(f"/api/agent/{sid}/status")
        assert status_resp.status_code == 200

    # Cleanup all
    for sid in sessions:
        await client.post(f"/api/agent/{sid}/stop")


@pytest.mark.asyncio
async def test_agent_404_for_missing_session(client):
    """Operations on non-existent sessions return 404."""
    resp = await client.get("/api/agent/nonexistent-session/status")
    assert resp.status_code == 404

    resp = await client.post("/api/agent/nonexistent-session/pause")
    assert resp.status_code in (404, 400)

    resp = await client.post("/api/agent/nonexistent-session/resume")
    assert resp.status_code in (404, 400)


# ---------------------------------------------------------------------------
# Executor-based agent endpoints  (/agent/*)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_executor_start_and_status(client):
    """Start an agent session via the executor and check its status."""
    goal = "Create a simple navigation bar component"

    start_resp = await client.post("/agent/start", json={
        "goal": goal,
        "project_path": ".",
    })
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["status"] in ("running", "started", "idle")
    assert "session_id" in start_data
    session_id = start_data["session_id"]

    # Check status
    status_resp = await client.get(f"/agent/{session_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["goal"] == goal
    assert "session_id" in status_data
    assert "tasks" in status_data

    # Cleanup: stop the session
    stop_resp = await client.post(f"/agent/{session_id}/stop")
    assert stop_resp.status_code == 200


@pytest.mark.asyncio
async def test_executor_pause_resume_stop(client):
    """Pause, resume, and stop an executor-based session."""
    start_resp = await client.post("/agent/start", json={
        "goal": "Write unit tests for a helper function",
        "project_path": ".",
    })
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # Wait a moment for tasks to be created
    time.sleep(0.3)

    # Pause
    pause_resp = await client.post(f"/agent/{session_id}/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"

    # Status should reflect paused
    status_resp = await client.get(f"/agent/{session_id}/status")
    assert status_resp.json()["status"] == "paused"

    # Resume
    resume_resp = await client.post(f"/agent/{session_id}/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "running"

    # Stop
    stop_resp = await client.post(f"/agent/{session_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"


@pytest.mark.asyncio
async def test_list_agent_sessions(client):
    """List all agent sessions — should return a list."""
    resp = await client.get("/agent/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert "total" in data
    assert isinstance(data["sessions"], list)
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_agent_output_events(client):
    """Get output events for a running agent session."""
    goal = "Build a simple login page"

    start_resp = await client.post("/agent/start", json={
        "goal": goal,
        "project_path": ".",
    })
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    # Poll output a few times
    for _ in range(5):
        output_resp = await client.get(f"/agent/{session_id}/output")
        if output_resp.status_code == 200:
            data = output_resp.json()
            assert "events" in data
            assert "has_more" in data
        time.sleep(0.3)

    # Cleanup
    await client.post(f"/agent/{session_id}/stop")
