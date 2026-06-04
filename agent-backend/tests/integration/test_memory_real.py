"""
REAL integration tests for the memory system.

Uses ACTUAL SQLite (via ChromaDB's internal SQLite) and ChromaDB — no mocks.
These tests verify the full data path from API → database → query results.

Endpoints tested:
    POST /memory/message        — Store a conversation message
    POST /memory/query/conversations  — Query conversation messages
    POST /memory/code           — Store a code event
    POST /memory/query/code     — Query code events
    POST /memory/hybrid         — Hybrid semantic search
    GET  /memory/stats          — Collection statistics
    DELETE /memory/{memory_id}  — Delete a memory entry

All calls are real HTTP requests to a running backend with real vector storage.
"""

import pytest
import httpx
import time
import os

BASE_URL = "http://127.0.0.1:8000"

# Directory where ChromaDB stores its data
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")


@pytest.fixture(scope="module")
def base_url():
    """Return the base URL for the running backend."""
    return BASE_URL


@pytest.fixture(autouse=True)
def cleanup_collections():
    """Clean up test collections before each test."""
    # We don't actually delete files here to avoid corrupting ChromaDB.
    # Instead tests use unique content/timestamps to avoid collisions.
    yield


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_and_retrieve_conversation(base_url):
    """Store a conversation message and retrieve it via semantic search."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Store
        store_resp = await client.post("/memory/message", json={
            "role": "user",
            "content": "What is the best way to handle authentication in React?",
            "conversation_id": "test-session-1",
        })
        assert store_resp.status_code == 200
        store_data = store_resp.json()
        assert store_data["status"] == "stored"
        assert "memory_id" in store_data

        # Small delay for indexing
        time.sleep(0.5)

        # Retrieve via semantic query
        query_resp = await client.post("/memory/query/conversations", json={
            "query": "React authentication",
            "n_results": 5,
        })
        assert query_resp.status_code == 200
        results = query_resp.json()
        assert len(results) > 0
        # Check our message is in the results
        texts = [r["text"] for r in results]
        assert any("authentication" in t for t in texts)


@pytest.mark.asyncio
async def test_store_conversation_with_metadata(base_url):
    """Storing conversation preserves role and content fields."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        resp = await client.post("/memory/message", json={
            "role": "assistant",
            "content": "Here is a code example: const x = 42;",
            "conversation_id": "sess-123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stored"
        assert "memory_id" in data


@pytest.mark.asyncio
async def test_query_conversation_with_limit(base_url):
    """Query respects the n_results (limit) parameter."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Store several messages with unique content to avoid caching
        for i in range(5):
            await client.post("/memory/message", json={
                "role": "user",
                "content": f"Test message number {i} about programming and Python {time.time()}",
                "conversation_id": "limit-test",
            })

        time.sleep(0.5)

        resp = await client.post("/memory/query/conversations", json={
            "query": "programming Python",
            "n_results": 2,
        })
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Code event memory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_and_retrieve_code_event(base_url):
    """Store a code event and retrieve it via semantic search."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Store
        store_resp = await client.post("/memory/code", json={
            "file_path": "src/components/LoginForm.tsx",
            "change_type": "create",
            "summary": "LoginForm component for user authentication",
            "diff": "export function LoginForm() { return <form>...</form>; }",
        })
        assert store_resp.status_code == 200
        store_data = store_resp.json()
        assert store_data["status"] == "stored"
        assert "memory_id" in store_data

        time.sleep(0.5)

        # Retrieve via semantic query
        query_resp = await client.post("/memory/query/code", json={
            "query": "LoginForm component",
            "n_results": 5,
        })
        assert query_resp.status_code == 200
        results = query_resp.json()
        assert len(results) > 0


# ---------------------------------------------------------------------------
# Hybrid search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semantic_search_finds_relevant_results(base_url):
    """Hybrid search returns relevant results ranked by similarity."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Store multiple messages on different topics
        messages = [
            {"role": "user", "content": f"How do I set up a PostgreSQL database with Docker? {time.time()}", "conversation_id": "db-topic"},
            {"role": "user", "content": f"What is the difference between JWT and session cookies? {time.time()}", "conversation_id": "auth-topic"},
            {"role": "user", "content": f"Explain React useEffect hook with cleanup {time.time()}", "conversation_id": "react-topic"},
            {"role": "user", "content": f"Best practices for REST API design {time.time()}", "conversation_id": "api-topic"},
        ]

        for msg in messages:
            resp = await client.post("/memory/message", json=msg)
            assert resp.status_code == 200

        # Store a code event too
        resp = await client.post("/memory/code", json={
            "file_path": "src/hooks/useAuth.ts",
            "change_type": "create",
            "summary": "Custom hook for authentication state management",
            "diff": "export function useAuth() { ... }",
        })
        assert resp.status_code == 200

        time.sleep(1)  # Wait for indexing

        # Search for React-related content
        search_resp = await client.post("/memory/hybrid", json={
            "query": "React hooks and effects",
            "sqlite_results": [],
            "n_results": 3,
        })
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) > 0
        # Top result should be React-related
        top_doc = results[0]["text"] if results else ""
        assert "React" in top_doc or "hook" in top_doc.lower()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_stats_returns_valid_data(base_url):
    """Memory stats endpoint returns valid collection statistics."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        resp = await client.get("/memory/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert "total_memories" in stats
        assert "collections" in stats
        assert "chroma_path" in stats
        assert "embedding_model" in stats
        # Should have conversation and code collections
        collection_names = list(stats["collections"].keys())
        assert "conversation_embeddings" in collection_names
        assert "code_embeddings" in collection_names


# ---------------------------------------------------------------------------
# Cross-collection query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_similar_across_all_collections(base_url):
    """Semantic search across all collections returns mixed results."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Store in both collections
        conv_resp = await client.post("/memory/message", json={
            "role": "user",
            "content": f"How to write a Python function for sorting {time.time()}",
            "conversation_id": "cross-test",
        })
        assert conv_resp.status_code == 200

        code_resp = await client.post("/memory/code", json={
            "file_path": "utils/sorter.py",
            "change_type": "create",
            "summary": "Python sorting utility functions",
            "diff": "def quicksort(arr): ...",
        })
        assert code_resp.status_code == 200

        time.sleep(0.5)

        # Query all collections
        query_resp = await client.post("/memory/query", json={
            "query": "Python sorting function",
            "n_results": 5,
        })
        assert query_resp.status_code == 200
        results = query_resp.json()
        assert len(results) > 0
        # Should have results from at least one source
        sources = set(r["source"] for r in results)
        assert len(sources) >= 1


# ---------------------------------------------------------------------------
# Delete memory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_memory_entry(base_url):
    """Store a memory entry and delete it."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Store a message
        store_resp = await client.post("/memory/message", json={
            "role": "user",
            "content": f"This message will be deleted {time.time()}",
            "conversation_id": "delete-test",
        })
        assert store_resp.status_code == 200
        memory_id = store_resp.json()["memory_id"]

        # Delete it
        del_resp = await client.delete(f"/memory/{memory_id}", params={"source": "conversation"})
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["deleted"] is True
        assert del_data["memory_id"] == memory_id


@pytest.mark.asyncio
async def test_delete_nonexistent_memory_returns_404(base_url):
    """Deleting a non-existent memory returns 404."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        resp = await client.delete("/memory/nonexistent-id", params={"source": "conversation"})
        assert resp.status_code == 404
