"""
Query cache — LRU cache for expensive operations.

Caches ChromaDB query results and LLM completions to avoid redundant work.
All entries carry a TTL (time-to-live) so stale data is automatically evicted.
"""

import time
import hashlib
from typing import Any, Optional
from dataclasses import dataclass
from collections import OrderedDict


@dataclass
class CacheEntry:
    """Single slot in the cache."""
    value: Any
    timestamp: float
    ttl_seconds: float


class LRUCache:
    """Simple LRU cache with TTL support."""

    def __init__(self, max_size: int = 100, default_ttl: float = 300):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits: int = 0
        self._misses: int = 0

    # ------------------------------------------------------------------

    def _make_key(self, *args, **kwargs) -> str:
        """Create a deterministic cache key from arguments."""
        key_data = f"{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    # ------------------------------------------------------------------

    def get(self, *args, **kwargs) -> Optional[Any]:
        """Fetch a cached value, returning ``None`` if missing or expired."""
        key = self._make_key(*args, **kwargs)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if time.time() - entry.timestamp > entry.ttl_seconds:
            del self._cache[key]
            self._misses += 1
            return None

        self._cache.move_to_end(key)
        self._hits += 1
        return entry.value

    def set(self, value: Any, *args, ttl: Optional[float] = None, **kwargs):
        """Store *value* in the cache keyed by *args/**kwargs*."""
        key = self._make_key(*args, **kwargs)

        if len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = CacheEntry(
            value=value,
            timestamp=time.time(),
            ttl_seconds=ttl or self._default_ttl,
        )

    def clear(self):
        """Evict every entry."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """Return cache telemetry."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / max(total, 1),
        }
