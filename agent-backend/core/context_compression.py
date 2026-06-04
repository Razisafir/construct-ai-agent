#!/usr/bin/env python3
"""
Context Compression — Reduce token usage by compacting conversations.

Auto-triggers when context exceeds 80% of budget.
Preserves critical facts, summarizes old messages.

Usage::

    from core.context_compression import ContextCompressor, KeyFact

    compressor = ContextCompressor()

    # Check if compaction is needed
    if compressor.should_compact(messages, max_tokens=8192):
        compressed = compressor.compact_conversation(messages, target_ratio=0.5)

    # Extract key facts
    facts = compressor.preserve_key_facts(messages)

    # Get statistics
    stats = compressor.get_context_stats(messages)

Architecture:
    - Uses LLM for summarization when available (higher quality)
    - Falls back to heuristic methods (extractive) when LLM is unavailable
    - Preserves critical facts in a structured format
    - Provides full observability via logging and statistics
"""

from __future__ import annotations

__all__ = [
    "KeyFact",
    "CompressionStrategy",
    "HeuristicCompressor",
    "LLMCompressor",
    "ContextCompressor",
    "CompressionResult",
    "CompressionStats",
]

import enum
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Tuple, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_COMPACTION_THRESHOLD = 0.80  # 80% of max_tokens triggers compaction
DEFAULT_TARGET_RATIO = 0.50  # Compress to 50% of original
DEFAULT_TOKEN_TO_WORD_RATIO = 0.75  # 1 token ≈ 0.75 words (GPT tokenizer average)
MAX_PRESERVE_MESSAGES = 3  # Always keep the N most recent messages intact
SUMMARY_MAX_WORDS = 100  # Target word count for a single summary message


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeyFact:
    """A critical fact extracted from the conversation that must be preserved.

    Attributes:
        fact: The textual fact statement (e.g. "User wants a REST API").
        importance: Relevance score from 0.0 (low) to 1.0 (critical).
        source_message_id: Index or ID of the message this fact came from.
        timestamp: ISO-8601 timestamp of when the fact was extracted.
    """

    fact: str
    importance: float = 1.0
    source_message_id: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "importance", max(0.0, min(1.0, float(self.importance)))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact": self.fact,
            "importance": self.importance,
            "source_message_id": self.source_message_id,
            "timestamp": self.timestamp,
        }


@dataclass
class CompressionResult:
    """Result of a context compression operation.

    Attributes:
        messages: The compressed list of messages.
        facts: Key facts that were preserved.
        original_token_count: Tokens before compression.
        compressed_token_count: Tokens after compression.
        strategy_used: Which compression strategy was applied.
        metadata: Additional information about the compression.
    """

    messages: List[Dict[str, Any]]
    facts: List[KeyFact]
    original_token_count: int
    compressed_token_count: int
    strategy_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def compression_ratio(self) -> float:
        """Return the achieved compression ratio (0.0–1.0)."""
        if self.original_token_count == 0:
            return 0.0
        return self.compressed_token_count / self.original_token_count

    @property
    def tokens_saved(self) -> int:
        """Return the number of tokens saved."""
        return self.original_token_count - self.compressed_token_count


@dataclass
class CompressionStats:
    """Statistics about a conversation's context.

    Attributes:
        total_tokens: Estimated total token count.
        message_count: Number of messages.
        age_range: Time span from oldest to newest message (seconds).
        avg_message_tokens: Average tokens per message.
        max_message_tokens: Largest single message token count.
        key_fact_count: Number of extracted key facts.
    """

    total_tokens: int
    message_count: int
    age_range: float
    avg_message_tokens: float
    max_message_tokens: int
    key_fact_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "message_count": self.message_count,
            "age_range_seconds": round(self.age_range, 2),
            "avg_message_tokens": round(self.avg_message_tokens, 2),
            "max_message_tokens": self.max_message_tokens,
            "key_fact_count": self.key_fact_count,
        }


