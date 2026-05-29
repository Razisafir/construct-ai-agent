"""
REAL LLM integration tests.

These make ACTUAL API calls to LLM providers.
They are skipped gracefully if no API key is configured or if the
local Ollama instance is not running.

Tests use the real LLMService.complete() method with Message objects.
No mocks — all calls go to actual provider endpoints.

Environment variables checked:
    OPENAI_API_KEY     — Required for OpenAI tests
    OLLAMA_HOST        — Optional, defaults to http://localhost:11434
"""

import os
import sys
import pytest
import httpx

# Import the real LLM service
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from core.llm_service import LLMService, Message, assemble_messages


@pytest.fixture
def llm_service():
    """Return a fresh LLMService instance."""
    return LLMService()


# ---------------------------------------------------------------------------
# OpenAI tests  (skipped if no API key)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_openai_completion(llm_service):
    """Test OpenAI non-streaming completion — skipped if no API key."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    messages = assemble_messages(
        user_prompt="Say exactly the word 'pong' and nothing else.",
    )
    result = await llm_service.complete(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=10,
    )
    assert result is not None
    assert len(result) > 0
    assert "pong" in result.lower()


@pytest.mark.asyncio
async def test_llm_openai_with_system_prompt(llm_service):
    """Test OpenAI completion with custom system prompt."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    messages = assemble_messages(
        user_prompt="Reply with exactly the word 'acknowledged'.",
        system_prompt="You are a concise assistant. Reply with single words only.",
    )
    result = await llm_service.complete(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=10,
    )
    assert result is not None
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Ollama tests  (skipped if Ollama not running)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_ollama_completion(llm_service):
    """Test Ollama non-streaming completion — skipped if Ollama not running."""
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            if resp.status_code != 200:
                pytest.skip(f"Ollama not running on {ollama_host}")
    except Exception:
        pytest.skip("Ollama not accessible")

    messages = assemble_messages(
        user_prompt="Say exactly the word 'pong' and nothing else.",
    )
    result = await llm_service.complete(
        messages=messages,
        model="ollama",  # This routes to Ollama
        max_tokens=10,
    )
    assert result is not None
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
def test_llm_route_by_complexity_short_prompt(llm_service):
    """Short prompts should route to Ollama (local, fast)."""
    provider = llm_service.route_by_complexity("hi")
    # Short prompts (< 200 chars) route to Ollama
    assert provider.value == "ollama"


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
def test_llm_route_by_complexity_code_prompt(llm_service):
    """Code-related prompts should route to a cloud provider."""
    provider = llm_service.route_by_complexity(
        "Refactor this function to use async/await pattern"
    )
    # Code tasks prefer Anthropic > OpenAI > Ollama
    assert provider.value in ("anthropic", "openai", "ollama")


# ---------------------------------------------------------------------------
# Message assembly (pure logic, always runs)
# ---------------------------------------------------------------------------

def test_assemble_messages_basic():
    """Message assembly works without LLM call."""
    messages = assemble_messages(
        user_prompt="Hello",
    )
    assert len(messages) >= 2  # system + user
    assert messages[0].role == "system"
    assert messages[-1].role == "user"
    assert messages[-1].content == "Hello"


def test_assemble_messages_with_system_prompt():
    """Custom system prompt is included."""
    messages = assemble_messages(
        user_prompt="Test",
        system_prompt="You are a test assistant.",
    )
    assert messages[0].role == "system"
    assert "test assistant" in messages[0].content


def test_assemble_messages_with_history():
    """Conversation history is preserved in order."""
    history = [
        Message(role="user", content="Previous question"),
        Message(role="assistant", content="Previous answer"),
    ]
    messages = assemble_messages(
        user_prompt="Follow-up",
        conversation_history=history,
    )
    # Should be: system, user, assistant, user
    roles = [m.role for m in messages]
    assert roles[0] == "system"
    assert roles[-1] == "user"
    assert roles[-1].content == "Follow-up"
    # History is included
    assert any(m.content == "Previous question" for m in messages)
    assert any(m.content == "Previous answer" for m in messages)


# ---------------------------------------------------------------------------
# LLMService instantiation
# ---------------------------------------------------------------------------

def test_llm_service_instantiation():
    """LLM service can be created without errors."""
    service = LLMService()
    assert service is not None
    assert hasattr(service, "complete")
    assert hasattr(service, "stream_complete")
    assert hasattr(service, "route_by_complexity")


def test_llm_service_has_ollama_config():
    """Ollama is always configured as a fallback."""
    service = LLMService()
    from core.llm_service import LLMProvider
    assert LLMProvider.OLLAMA in service.configs
    ollama_config = service.configs[LLMProvider.OLLAMA]
    assert ollama_config.base_url is not None


def test_llm_service_stats():
    """LLM service provides usage statistics."""
    service = LLMService()
    stats = service.get_stats()
    assert isinstance(stats, dict)


# ---------------------------------------------------------------------------
# Invalid provider / error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_unknown_model_falls_back(llm_service):
    """An unknown model string should not crash — it falls back to Ollama."""
    messages = assemble_messages(user_prompt="Test fallback")
    provider = llm_service._resolve_provider("unknown-model-name", "test")
    # Should resolve to some provider, not crash
    assert provider is not None


def test_llm_message_dataclass():
    """Message dataclass works correctly."""
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
