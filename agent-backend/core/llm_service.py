"""
LLM Service — Unified interface for multiple LLM providers.

Supports: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini), Ollama (local)

Features:
- Smart routing: local for simple tasks, cloud for complex reasoning
- Streaming: yield tokens as they're generated
- Context assembly: build prompt from memory + current task + codebase context
- Fallback: if a cloud provider fails, automatically falls back to Ollama
- Token logging: all calls are logged with timing and (where available) token counts
"""

import os
import time
import json
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import (
    AsyncIterator,
    Optional,
    Dict,
    List,
    Any,
    Callable,
    Awaitable,
)

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider / model configuration
# ---------------------------------------------------------------------------


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuration for a single LLM provider."""

    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # used by Ollama
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMCallLog:
    """Log entry for a single LLM call."""

    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are Construct, an autonomous AI coding assistant. You help users by "
    "reading files, writing code, running tests, and managing git repositories. "
    "You have access to tools for file operations, shell commands, git operations, "
    "and code analysis. Always be precise, write clean code, and verify your changes. "
    "When you need to perform an action, use the available tools."
)


def _build_tool_context(tool_schemas: List[Dict[str, Any]]) -> str:
    """Build a system prompt section describing available tools."""
    lines = ["\n## Available Tools\n"]
    for schema in tool_schemas:
        func = schema.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def assemble_messages(
    user_prompt: str,
    system_prompt: Optional[str] = None,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
    memory_context: Optional[str] = None,
    conversation_history: Optional[List[Message]] = None,
) -> List[Message]:
    """
    Assemble a complete message list for an LLM call.

    The assembled prompt includes (in order):
    1. System message with tool descriptions
    2. Optional memory context from semantic search
    3. Optional conversation history
    4. The current user prompt

    Parameters
    ----------
    user_prompt:
        The current user request or task description.
    system_prompt:
        Override the default system prompt.
    tool_schemas:
        JSON schemas of available tools (for function calling).
    memory_context:
        Retrieved memories relevant to the task.
    conversation_history:
        Previous conversation turns.

    Returns
    -------
    list[Message]
        Ordered list of messages ready for the LLM.
    """
    messages: List[Message] = []

    # 1. System prompt with tool context
    sys_content = system_prompt or DEFAULT_SYSTEM_PROMPT
    if tool_schemas:
        sys_content += _build_tool_context(tool_schemas)
    messages.append(Message(role="system", content=sys_content))

    # 2. Memory context
    if memory_context:
        messages.append(
            Message(
                role="system",
                content=f"\n## Relevant Context from Memory\n{memory_context}\n",
            )
        )

    # 3. Conversation history
    if conversation_history:
        messages.extend(conversation_history)

    # 4. User prompt
    messages.append(Message(role="user", content=user_prompt))

    return messages


# ---------------------------------------------------------------------------
# LLM Service
# ---------------------------------------------------------------------------


class LLMService:
    """Unified LLM interface with multi-provider support."""

    def __init__(self) -> None:
        self.configs: Dict[LLMProvider, LLMConfig] = {}
        self._init_configs()
        self._clients: Dict[LLMProvider, Any] = {}
        self._call_history: List[LLMCallLog] = []
        self._session: Optional[aiohttp.ClientSession] = None

    # -- Configuration ------------------------------------------------------

    def _init_configs(self) -> None:
        """Load provider configurations from environment variables."""
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.configs[LLMProvider.OPENAI] = LLMConfig(
                provider=LLMProvider.OPENAI,
                model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                api_key=openai_key,
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "4096")),
            )
            logger.info(
                "OpenAI configured: model=%s",
                self.configs[LLMProvider.OPENAI].model,
            )

        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.configs[LLMProvider.ANTHROPIC] = LLMConfig(
                provider=LLMProvider.ANTHROPIC,
                model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                api_key=anthropic_key,
                temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096")),
            )
            logger.info(
                "Anthropic configured: model=%s",
                self.configs[LLMProvider.ANTHROPIC].model,
            )

        # Google
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            self.configs[LLMProvider.GOOGLE] = LLMConfig(
                provider=LLMProvider.GOOGLE,
                model=os.getenv("GOOGLE_MODEL", "gemini-1.5-pro"),
                api_key=google_key,
                temperature=float(os.getenv("GOOGLE_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("GOOGLE_MAX_TOKENS", "4096")),
            )
            logger.info(
                "Google configured: model=%s",
                self.configs[LLMProvider.GOOGLE].model,
            )

        # Ollama (local — always configured as fallback)
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
        self.configs[LLMProvider.OLLAMA] = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model=ollama_model,
            base_url=ollama_host,
            temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", "4096")),
        )
        logger.info("Ollama configured: host=%s, model=%s", ollama_host, ollama_model)

    # -- Client management --------------------------------------------------

    def _get_openai_client(self):
        """Lazy-load and cache the OpenAI async client."""
        if LLMProvider.OPENAI not in self._clients:
            import openai

            config = self.configs[LLMProvider.OPENAI]
            self._clients[LLMProvider.OPENAI] = openai.AsyncOpenAI(
                api_key=config.api_key,
                timeout=config.timeout,
            )
        return self._clients[LLMProvider.OPENAI]

    def _get_anthropic_client(self):
        """Lazy-load and cache the Anthropic async client."""
        if LLMProvider.ANTHROPIC not in self._clients:
            import anthropic

            config = self.configs[LLMProvider.ANTHROPIC]
            self._clients[LLMProvider.ANTHROPIC] = anthropic.AsyncAnthropic(
                api_key=config.api_key,
                timeout=config.timeout,
            )
        return self._clients[LLMProvider.ANTHROPIC]

    def _get_aiohttp_session(self) -> aiohttp.ClientSession:
        """Lazy-load and cache the shared aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    # -- Routing ------------------------------------------------------------

    def route_by_complexity(self, prompt: str) -> LLMProvider:
        """
        Select the best provider based on prompt complexity.

        Heuristics:
        - Short prompts (< 200 chars) -> Ollama (local, fast, free)
        - Code generation tasks -> OpenAI/Anthropic (best code quality)
        - Complex reasoning -> Anthropic (best reasoning)
        - Quick completions -> Ollama
        - Fallback order: Anthropic > OpenAI > Ollama

        Parameters
        ----------
        prompt:
            The user prompt to route.

        Returns
        -------
        LLMProvider
            The selected provider.
        """
        prompt_lower = prompt.lower()

        # Short/simple prompts -> Ollama
        if len(prompt) < 200:
            return LLMProvider.OLLAMA

        # Code-heavy tasks -> prefer OpenAI or Anthropic
        code_keywords = [
            "refactor", "rewrite", "implement", "function",
            "class", "debug", "fix", "optimize", "test",
            "write code", "generate code", "code review",
        ]
        is_code_task = any(kw in prompt_lower for kw in code_keywords)

        if is_code_task:
            if LLMProvider.ANTHROPIC in self.configs:
                return LLMProvider.ANTHROPIC
            if LLMProvider.OPENAI in self.configs:
                return LLMProvider.OPENAI

        # Complex reasoning -> Anthropic
        reasoning_keywords = [
            "explain", "analyze", "compare", "design",
            "architecture", "why", "how to", "strategy",
        ]
        is_reasoning_task = any(kw in prompt_lower for kw in reasoning_keywords)

        if is_reasoning_task and LLMProvider.ANTHROPIC in self.configs:
            return LLMProvider.ANTHROPIC

        # Default priority: Anthropic > OpenAI > Ollama
        if LLMProvider.ANTHROPIC in self.configs:
            return LLMProvider.ANTHROPIC
        if LLMProvider.OPENAI in self.configs:
            return LLMProvider.OPENAI
        if LLMProvider.GOOGLE in self.configs:
            return LLMProvider.GOOGLE

        # Always-available fallback
        return LLMProvider.OLLAMA

    def _resolve_provider(self, model: str, prompt: str) -> LLMProvider:
        """Resolve a model string or 'auto' to a concrete provider."""
        if model == "auto":
            return self.route_by_complexity(prompt)
        try:
            return LLMProvider(model)
        except ValueError:
            # Treat unknown model strings as provider hints
            if "gpt" in model.lower() and LLMProvider.OPENAI in self.configs:
                return LLMProvider.OPENAI
            if "claude" in model.lower() and LLMProvider.ANTHROPIC in self.configs:
                return LLMProvider.ANTHROPIC
            if "gemini" in model.lower() and LLMProvider.GOOGLE in self.configs:
                return LLMProvider.GOOGLE
            return LLMProvider.OLLAMA

    # -- Non-streaming completion -------------------------------------------

    async def complete(
        self,
        messages: List[Message],
        model: str = "auto",
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Non-streaming completion. Returns the full response text.

        If the primary provider fails, automatically falls back to Ollama.

        Parameters
        ----------
        messages:
            Conversation messages.
        model:
            Model identifier or ``"auto"`` for smart routing.
        tool_schemas:
            Optional tool schemas for function calling.
        temperature:
            Override the default temperature.
        max_tokens:
            Override the default max_tokens.

        Returns
        -------
        str
            The LLM's response text.
        """
        prompt_text = messages[-1].content if messages else ""
        provider = self._resolve_provider(model, prompt_text)

        try:
            return await self._complete_with_provider(
                provider, messages, tool_schemas, temperature, max_tokens
            )
        except Exception as exc:
            logger.warning(
                "Primary provider %s failed: %s. Falling back to Ollama.",
                provider.value,
                exc,
            )
            if provider != LLMProvider.OLLAMA:
                return await self._complete_with_provider(
                    LLMProvider.OLLAMA, messages, tool_schemas, temperature, max_tokens
                )
            raise

    async def _complete_with_provider(
        self,
        provider: LLMProvider,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Dispatch to the appropriate provider implementation."""
        if provider == LLMProvider.OPENAI:
            return await self._openai_complete(messages, tool_schemas, temperature, max_tokens)
        elif provider == LLMProvider.ANTHROPIC:
            return await self._anthropic_complete(messages, tool_schemas, temperature, max_tokens)
        elif provider == LLMProvider.GOOGLE:
            return await self._google_complete(messages, tool_schemas, temperature, max_tokens)
        elif provider == LLMProvider.OLLAMA:
            return await self._ollama_complete(messages, tool_schemas, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # -- Streaming completion -----------------------------------------------

    async def stream_complete(
        self,
        messages: List[Message],
        model: str = "auto",
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming completion. Yields text chunks as they're generated.

        Falls back to Ollama if the primary provider fails.

        Parameters
        ----------
        messages:
            Conversation messages.
        model:
            Model identifier or ``"auto"`` for smart routing.
        tool_schemas:
            Optional tool schemas for function calling.
        temperature:
            Override the default temperature.
        max_tokens:
            Override the default max_tokens.

        Yields
        ------
        str
            Partial text chunks from the LLM.
        """
        prompt_text = messages[-1].content if messages else ""
        provider = self._resolve_provider(model, prompt_text)

        try:
            async for chunk in self._stream_with_provider(
                provider, messages, tool_schemas, temperature, max_tokens
            ):
                yield chunk
        except Exception as exc:
            logger.warning(
                "Primary provider %s streaming failed: %s. Falling back to Ollama.",
                provider.value,
                exc,
            )
            if provider != LLMProvider.OLLAMA:
                async for chunk in self._stream_with_provider(
                    LLMProvider.OLLAMA, messages, tool_schemas, temperature, max_tokens
                ):
                    yield chunk
            else:
                yield f"\n[Error: {exc}]"

    async def _stream_with_provider(
        self,
        provider: LLMProvider,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Dispatch streaming to the appropriate provider."""
        if provider == LLMProvider.OPENAI:
            async for chunk in self._openai_stream(messages, tool_schemas, temperature, max_tokens):
                yield chunk
        elif provider == LLMProvider.ANTHROPIC:
            async for chunk in self._anthropic_stream(messages, tool_schemas, temperature, max_tokens):
                yield chunk
        elif provider == LLMProvider.GOOGLE:
            async for chunk in self._google_stream(messages, tool_schemas, temperature, max_tokens):
                yield chunk
        elif provider == LLMProvider.OLLAMA:
            async for chunk in self._ollama_stream(messages, tool_schemas, temperature, max_tokens):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # -- Provider implementations: OpenAI -----------------------------------

    async def _openai_complete(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Non-streaming OpenAI completion."""
        client = self._get_openai_client()
        config = self.configs[LLMProvider.OPENAI]
        start = time.time()

        openai_messages = [{"role": m.role, "content": m.content} for m in messages]
        kwargs: Dict[str, Any] = {
            "model": config.model,
            "messages": openai_messages,
            "temperature": temperature or config.temperature,
            "max_tokens": max_tokens or config.max_tokens,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        response = await client.chat.completions.create(**kwargs)

        duration_ms = int((time.time() - start) * 1000)
        usage = response.usage
        self._log_call(
            LLMCallLog(
                provider="openai",
                model=config.model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                duration_ms=duration_ms,
            )
        )

        # Check for tool calls
        choice = response.choices[0]
        if choice.message.tool_calls:
            return json.dumps(
                {
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                        for tc in choice.message.tool_calls
                    ]
                }
            )

        return choice.message.content or ""

    async def _openai_stream(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Streaming OpenAI completion."""
        client = self._get_openai_client()
        config = self.configs[LLMProvider.OPENAI]
        start = time.time()

        openai_messages = [{"role": m.role, "content": m.content} for m in messages]
        kwargs: Dict[str, Any] = {
            "model": config.model,
            "messages": openai_messages,
            "temperature": temperature or config.temperature,
            "max_tokens": max_tokens or config.max_tokens,
            "stream": True,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        stream = await client.chat.completions.create(**kwargs)
        full_content = ""

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                full_content += delta.content
                yield delta.content

        duration_ms = int((time.time() - start) * 1000)
        self._log_call(
            LLMCallLog(
                provider="openai",
                model=config.model,
                prompt_tokens=0,  # not available in streaming
                completion_tokens=0,
                duration_ms=duration_ms,
            )
        )

    # -- Provider implementations: Anthropic --------------------------------

    async def _anthropic_complete(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Non-streaming Anthropic completion."""
        client = self._get_anthropic_client()
        config = self.configs[LLMProvider.ANTHROPIC]
        start = time.time()

        # Separate system from conversation
        system_msg = ""
        conversation: List[Dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_msg += m.content + "\n"
            else:
                conversation.append({"role": m.role, "content": m.content})

        kwargs: Dict[str, Any] = {
            "model": config.model,
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature or config.temperature,
            "messages": conversation,
        }
        if system_msg.strip():
            kwargs["system"] = system_msg.strip()
        if tool_schemas:
            anthropic_tools = []
            for schema in tool_schemas:
                func = schema.get("function", {})
                anthropic_tools.append(
                    {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )
            kwargs["tools"] = anthropic_tools

        response = await client.messages.create(**kwargs)

        duration_ms = int((time.time() - start) * 1000)
        self._log_call(
            LLMCallLog(
                provider="anthropic",
                model=config.model,
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
                duration_ms=duration_ms,
            )
        )

        # Check for tool use
        for block in response.content:
            if block.type == "tool_use":
                return json.dumps(
                    {
                        "tool_calls": [
                            {
                                "id": block.id,
                                "name": block.name,
                                "arguments": json.dumps(block.input),
                            }
                        ]
                    }
                )

        return "".join(block.text for block in response.content if block.type == "text")

    async def _anthropic_stream(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Streaming Anthropic completion."""
        client = self._get_anthropic_client()
        config = self.configs[LLMProvider.ANTHROPIC]
        start = time.time()

        # Separate system from conversation
        system_msg = ""
        conversation: List[Dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system_msg += m.content + "\n"
            else:
                conversation.append({"role": m.role, "content": m.content})

        kwargs: Dict[str, Any] = {
            "model": config.model,
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature or config.temperature,
            "messages": conversation,
        }
        if system_msg.strip():
            kwargs["system"] = system_msg.strip()
        if tool_schemas:
            anthropic_tools = []
            for schema in tool_schemas:
                func = schema.get("function", {})
                anthropic_tools.append(
                    {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )
            kwargs["tools"] = anthropic_tools

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

        # Log after stream completes
        duration_ms = int((time.time() - start) * 1000)
        self._log_call(
            LLMCallLog(
                provider="anthropic",
                model=config.model,
                duration_ms=duration_ms,
            )
        )

    # -- Provider implementations: Google -----------------------------------

    async def _google_complete(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Non-streaming Google Gemini completion via REST API."""
        config = self.configs[LLMProvider.GOOGLE]
        start = time.time()

        # Build content parts
        contents = []
        system_parts = []
        for m in messages:
            if m.role == "system":
                system_parts.append({"text": m.content})
            else:
                role = "user" if m.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.content}]})

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
        )
        # SECURITY: API key is sent via x-goog-api-key header instead of URL
        # query parameter to prevent logging by proxies and servers.
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "x-goog-api-key": config.api_key or "",
        }
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature or config.temperature,
                "maxOutputTokens": max_tokens or config.max_tokens,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}
        if tool_schemas:
            # Google uses functionDeclarations format
            declarations = []
            for schema in tool_schemas:
                func = schema.get("function", {})
                declarations.append(
                    {
                        "name": func.get("name", ""),
                        "description": func.get("description", ""),
                        "parameters": func.get("parameters", {}),
                    }
                )
            payload["tools"] = [{"functionDeclarations": declarations}]

        session = self._get_aiohttp_session()
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Google API error {resp.status}: {text[:500]}")
            data = await resp.json()

        duration_ms = int((time.time() - start) * 1000)

        # Extract response text
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"No candidates in Google response: {data}")

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])

        # Check for function calls
        for part in parts:
            if "functionCall" in part:
                fc = part["functionCall"]
                return json.dumps(
                    {
                        "tool_calls": [
                            {
                                "id": fc.get("name", ""),
                                "name": fc.get("name", ""),
                                "arguments": json.dumps(fc.get("args", {})),
                            }
                        ]
                    }
                )

        text = "".join(p.get("text", "") for p in parts)

        # Extract token counts if available
        usage = data.get("usageMetadata", {})
        self._log_call(
            LLMCallLog(
                provider="google",
                model=config.model,
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                duration_ms=duration_ms,
            )
        )

        return text

    async def _google_stream(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Streaming Google Gemini completion via REST API."""
        config = self.configs[LLMProvider.GOOGLE]

        contents = []
        system_parts = []
        for m in messages:
            if m.role == "system":
                system_parts.append({"text": m.content})
            else:
                role = "user" if m.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.content}]})

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:streamGenerateContent"
            f"?alt=sse"
        )
        # SECURITY: API key sent via header instead of URL query parameter
        stream_headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "x-goog-api-key": config.api_key or "",
        }
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature or config.temperature,
                "maxOutputTokens": max_tokens or config.max_tokens,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": system_parts}

        session = self._get_aiohttp_session()
        async with session.post(url, json=payload, headers=stream_headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Google API error {resp.status}: {text[:500]}")

            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield part["text"]
                    except json.JSONDecodeError:
                        continue

    # -- Provider implementations: Ollama -----------------------------------

    async def _ollama_complete(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Non-streaming Ollama completion via local HTTP API."""
        config = self.configs[LLMProvider.OLLAMA]
        start = time.time()

        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        url = f"{config.base_url}/api/chat"
        payload = {
            "model": config.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature or config.temperature,
                "num_predict": max_tokens or config.max_tokens,
            },
        }
        if tool_schemas:
            # Ollama supports tools in newer versions
            tools = []
            for schema in tool_schemas:
                func = schema.get("function", {})
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": func.get("name", ""),
                            "description": func.get("description", ""),
                            "parameters": func.get("parameters", {}),
                        },
                    }
                )
            payload["tools"] = tools

        session = self._get_aiohttp_session()
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {text[:500]}")
            data = await resp.json()

        duration_ms = int((time.time() - start) * 1000)
        self._log_call(
            LLMCallLog(
                provider="ollama",
                model=config.model,
                duration_ms=duration_ms,
            )
        )

        # Check for tool calls in response
        message = data.get("message", {})
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            return json.dumps(
                {
                    "tool_calls": [
                        {
                            "id": tc.get("function", {}).get("name", ""),
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": json.dumps(
                                tc.get("function", {}).get("arguments", {})
                            ),
                        }
                        for tc in tool_calls
                    ]
                }
            )

        return message.get("content", "")

    async def _ollama_stream(
        self,
        messages: List[Message],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Streaming Ollama completion via local HTTP API."""
        config = self.configs[LLMProvider.OLLAMA]
        start = time.time()

        ollama_messages = [{"role": m.role, "content": m.content} for m in messages]
        url = f"{config.base_url}/api/chat"
        payload = {
            "model": config.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": temperature or config.temperature,
                "num_predict": max_tokens or config.max_tokens,
            },
        }
        if tool_schemas:
            tools = []
            for schema in tool_schemas:
                func = schema.get("function", {})
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": func.get("name", ""),
                            "description": func.get("description", ""),
                            "parameters": func.get("parameters", {}),
                        },
                    }
                )
            payload["tools"] = tools

        session = self._get_aiohttp_session()
        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Ollama error {resp.status}: {text[:500]}")

            async for line in resp.content:
                line = line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        yield content
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

        duration_ms = int((time.time() - start) * 1000)
        self._log_call(
            LLMCallLog(
                provider="ollama",
                model=config.model,
                duration_ms=duration_ms,
            )
        )

    # -- Logging ------------------------------------------------------------

    def _log_call(self, log: LLMCallLog) -> None:
        """Record an LLM call to the history log."""
        self._call_history.append(log)
        logger.info(
            "LLM call: %s/%s — %dms (prompt=%d, completion=%d)",
            log.provider,
            log.model,
            log.duration_ms,
            log.prompt_tokens,
            log.completion_tokens,
        )

    def get_call_history(self) -> List[LLMCallLog]:
        """Return the history of all LLM calls."""
        return list(self._call_history)

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics for all LLM calls."""
        if not self._call_history:
            return {"total_calls": 0}

        total = len(self._call_history)
        successful = sum(1 for c in self._call_history if c.success)
        failed = total - successful
        total_tokens = sum(c.prompt_tokens + c.completion_tokens for c in self._call_history)
        avg_duration = sum(c.duration_ms for c in self._call_history) / total

        by_provider: Dict[str, Dict[str, int]] = {}
        for c in self._call_history:
            p = c.provider
            if p not in by_provider:
                by_provider[p] = {"calls": 0, "tokens": 0, "duration_ms": 0}
            by_provider[p]["calls"] += 1
            by_provider[p]["tokens"] += c.prompt_tokens + c.completion_tokens
            by_provider[p]["duration_ms"] += c.duration_ms

        return {
            "total_calls": total,
            "successful": successful,
            "failed": failed,
            "total_tokens": total_tokens,
            "avg_duration_ms": round(avg_duration, 1),
            "by_provider": by_provider,
        }

    # -- Cleanup ------------------------------------------------------------

    async def close(self) -> None:
        """Close all open clients and sessions."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        # The openai and anthropic clients manage their own sessions
        self._clients.clear()