# ---------------------------------------------------------------------------
# Message type helper
# ---------------------------------------------------------------------------

# A Message is a dict with at minimum a "role" and "content" key,
# plus optional metadata (timestamp, name, etc.).
Message = Dict[str, Any]


# ---------------------------------------------------------------------------
# Compression Strategies (Strategy Pattern)
# ---------------------------------------------------------------------------

class CompressionStrategy(ABC):
    """Abstract base for context compression strategies."""

    name: str = "abstract"

    @abstractmethod
    def compress(
        self,
        messages: List[Message],
        target_ratio: float,
        facts: List[KeyFact],
    ) -> List[Message]:
        """Compress *messages* toward the *target_ratio*.

        Args:
            messages: Original conversation messages.
            target_ratio: Desired ratio of output tokens to input tokens.
            facts: Key facts that must be preserved in the output.

        Returns:
            The compressed list of messages.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this strategy can be used in the current environment."""
        ...


class HeuristicCompressor(CompressionStrategy):
    """Extractive compression using heuristics — no external dependencies.

    This strategy:
    1. Always preserves the first message (system prompt / context).
    2. Always preserves the last N messages (most recent context).
    3. Summarizes the middle section by extracting key sentences.
    4. Injects preserved :class:`KeyFact` objects as a system message.
    """

    name = "heuristic"

    def __init__(
        self,
        preserve_first: bool = True,
        preserve_last: int = MAX_PRESERVE_MESSAGES,
    ) -> None:
        self.preserve_first = preserve_first
        self.preserve_last = preserve_last

    # -- Heuristic scoring for sentence importance -------------------------

    @staticmethod
    def _score_sentence(sentence: str, all_facts: List[KeyFact]) -> float:
        """Score a sentence's importance based on heuristics.

        Higher scores indicate sentences that should be kept.
        """
        score = 0.0
        lower = sentence.lower().strip()

        # 1. Fact overlap — sentences containing key fact keywords get boosted
        for fact in all_facts:
            fact_words = set(fact.fact.lower().split())
            sentence_words = set(lower.split())
            overlap = len(fact_words & sentence_words)
            if overlap > 0:
                score += overlap * 2.0 * fact.importance

        # 2. Structural indicators
        if lower.startswith(("the goal is", "the objective", "the purpose")):
            score += 3.0
        if lower.startswith(("important", "note", "warning", "critical")):
            score += 2.5
        if "decided" in lower or "agreed" in lower or "concluded" in lower:
            score += 2.0
        if "error" in lower or "exception" in lower or "failed" in lower:
            score += 1.5
        if "todo" in lower or "task" in lower or "action item" in lower:
            score += 1.5

        # 3. Content-rich signals
        if len(sentence) > 50:  # Substantive sentences
            score += 0.5
        if any(c.isdigit() for c in sentence):  # Contains numbers (often important)
            score += 0.5
        if "=" in sentence or ":" in sentence:  # Assignments or definitions
            score += 0.5

        return score

    def _extract_key_sentences(self, text: str, facts: List[KeyFact], max_sentences: int = 10) -> str:
        """Extract the most important sentences from a block of text.

        Uses a scoring function that considers fact overlap, structural
        indicators, and content signals.
        """
        # Split into sentences (simple heuristic)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if not sentences:
            return text[:500]  # Fallback: return truncated text

        scored = [
            (sentence, self._score_sentence(sentence, facts))
            for sentence in sentences
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top sentences, then re-sort by original order
        top = scored[:max_sentences]
        top.sort(key=lambda x: sentences.index(x[0]))

        return " ".join(s[0] for s in top)

    def _summarize_message(self, message: Message, facts: List[KeyFact]) -> Message:
        """Create a condensed version of a single message."""
        content = message.get("content", "")
        if not content or len(content) < 100:
            return message  # Too short to summarize

        summary = self._extract_key_sentences(content, facts, max_sentences=5)
        summarized = dict(message)
        summarized["content"] = f"[Summarized] {summary}"
        summarized["_original_length"] = len(content)
        summarized["_compressed"] = True
        return summarized

    # -- Main compress implementation ------------------------------------

    def compress(
        self,
        messages: List[Message],
        target_ratio: float,
        facts: List[KeyFact],
    ) -> List[Message]:
        """Heuristic compression: keep first, last N, summarize middle."""
        if not messages:
            return []

        total = len(messages)
        result: List[Message] = []

        # Determine which messages to preserve vs summarize
        preserve_indices: set = set()

        if self.preserve_first and total > 0:
            preserve_indices.add(0)  # System prompt / first message

        for i in range(max(0, total - self.preserve_last), total):
            preserve_indices.add(i)

        # Build fact preservation message
        if facts:
            fact_lines = [f"- {f.fact}" for f in sorted(facts, key=lambda x: x.importance, reverse=True)]
            fact_message: Message = {
                "role": "system",
                "content": f"[Preserved Facts]\n" + "\n".join(fact_lines),
                "_compressed": True,
                "_fact_summary": True,
            }
            result.append(fact_message)

        # Process each message
        for idx, msg in enumerate(messages):
            if idx in preserve_indices:
                result.append(msg)
            else:
                summarized = self._summarize_message(msg, facts)
                result.append(summarized)

        logger.info(
            "HeuristicCompressor: %d → %d messages (preserved %d, summarized %d)",
            total, len(result), len(preserve_indices), total - len(preserve_indices),
        )
        return result

    def is_available(self) -> bool:
        """Heuristic compressor is always available (no external deps)."""
        return True


class LLMCompressor(CompressionStrategy):
    """LLM-based compression that uses a language model to generate summaries.

    This strategy produces higher-quality summaries but requires an LLM
    client to be available. Falls back to heuristic if the LLM call fails.
    """

    name = "llm"

    def __init__(
        self,
        summarize_fn: Optional[Callable[[str], str]] = None,
        fallback: Optional[CompressionStrategy] = None,
    ) -> None:
        """Initialize with an optional summarization function.

        Args:
            summarize_fn: A callable that takes a string and returns a
                summarized string. If not provided, the compressor will
                check for common LLM client patterns.
            fallback: Strategy to use if the LLM is unavailable.
        """
        self._summarize_fn = summarize_fn
        self._fallback = fallback or HeuristicCompressor()

    def _get_summarize_fn(self) -> Optional[Callable[[str], str]]:
        """Resolve the summarization function.

        If explicitly provided, use that. Otherwise try to detect
        common LLM client libraries.
        """
        if self._summarize_fn is not None:
            return self._summarize_fn

        # Try OpenAI
        try:
            import openai
            client = openai.OpenAI()

            def _openai_summarize(text: str) -> str:
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Summarize the following conversation excerpt "
                                "concisely while preserving all critical facts, "
                                "decisions, action items, and error messages. "
                                f"Maximum {SUMMARY_MAX_WORDS} words."
                            ),
                        },
                        {"role": "user", "content": text[:4000]},  # Token limit safety
                    ],
                    temperature=0.3,
                    max_tokens=200,
                )
                return resp.choices[0].message.content or text[:500]

            return _openai_summarize
        except ImportError:
            pass

        # Try Anthropic
        try:
            import anthropic
            client = anthropic.Anthropic()

            def _anthropic_summarize(text: str) -> str:
                resp = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=200,
                    system=(
                        "Summarize conversation excerpts concisely. "
                        "Preserve critical facts, decisions, and action items."
                    ),
                    messages=[{"role": "user", "content": text[:4000]}],
                )
                return resp.content[0].text if resp.content else text[:500]

            return _anthropic_summarize
        except ImportError:
            pass

        return None

    def compress(
        self,
        messages: List[Message],
        target_ratio: float,
        facts: List[KeyFact],
    ) -> List[Message]:
        """LLM-based compression with fallback to heuristic."""
        summarize_fn = self._get_summarize_fn()

        if summarize_fn is None:
            logger.info("LLM not available, falling back to heuristic compression")
            return self._fallback.compress(messages, target_ratio, facts)

        if not messages:
            return []

        total = len(messages)
        preserve_indices: set = set()
        preserve_indices.add(0)  # Keep first message
        for i in range(max(0, total - MAX_PRESERVE_MESSAGES), total):
            preserve_indices.add(i)

        result: List[Message] = []

        # Add fact summary
        if facts:
            fact_lines = [f"- {f.fact}" for f in sorted(facts, key=lambda x: x.importance, reverse=True)]
            result.append({
                "role": "system",
                "content": "[Preserved Facts]\n" + "\n".join(fact_lines),
                "_compressed": True,
                "_fact_summary": True,
            })

        # Group middle messages for batch summarization
        middle_messages = [(i, m) for i, m in enumerate(messages) if i not in preserve_indices]

        if middle_messages:
            # Combine middle messages for LLM summarization
            combined_text = "\n\n".join(
                f"[{m.get('role', 'unknown')}] {m.get('content', '')}"[:500]
                for _, m in middle_messages
            )

            try:
                summary = summarize_fn(combined_text)
                result.append({
                    "role": "system",
                    "content": f"[Conversation Summary]\n{summary}",
                    "_compressed": True,
                    "_llm_summary": True,
                })
            except Exception as exc:
                logger.warning("LLM summarization failed: %s. Falling back to heuristic.", exc)
                return self._fallback.compress(messages, target_ratio, facts)
        
        # Add preserved messages
        for idx in sorted(preserve_indices):
            result.append(messages[idx])

        logger.info(
            "LLMCompressor: %d → %d messages (LLM summarized %d middle messages)",
            total, len(result), len(middle_messages),
        )
        return result

    def is_available(self) -> bool:
        """Check if an LLM client is available."""
        return self._get_summarize_fn() is not None


