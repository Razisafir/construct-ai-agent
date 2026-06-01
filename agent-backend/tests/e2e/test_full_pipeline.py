"""
End-to-end pipeline test for the Construct Agent.

Tests the full flow:
1. Health check
2. Start agent session
3. Poll for events
4. Verify session completes
5. Check session status
"""

import pytest
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as c:
        yield c


@pytest.mark.asyncio
async def test_health_check(client):
    """Backend is running and healthy."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_lifecycle(client):
    """Full agent session lifecycle: start → events → complete."""
    session_id = f"test-session-{int(time.time())}"
    goal = "Create a React login form component"

    # 1. Start the agent session
    start_resp = await client.post("/api/agent/start", json={
        "session_id": session_id,
        "goal": goal,
        "project_path": ".",
        "mode": "interactive",
    })
    assert start_resp.status_code == 200
    start_data = start_resp.json()
    assert start_data["session_id"] == session_id
    assert start_data["status"] == "started"

    # 2. Poll for events (up to 30 seconds)
    events = []
    last_timestamp = 0
    for _ in range(60):  # 60 * 0.5s = 30s max
        events_resp = await client.get(
            f"/api/agent/{session_id}/events",
            params={"after": last_timestamp}
        )
        assert events_resp.status_code == 200
        new_events = events_resp.json()
        events.extend(new_events)

        if new_events:
            last_timestamp = max(e["timestamp"] for e in new_events)

        # Check if complete
        status_resp = await client.get(f"/api/agent/{session_id}/status")
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "stopped", "failed"):
                break

        time.sleep(0.5)

    # 3. Verify we got events
    assert len(events) > 0, "Expected at least some events"

    # 4. Check session status
    status_resp = await client.get(f"/api/agent/{session_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["session_id"] == session_id
    assert status_data["status"] in ("completed", "stopped", "failed")
    assert status_data["goal"] == goal

    # 5. Verify event types
    event_types = {e["type"] for e in events}
    assert "thought" in event_types, "Expected at least one thought event"

    # 6. Stop the session (cleanup)
    await client.post(f"/api/agent/{session_id}/stop")


@pytest.mark.asyncio
async def test_agent_pause_resume(client):
    """Agent session can be paused and resumed."""
    session_id = f"test-pause-{int(time.time())}"

    # Start
    start_resp = await client.post("/api/agent/start", json={
        "session_id": session_id,
        "goal": "Create a simple API endpoint",
        "project_path": ".",
        "mode": "interactive",
    })
    assert start_resp.status_code == 200

    # Pause
    pause_resp = await client.post(f"/api/agent/{session_id}/pause")
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "paused"

    # Verify paused
    status_resp = await client.get(f"/api/agent/{session_id}/status")
    assert status_resp.json()["status"] == "paused"

    # Resume
    resume_resp = await client.post(f"/api/agent/{session_id}/resume")
    assert resume_resp.status_code == 200
    assert resume_resp.json()["status"] == "running"

    # Cleanup
    await client.post(f"/api/agent/{session_id}/stop")


@pytest.mark.asyncio
async def test_agent_not_found(client):
    """Requests for non-existent sessions return 404."""
    resp = await client.get("/api/agent/nonexistent/status")
    assert resp.status_code == 404

    resp = await client.post("/api/agent/nonexistent/pause")
    assert resp.status_code == 404

    resp = await client.post("/api/agent/nonexistent/stop")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_session(client):
    """Starting a session with duplicate ID returns 409."""
    session_id = f"test-dup-{int(time.time())}"

    # First start
    resp1 = await client.post("/api/agent/start", json={
        "session_id": session_id,
        "goal": "First goal",
        "project_path": ".",
        "mode": "interactive",
    })
    assert resp1.status_code == 200

    # Duplicate
    resp2 = await client.post("/api/agent/start", json={
        "session_id": session_id,
        "goal": "Second goal",
        "project_path": ".",
        "mode": "interactive",
    })
    assert resp2.status_code == 409

    # Cleanup
    await client.post(f"/api/agent/{session_id}/stop")
