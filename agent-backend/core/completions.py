"""Fast inline code completions using local LLM or cloud API.

Provides ghost-text suggestions for the Monaco editor via the
InlineCompletionsProvider API. Supports multiple backends:

1. **Groq** — ultra-fast (<200ms) cloud completions using llama-3.1-8b-instant
2. **Ollama** — local completions via the Ollama API (no API key needed)
3. **OpenAI-compatible** — any OpenAI-format endpoint

The completion prompt is carefully crafted to produce short, contextually
relevant code completions that look like natural code continuation.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CompletionResult:
    """Result from an inline completion request."""

    completion: str
    latency_ms: float
    model: str
    provider: str
    completion_id: str = ""


class InlineCompletionService:
    """Provides fast inline code completions.

    Tries providers in order: Groq → Ollama → OpenAI.
    Falls back gracefully if no provider is available.
    """

    def __init__(self) -> None:
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        self.ollama_url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
        self.groq_model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        self.openai_url = os.environ.get("OPENAI_URL", "https://api.openai.com/v1")
        self.openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        # Analytics
        self._stats = {
            "total_requests": 0,
            "successful": 0,
            "accepted": 0,
            "dismissed": 0,
            "avg_latency_ms": 0.0,
        }

    @property
    def is_available(self) -> bool:
        """Check if at least one completion provider is configured."""
        return bool(self.groq_api_key) or self._ollama_available() or bool(self.openai_api_key)

    def _ollama_available(self) -> bool:
        """Quick check if Ollama is likely reachable."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def complete(
        self,
        prefix: str,
        suffix: str,
        language: str,
        file_path: str,
        line: int = 0,
        column: int = 0,
    ) -> Optional[CompletionResult]:
        """Get an inline code completion.

        Args:
            prefix: Code before the cursor.
            suffix: Code after the cursor.
            language: Programming language ID.
            file_path: Path of the file being edited.
            line: Current line number (1-based).
            column: Current column number (1-based).

        Returns:
            A CompletionResult or None if no completion available.
        """
        self._stats["total_requests"] += 1
        start_time = time.time()

        # Build prompt
        prompt = self._build_prompt(prefix, suffix, language, file_path)

        # Try providers in order
        result = None

        # 1. Groq (fastest)
        if self.groq_api_key:
            result = await self._complete_groq(prompt, language)

        # 2. Ollama (local, no API key)
        if result is None and self._ollama_available():
            result = await self._complete_ollama(prompt, language)

        # 3. OpenAI-compatible
        if result is None and self.openai_api_key:
            result = await self._complete_openai(prompt, language)

        if result:
            latency_ms = (time.time() - start_time) * 1000
            self._stats["successful"] += 1
            self._update_avg_latency(latency_ms)

            return CompletionResult(
                completion=result.strip(),
                latency_ms=latency_ms,
                model=result.model if hasattr(result, "model") else "unknown",
                provider=result.provider if hasattr(result, "provider") else "unknown",
                completion_id=f"comp-{int(time.time() * 1000)}",
            )

        return None

    def _build_prompt(self, prefix: str, suffix: str, language: str, file_path: str) -> str:
        """Build the completion prompt.

        Uses a carefully crafted prompt that encourages short, relevant
        completions rather than full-function implementations.
        """
        # Truncate context to avoid token limits
        max_prefix = 1500
        max_suffix = 500

        if len(prefix) > max_prefix:
            prefix = prefix[-max_prefix:]
        if len(suffix) > max_suffix:
            suffix = suffix[:max_suffix]

        return f"""You are an expert {language} developer. Complete the code at the cursor position.

File: {file_path}

CODE BEFORE CURSOR:
```{language}
{prefix}
```

CODE AFTER CURSOR:
```{language}
{suffix}
```

Complete the code at the cursor. Rules:
- Output ONLY the completion text, no explanations, no markdown
- The completion should be 1-3 lines maximum
- Must be syntactically correct and contextually appropriate
- Continue the current line/thought naturally
- Do not repeat code that already exists"""

    async def _complete_groq(self, prompt: str, language: str) -> Optional[Any]:
        """Get completion from Groq API (ultra-fast, <200ms)."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_api_key}"},
                    json={
                        "model": self.groq_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 128,
                        "temperature": 0.2,
                        "stop": ["\n\n", "```", "```{language}"],
                    },
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                    class GroqResult:
                        pass

                    r = GroqResult()
                    r.strip = lambda: content.strip()
                    r.model = self.groq_model
                    r.provider = "groq"
                    return r

        except Exception as exc:
            logger.debug("Groq completion failed: %s", exc)
            return None

    async def _complete_ollama(self, prompt: str, language: str) -> Optional[Any]:
        """Get completion from local Ollama API."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": 128,
                            "temperature": 0.2,
                            "stop": ["\n\n", "```"],
                        },
                    },
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    content = data.get("response", "")

                    class OllamaResult:
                        pass

                    r = OllamaResult()
                    r.strip = lambda: content.strip()
                    r.model = self.ollama_model
                    r.provider = "ollama"
                    return r

        except Exception as exc:
            logger.debug("Ollama completion failed: %s", exc)
            return None

    async def _complete_openai(self, prompt: str, language: str) -> Optional[Any]:
        """Get completion from OpenAI-compatible API."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.openai_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.openai_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 128,
                        "temperature": 0.2,
                        "stop": ["\n\n", "```"],
                    },
                    timeout=aiohttp.ClientTimeout(total=3),
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                    class OpenAIResult:
                        pass

                    r = OpenAIResult()
                    r.strip = lambda: content.strip()
                    r.model = self.openai_model
                    r.provider = "openai"
                    return r

        except Exception as exc:
            logger.debug("OpenAI completion failed: %s", exc)
            return None

    def track_acceptance(self, completion_id: str, accepted: bool) -> None:
        """Track whether a completion was accepted or dismissed."""
        if accepted:
            self._stats["accepted"] += 1
        else:
            self._stats["dismissed"] += 1

    def _update_avg_latency(self, latency_ms: float) -> None:
        """Update rolling average latency."""
        total = self._stats["successful"]
        current_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = (
            (current_avg * (total - 1) + latency_ms) / total
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get completion service statistics."""
        return {
            **self._stats,
            "providers": {
                "groq": bool(self.groq_api_key),
                "ollama": self._ollama_available(),
                "openai": bool(self.openai_api_key),
            },
            "available": self.is_available,
        }