# ---------------------------------------------------------------------------
# Main ContextCompressor
# ---------------------------------------------------------------------------

class ContextCompressor:
    """Orchestrates context compression with automatic strategy selection.

    This is the primary interface for context compression. It:
    1. Estimates token counts from message text.
    2. Decides when compaction is needed.
    3. Extracts key facts that must survive compression.
    4. Applies the best available compression strategy.
    5. Provides full statistics and observability.

    Example::

        compressor = ContextCompressor()

        # Simple: compress if needed
        if compressor.should_compact(messages, max_tokens=8192):
            result = compressor.compact_conversation(messages, target_ratio=0.5)
            messages = result.messages

        # Advanced: with custom LLM
        def my_llm(text: str) -> str:
            return my_model.summarize(text)

        compressor = ContextCompressor(llm_summarize_fn=my_llm)
        result = compressor.compact_conversation(messages)

        # Inspect results
        print(f"Saved {result.tokens_saved} tokens ({result.compression_ratio:.0%} of original)")
        for fact in result.facts:
            print(f"  Fact: {fact.fact} (importance: {fact.importance})")
    """

    def __init__(
        self,
        llm_summarize_fn: Optional[Callable[[str], str]] = None,
        compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD,
    ) -> None:
        """Initialize the compressor.

        Args:
            llm_summarize_fn: Optional custom LLM summarization function.
                If provided, LLM-based compression will be attempted first.
            compaction_threshold: Fraction of max_tokens that triggers
                compaction (default: 0.80).
        """
        self._compaction_threshold = compaction_threshold

        # Initialize strategies
        self._heuristic = HeuristicCompressor()
        self._llm = LLMCompressor(summarize_fn=llm_summarize_fn, fallback=self._heuristic)

        # Stats tracking
        self._compression_history: List[Dict[str, Any]] = []

    # -- Token estimation --------------------------------------------------

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximate token count from text.

        Uses the heuristic that 1 token ≈ 0.75 words for GPT-style tokenizers.
        This is a fast approximation suitable for triggering compaction.
        For precise counts, use ``tiktoken``.

        Args:
            text: Input text to estimate.

        Returns:
            Estimated integer token count (minimum 1).
        """
        if not text:
            return 0

        # Split on whitespace to count words
        words = len(text.split())

        # Add overhead for punctuation, special characters, code
        code_overhead = text.count("{") + text.count("}") + text.count("(") + text.count(")")
        code_overhead += text.count("[") + text.count("]") + text.count(";") + text.count(",")

        # Each "word" of code-ish tokens counts as more
        estimated_tokens = int((words + code_overhead * 0.5) / DEFAULT_TOKEN_TO_WORD_RATIO)

        return max(1, estimated_tokens)

    # -- Decision making ---------------------------------------------------

    def should_compact(self, messages: List[Message], max_tokens: int) -> bool:
        """Check if the conversation exceeds the compaction threshold.

        Args:
            messages: Current conversation messages.
            max_tokens: Maximum allowed tokens for the context window.

        Returns:
            ``True`` if compaction should be performed.
        """
        if not messages or max_tokens <= 0:
            return False

        total_tokens = sum(
            self.estimate_tokens(m.get("content", "")) for m in messages
        )
        threshold_tokens = int(max_tokens * self._compaction_threshold)

        should_compact = total_tokens >= threshold_tokens

        if should_compact:
            logger.info(
                "Context compaction triggered: %d/%d tokens (%.1f%% >= %.0f%% threshold)",
                total_tokens, max_tokens, total_tokens / max_tokens * 100,
                self._compaction_threshold * 100,
            )
        else:
            logger.debug(
                "No compaction needed: %d/%d tokens (%.1f%% < %.0f%% threshold)",
                total_tokens, max_tokens, total_tokens / max_tokens * 100,
                self._compaction_threshold * 100,
            )

        return should_compact

    # -- Fact extraction ---------------------------------------------------

    def preserve_key_facts(self, messages: List[Message]) -> List[KeyFact]:
        """Extract critical facts that must be preserved during compression.

        Uses heuristics to identify important information from the
        conversation, such as decisions, requirements, constraints, and
        error states.

        Args:
            messages: Conversation messages to analyze.

        Returns:
            A list of :class:`KeyFact` objects sorted by importance.
        """
        facts: List[KeyFact] = []

        # Keywords that indicate important facts
        importance_patterns = [
            (r"\b(decided|decision|agreed|concluded)\b", 0.9),
            (r"\b(requirement|must|need to|has to)\b", 0.85),
            (r"\b(constraint|limitation|cannot|must not)\b", 0.8),
            (r"\b(error|exception|failed|bug|issue)\b", 0.75),
            (r"\b(action item|todo|task|follow.up)\b", 0.7),
            (r"\b(important|critical|note that|remember)\b", 0.65),
            (r"\b(user wants|goal is|objective|purpose)\b", 0.6),
            (r"\b(using|tech stack|framework|library)\b", 0.55),
        ]

        for msg_idx, message in enumerate(messages):
            content = message.get("content", "")
            role = message.get("role", "")

            # Split into sentences for granular analysis
            sentences = re.split(r'(?<=[.!?])\s+', content)

            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 15:
                    continue

                lower = sentence.lower()
                for pattern, base_importance in importance_patterns:
                    if re.search(pattern, lower):
                        # Adjust importance based on role
                        role_multiplier = 1.0
                        if role == "system":
                            role_multiplier = 1.1
                        elif role == "assistant" and "error" in lower:
                            role_multiplier = 1.2

                        importance = min(1.0, base_importance * role_multiplier)

                        # Truncate very long facts
                        fact_text = sentence[:200] + "..." if len(sentence) > 200 else sentence

                        facts.append(KeyFact(
                            fact=fact_text,
                            importance=importance,
                            source_message_id=msg_idx,
                        ))
                        break  # One fact per sentence

        # Remove near-duplicates (simple string containment check)
        deduped: List[KeyFact] = []
        for fact in sorted(facts, key=lambda f: f.importance, reverse=True):
            is_duplicate = any(
                fact.fact.lower() in existing.fact.lower()
                or existing.fact.lower() in fact.fact.lower()
                for existing in deduped
            )
            if not is_duplicate:
                deduped.append(fact)

        # Cap at reasonable number
        MAX_FACTS = 20
        result = deduped[:MAX_FACTS]

        logger.info("Extracted %d key facts from %d messages", len(result), len(messages))
        return result

    # -- Main compaction API -----------------------------------------------

    def compact_conversation(
        self,
        messages: List[Message],
        target_ratio: float = DEFAULT_TARGET_RATIO,
    ) -> CompressionResult:
        """Compact a conversation by summarizing older messages.

        This is the primary entry point for context compression. It:
        1. Extracts key facts from the conversation.
        2. Selects the best available compression strategy.
        3. Applies compression to reach the target ratio.
        4. Returns the result with full metadata.

        Args:
            messages: Current conversation messages.
            target_ratio: Target ratio of output to input tokens
                (default: 0.5, meaning compress to 50%).

        Returns:
            A :class:`CompressionResult` with compressed messages and metadata.
        """
        if not messages:
            return CompressionResult(
                messages=[], facts=[], original_token_count=0,
                compressed_token_count=0, strategy_used="none",
            )

        start_time = time.monotonic()
        original_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in messages)

        # Extract facts first
        facts = self.preserve_key_facts(messages)

        # Select best available strategy
        if self._llm.is_available():
            strategy: CompressionStrategy = self._llm
        else:
            strategy = self._heuristic

        logger.info(
            "Compacting %d messages (~%d tokens) using %s strategy, target_ratio=%.2f",
            len(messages), original_tokens, strategy.name, target_ratio,
        )

        # Apply compression
        compressed = strategy.compress(messages, target_ratio, facts)

        # Post-process: if still too large, apply age-based removal
        compressed_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in compressed)
        if compressed_tokens > original_tokens * target_ratio * 1.1:
            logger.info(
                "Compression insufficient (%d tokens > target %d), "
                "applying age-based removal",
                compressed_tokens, int(original_tokens * target_ratio),
            )
            compressed = self.compact_by_age(
                compressed,
                max_tokens=int(original_tokens * target_ratio),
            )
            compressed_tokens = sum(
                self.estimate_tokens(m.get("content", "")) for m in compressed
            )

        elapsed = time.monotonic() - start_time

        result = CompressionResult(
            messages=compressed,
            facts=facts,
            original_token_count=original_tokens,
            compressed_token_count=compressed_tokens,
            strategy_used=strategy.name,
            metadata={
                "target_ratio": target_ratio,
                "actual_ratio": compressed_tokens / original_tokens if original_tokens else 0,
                "elapsed_seconds": round(elapsed, 3),
                "facts_extracted": len(facts),
            },
        )

        self._compression_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "strategy": strategy.name,
            "message_count_before": len(messages),
            "message_count_after": len(compressed),
        })

        logger.info(
            "Compression complete: %d → %d tokens (%.1f%%) using %s in %.3fs",
            original_tokens, compressed_tokens,
            result.compression_ratio * 100, strategy.name, elapsed,
        )

        return result

    # -- Age-based compaction fallback -------------------------------------

    def compact_by_age(
        self,
        messages: List[Message],
        max_tokens: int,
    ) -> List[Message]:
        """Remove oldest messages first until under the token budget.

        This is a last-resort compaction strategy that preserves the most
        recent messages while dropping older ones. Key facts are retained
        via an injected summary message.

        Args:
            messages: Messages to compact.
            max_tokens: Maximum allowed tokens.

        Returns:
            Messages that fit within the token budget.
        """
        if not messages:
            return []

        total = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        if total <= max_tokens:
            return messages

        # Always keep system message and last N messages
        keep_system = []
        middle = []
        tail = []

        if messages and messages[0].get("role") == "system":
            keep_system = [messages[0]]
            messages = messages[1:]

        tail_count = min(MAX_PRESERVE_MESSAGES, len(messages))
        tail = messages[-tail_count:]
        middle = messages[:-tail_count]

        # Extract key facts from middle messages being removed
        facts = self.preserve_key_facts(middle)

        # Build result starting with system + fact summary + tail
        result = list(keep_system)

        if facts:
            fact_lines = [f"- {f.fact}" for f in sorted(facts, key=lambda x: x.importance, reverse=True)[:10]]
            result.append({
                "role": "system",
                "content": f"[Earlier conversation facts]\n" + "\n".join(fact_lines),
                "_compressed": True,
                "_age_based": True,
            })

        result.extend(tail)

        # Verify we're under budget
        result_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in result)
        if result_tokens > max_tokens and len(tail) > 1:
            # Even tail is too large — trim oldest from tail
            while len(tail) > 1:
                tail = tail[1:]
                result = list(keep_system)
                if facts:
                    result.append({
                        "role": "system",
                        "content": f"[Earlier conversation facts]\n" + "\n".join(fact_lines[:5]),
                        "_compressed": True,
                        "_age_based": True,
                    })
                result.extend(tail)
                result_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in result)
                if result_tokens <= max_tokens:
                    break

        logger.info(
            "Age-based compaction: kept %d of %d messages (%d system, %d facts, %d recent)",
            len(result), len(messages) + len(keep_system), len(keep_system),
            1 if facts else 0, len(tail),
        )
        return result

    # -- Statistics --------------------------------------------------------

    def get_context_stats(self, messages: List[Message]) -> CompressionStats:
        """Compute statistics about the current conversation context.

        Args:
            messages: Conversation messages to analyze.

        Returns:
            A :class:`CompressionStats` object with detailed metrics.
        """
        if not messages:
            return CompressionStats(
                total_tokens=0, message_count=0, age_range=0.0,
                avg_message_tokens=0.0, max_message_tokens=0,
            )

        token_counts = [self.estimate_tokens(m.get("content", "")) for m in messages]
        total_tokens = sum(token_counts)

        # Compute age range from message timestamps if available
        timestamps: List[float] = []
        for m in messages:
            ts = m.get("timestamp")
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        timestamps.append(float(ts))
                except (ValueError, TypeError):
                    pass

        if len(timestamps) >= 2:
            age_range = max(timestamps) - min(timestamps)
        else:
            age_range = 0.0

        # Extract fact count
        facts = self.preserve_key_facts(messages)

        return CompressionStats(
            total_tokens=total_tokens,
            message_count=len(messages),
            age_range=age_range,
            avg_message_tokens=total_tokens / len(messages) if messages else 0.0,
            max_message_tokens=max(token_counts) if token_counts else 0,
            key_fact_count=len(facts),
        )

    def get_compression_history(self) -> List[Dict[str, Any]]:
        """Return the history of all compression operations performed.

        Returns:
            List of dictionaries with metadata about each compression.
        """
        return list(self._compression_history)

    def clear_history(self) -> None:
        """Clear the compression history."""
        self._compression_history.clear()

    # -- Diagnostics -------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Run a diagnostic check on the compression system.

        Returns:
            Dictionary with availability status and configuration.
        """
        return {
            "heuristic_available": self._heuristic.is_available(),
            "llm_available": self._llm.is_available(),
            "compaction_threshold": self._compaction_threshold,
            "default_target_ratio": DEFAULT_TARGET_RATIO,
            "token_to_word_ratio": DEFAULT_TOKEN_TO_WORD_RATIO,
            "compression_history_count": len(self._compression_history),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
