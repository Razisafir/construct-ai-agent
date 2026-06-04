"""
Memory package for Construct AI Agent.

Provides semantic memory backed by ChromaDB + sentence-transformers
for vector-based similarity search.
"""

from .semantic import (
    get_chroma_client,
    get_embedding_model,
    store_embedding,
    store_conversation_message,
    store_code_event,
    query_similar,
    query_conversations,
    query_code_events,
    delete_memory,
    get_collection_stats,
    get_recent_memories,
    hybrid_search,
    MemoryEntry,
    SearchResult,
)

__all__ = [
    "get_chroma_client",
    "get_embedding_model",
    "store_embedding",
    "store_conversation_message",
    "store_code_event",
    "query_similar",
    "query_conversations",
    "query_code_events",
    "delete_memory",
    "get_collection_stats",
    "get_recent_memories",
    "hybrid_search",
    "MemoryEntry",
    "SearchResult",
]
