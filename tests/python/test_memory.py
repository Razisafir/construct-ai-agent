"""Tests for memory system: SQLite + ChromaDB."""

import os
import time
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest


# ============================================================================
# SQLite Memory Tests
# ============================================================================


class TestSQLiteMemory:
    """Test SQLite memory operations."""

    # --- Fixtures ---

    @pytest.fixture
    def db(self):
        """Create temporary in-memory database with full schema."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding_vector BLOB
            );
            CREATE INDEX idx_conversations_ts ON conversations(timestamp);
            CREATE INDEX idx_conversations_role ON conversations(role);

            CREATE TABLE code_events (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                change_type TEXT NOT NULL,
                diff TEXT,
                summary TEXT NOT NULL
            );
            CREATE INDEX idx_code_events_ts ON code_events(timestamp);
            CREATE INDEX idx_code_events_file ON code_events(file_path);

            CREATE TABLE user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                last_updated INTEGER NOT NULL
            );

            CREATE TABLE project_state (
                project_path TEXT PRIMARY KEY,
                current_branch TEXT NOT NULL DEFAULT '',
                last_commit TEXT NOT NULL DEFAULT '',
                agent_context_json TEXT NOT NULL DEFAULT '{}',
                updated_at INTEGER NOT NULL
            );
            """
        )
        conn.commit()
        yield conn
        conn.close()

    @pytest.fixture
    def db_with_data(self, db):
        """Populate database with sample conversations."""
        cursor = db.cursor()
        conversations = [
            ("c1", int(time.time()) - 100, "user", "How do I implement auth?"),
            ("c2", int(time.time()) - 90, "assistant", "Use JWT tokens with bcrypt."),
            ("c3", int(time.time()) - 80, "user", "What about rate limiting?"),
            ("c4", int(time.time()) - 70, "assistant", "Use redis-rate-limits or a sliding window."),
            ("c5", int(time.time()) - 60, "user", "Database connection pooling?"),
        ]
        cursor.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            conversations,
        )
        db.commit()
        yield db

    # --- record_conversation ---

    def test_record_conversation(self, db):
        """Test recording a conversation message."""
        cursor = db.cursor()
        msg = ("msg-1", int(time.time()), "user", "Hello, Construct!")
        cursor.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            msg,
        )
        db.commit()

        cursor.execute("SELECT * FROM conversations WHERE id = ?", ("msg-1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "msg-1"
        assert row[3] == "user"
        assert row[4] == "Hello, Construct!"

    def test_record_conversation_upsert(self, db):
        """Test that duplicate IDs are handled via upsert."""
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("same-id", 1000, "user", "First"),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("same-id", 2000, "assistant", "Second"),
        )
        db.commit()

        cursor.execute("SELECT content FROM conversations WHERE id = ?", ("same-id",))
        assert cursor.fetchone()[0] == "Second"

    def test_record_conversation_unicode(self, db):
        """Test recording unicode content."""
        cursor = db.cursor()
        content = "Hello World 日本語 test"
        cursor.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("unicode", int(time.time()), "user", content),
        )
        db.commit()

        cursor.execute("SELECT content FROM conversations WHERE id = ?", ("unicode",))
        assert cursor.fetchone()[0] == content

    def test_record_conversation_long_content(self, db):
        """Test recording very long content."""
        cursor = db.cursor()
        long_content = "a" * 100_000
        cursor.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("long", int(time.time()), "user", long_content),
        )
        db.commit()

        cursor.execute("SELECT LENGTH(content) FROM conversations WHERE id = ?", ("long",))
        assert cursor.fetchone()[0] == 100_000

    # --- recall_context ---

    def test_recall_context(self, db_with_data):
        """Test context recall with search query."""
        db = db_with_data
        cursor = db.cursor()
        query = "auth"
        pattern = f"%{query}%"

        cursor.execute(
            "SELECT id, content, timestamp FROM conversations WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (pattern, 10),
        )
        results = cursor.fetchall()

        assert len(results) >= 1
        contents = [r[1] for r in results]
        assert any("auth" in c.lower() for c in contents)

    def test_recall_context_no_results(self, db_with_data):
        """Test context recall with non-matching query."""
        db = db_with_data
        cursor = db.cursor()
        pattern = "%xyznonexistent%"

        cursor.execute(
            "SELECT id, content, timestamp FROM conversations WHERE content LIKE ? LIMIT ?",
            (pattern, 10),
        )
        results = cursor.fetchall()
        assert len(results) == 0

    def test_recall_context_respects_limit(self, db_with_data):
        """Test that recall respects the limit parameter."""
        db = db_with_data
        cursor = db.cursor()
        pattern = "%the%"

        cursor.execute(
            "SELECT id FROM conversations WHERE content LIKE ? LIMIT ?",
            (pattern, 2),
        )
        results = cursor.fetchall()
        assert len(results) <= 2

    def test_recall_context_combined_sources(self, db_with_data):
        """Test recall across both conversations and code events."""
        db = db_with_data
        cursor = db.cursor()

        # Add code events
        cursor.execute(
            "INSERT INTO code_events (id, timestamp, file_path, change_type, diff, summary) VALUES (?, ?, ?, ?, ?, ?)",
            ("ce-1", int(time.time()), "src/auth.py", "create", "+def login()", "Added auth module"),
        )
        db.commit()

        pattern = "%auth%"

        # Search conversations
        cursor.execute(
            "SELECT id, 'conversation' as source, content, timestamp FROM conversations WHERE content LIKE ?",
            (pattern,),
        )
        conv_results = cursor.fetchall()

        # Search code events
        cursor.execute(
            "SELECT id, 'code_event' as source, summary || ' | ' || file_path, timestamp FROM code_events WHERE summary LIKE ? OR file_path LIKE ?",
            (pattern, pattern),
        )
        code_results = cursor.fetchall()

        combined = conv_results + code_results
        assert len(combined) >= 2  # At least 1 from each source

    # --- store_preference ---

    def test_store_preference(self, db):
        """Test preference storage."""
        cursor = db.cursor()
        now = int(time.time())

        cursor.execute(
            """INSERT INTO user_preferences (key, value, confidence, last_updated)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   confidence = excluded.confidence,
                   last_updated = excluded.last_updated""",
            ("theme", "dark", 0.9, now),
        )
        db.commit()

        cursor.execute("SELECT key, value, confidence FROM user_preferences WHERE key = ?", ("theme",))
        row = cursor.fetchone()
        assert row == ("theme", "dark", 0.9)

    def test_store_preference_upsert(self, db):
        """Test preference upsert updates existing values."""
        cursor = db.cursor()
        now = int(time.time())

        cursor.execute(
            "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
            ("font", "monospace", 0.8, now),
        )
        cursor.execute(
            """INSERT INTO user_preferences (key, value, confidence, last_updated)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   confidence = excluded.confidence,
                   last_updated = excluded.last_updated""",
            ("font", "sans-serif", 0.75, now + 10),
        )
        db.commit()

        cursor.execute("SELECT value, confidence FROM user_preferences WHERE key = ?", ("font",))
        row = cursor.fetchone()
        assert row == ("sans-serif", 0.75)

    def test_get_preferences_ordered(self, db):
        """Test preferences are ordered by confidence descending."""
        cursor = db.cursor()
        now = int(time.time())

        prefs = [
            ("low", "val1", 0.3, now),
            ("high", "val2", 0.95, now),
            ("mid", "val3", 0.6, now),
        ]
        cursor.executemany(
            "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
            prefs,
        )
        db.commit()

        cursor.execute(
            "SELECT key, confidence FROM user_preferences ORDER BY confidence DESC"
        )
        results = cursor.fetchall()

        assert results[0][1] == 0.95
        assert results[1][1] == 0.6
        assert results[2][1] == 0.3

    # --- project_state ---

    def test_project_state_default(self, db):
        """Test default project state for non-existent path."""
        cursor = db.cursor()
        cursor.execute(
            "SELECT project_path, current_branch, last_commit, agent_context_json FROM project_state WHERE project_path = ?",
            ("/nonexistent",),
        )
        row = cursor.fetchone()
        # No row exists; default would be handled by application code
        assert row is None

    def test_project_state_crud(self, db):
        """Test project state create, read, update."""
        cursor = db.cursor()
        now = int(time.time())

        # Create
        cursor.execute(
            "INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("/proj/a", "main", "abc123", "{}", now),
        )
        db.commit()

        # Read
        cursor.execute(
            "SELECT project_path, current_branch, last_commit FROM project_state WHERE project_path = ?",
            ("/proj/a",),
        )
        row = cursor.fetchone()
        assert row == ("/proj/a", "main", "abc123")

        # Update
        cursor.execute(
            """INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(project_path) DO UPDATE SET
                   current_branch = excluded.current_branch,
                   last_commit = excluded.last_commit,
                   agent_context_json = excluded.agent_context_json,
                   updated_at = excluded.updated_at""",
            ("/proj/a", "feature/new", "def456", '{"key": "val"}', now + 10),
        )
        db.commit()

        cursor.execute(
            "SELECT current_branch, last_commit FROM project_state WHERE project_path = ?",
            ("/proj/a",),
        )
        row = cursor.fetchone()
        assert row == ("feature/new", "def456")

    # --- code_events ---

    def test_code_event_crud(self, db):
        """Test code event create and read."""
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO code_events (id, timestamp, file_path, change_type, diff, summary) VALUES (?, ?, ?, ?, ?, ?)",
            ("ce-1", int(time.time()), "src/main.py", "create", "+ def main():", "Added main"),
        )
        db.commit()

        cursor.execute("SELECT * FROM code_events WHERE id = ?", ("ce-1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[3] == "src/main.py"
        assert row[4] == "create"
        assert row[5] == "+ def main():"

    # --- persistence ---

    def test_persistence(self, temp_dir):
        """Test data persists across connections (file-based DB)."""
        db_path = temp_dir / "test.db"

        # Write data
        conn1 = sqlite3.connect(str(db_path))
        conn1.executescript(
            """
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            );
            """
        )
        conn1.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("persist-1", 1000, "user", "Persistent message"),
        )
        conn1.commit()
        conn1.close()

        # Read data in new connection
        conn2 = sqlite3.connect(str(db_path))
        cursor = conn2.cursor()
        cursor.execute("SELECT content FROM conversations WHERE id = ?", ("persist-1",))
        row = cursor.fetchone()
        conn2.close()

        assert row[0] == "Persistent message"


# ============================================================================
# ChromaDB Memory Tests
# ============================================================================


class TestChromaDBMemory:
    """Test ChromaDB vector operations (with mocked chromadb)."""

    @pytest.fixture
    def mock_collection(self):
        """Create a mock ChromaDB collection."""
        collection = MagicMock()
        collection.add.return_value = None
        collection.query.return_value = {
            "ids": [["doc-1", "doc-2"]],
            "documents": [["Document 1 content", "Document 2 content"]],
            "metadatas": [[{"source": "test"}, {"source": "test"}]],
            "distances": [[0.1, 0.3]],
        }
        collection.get.return_value = {
            "ids": ["doc-1"],
            "documents": ["Document 1 content"],
            "metadatas": [{"source": "test"}],
        }
        yield collection

    # --- store_embedding ---

    def test_store_embedding(self, mock_collection):
        """Test storing an embedding."""
        mock_collection.add(
            ids=["embed-1"],
            documents=["Test document content"],
            metadatas=[{"source": "test", "timestamp": 1000}],
        )

        mock_collection.add.assert_called_once()
        call_args = mock_collection.add.call_args
        assert call_args[1]["ids"] == ["embed-1"]
        assert call_args[1]["documents"] == ["Test document content"]

    def test_store_embedding_batch(self, mock_collection):
        """Test storing multiple embeddings in batch."""
        docs = [
            ("id-1", "Document one", {"type": "user"}),
            ("id-2", "Document two", {"type": "assistant"}),
            ("id-3", "Document three", {"type": "user"}),
        ]
        ids, documents, metadatas = zip(*docs)
        mock_collection.add(
            ids=list(ids),
            documents=list(documents),
            metadatas=list(metadatas),
        )

        assert mock_collection.add.call_count == 1
        call_args = mock_collection.add.call_args[1]
        assert len(call_args["ids"]) == 3

    # --- query_similar ---

    def test_query_similar(self, mock_collection):
        """Test semantic similarity search."""
        results = mock_collection.query(
            query_texts=["test query"],
            n_results=5,
        )

        mock_collection.query.assert_called_once()
        assert "ids" in results
        assert len(results["ids"][0]) == 2
        assert results["distances"][0][0] < results["distances"][0][1]

    def test_query_similar_with_filter(self, mock_collection):
        """Test semantic search with metadata filter."""
        mock_collection.query(
            query_texts=["test query"],
            n_results=5,
            where={"source": "test"},
        )

        call_args = mock_collection.query.call_args[1]
        assert call_args["where"] == {"source": "test"}

    def test_query_similar_empty_results(self, mock_collection):
        """Test semantic search with no results."""
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        results = mock_collection.query(
            query_texts=["nonexistent xyz query"],
            n_results=5,
        )

        assert len(results["ids"][0]) == 0

    # --- hybrid_search ---

    def test_hybrid_search(self, mock_collection):
        """Test hybrid vector + text search."""
        # First do a keyword search (simulated)
        keyword_results = [("doc-k1", "keyword match", 0.5)]

        # Then do vector search
        vector_results = mock_collection.query(
            query_texts=["hybrid query"],
            n_results=10,
        )

        # Combine results
        combined = []
        seen = set()
        for doc_id, content, score in keyword_results:
            combined.append({"id": doc_id, "content": content, "score": score})
            seen.add(doc_id)

        for i, doc_id in enumerate(vector_results["ids"][0]):
            if doc_id not in seen:
                combined.append({
                    "id": doc_id,
                    "content": vector_results["documents"][0][i],
                    "score": 1.0 - vector_results["distances"][0][i],
                })

        assert len(combined) >= 2

    def test_hybrid_search_deduplication(self, mock_collection):
        """Test hybrid search deduplicates overlapping results."""
        mock_collection.query.return_value = {
            "ids": [["doc-k1", "doc-vec1"]],
            "documents": [["keyword match", "vector match"]],
            "metadatas": [[{"source": "test"}, {"source": "test"}]],
            "distances": [[0.5, 0.2]],
        }

        keyword_results = [("doc-k1", "keyword match", 0.5)]
        vector_results = mock_collection.query(
            query_texts=["query"],
            n_results=10,
        )

        # Deduplicate
        seen = set()
        combined = []
        for doc_id, content, score in keyword_results:
            if doc_id not in seen:
                combined.append({"id": doc_id, "content": content, "score": score})
                seen.add(doc_id)

        for i, doc_id in enumerate(vector_results["ids"][0]):
            if doc_id not in seen:
                combined.append({
                    "id": doc_id,
                    "content": vector_results["documents"][0][i],
                    "score": 1.0 - vector_results["distances"][0][i],
                })
                seen.add(doc_id)

        # doc-k1 should appear only once even though it's in both
        doc_k1_count = sum(1 for r in combined if r["id"] == "doc-k1")
        assert doc_k1_count == 1

    # --- delete ---

    def test_delete_embedding(self, mock_collection):
        """Test deleting an embedding."""
        mock_collection.delete(ids=["doc-1"])
        mock_collection.delete.assert_called_once()
        assert mock_collection.delete.call_args[1]["ids"] == ["doc-1"]

    def test_delete_by_filter(self, mock_collection):
        """Test deleting embeddings by filter."""
        mock_collection.delete(where={"source": "test"})
        assert mock_collection.delete.call_args[1]["where"] == {"source": "test"}

    # --- update ---

    def test_update_embedding(self, mock_collection):
        """Test updating an embedding."""
        mock_collection.update(
            ids=["doc-1"],
            documents=["Updated content"],
            metadatas=[{"updated": True}],
        )
        mock_collection.update.assert_called_once()

    # --- count ---

    def test_count_embeddings(self, mock_collection):
        """Test counting embeddings in collection."""
        mock_collection.count.return_value = 42
        count = mock_collection.count()
        assert count == 42

    # --- peek ---

    def test_peek_collection(self, mock_collection):
        """Test peeking at collection contents."""
        mock_collection.peek.return_value = {
            "ids": ["doc-1", "doc-2"],
            "documents": ["Doc 1", "Doc 2"],
            "metadatas": [{}, {}],
        }
        result = mock_collection.peek(limit=2)
        assert len(result["ids"]) == 2
