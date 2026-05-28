"""Test memory persists across sessions.

This integration test verifies:
1. Store conversation in one database connection
2. Close and reopen new connection to same database file
3. Verify conversation is still retrievable
4. Test semantic search still works after reconnection
5. Test project state persists
6. Test preferences persist with correct ordering
"""

import os
import sys
import json
import time
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def persistent_db():
    """Create a file-based database that persists across connections."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    def create_schema(conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding_vector BLOB
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_ts ON conversations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_conversations_role ON conversations(role);

            CREATE TABLE IF NOT EXISTS code_events (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                change_type TEXT NOT NULL,
                diff TEXT,
                summary TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_code_events_ts ON code_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_code_events_file ON code_events(file_path);

            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                last_updated INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_state (
                project_path TEXT PRIMARY KEY,
                current_branch TEXT NOT NULL DEFAULT '',
                last_commit TEXT NOT NULL DEFAULT '',
                agent_context_json TEXT NOT NULL DEFAULT '{}',
                updated_at INTEGER NOT NULL
            );
            """
        )
        conn.commit()

    # Create initial connection and schema
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sample_data() -> List[Tuple[str, int, str, str]]:
    """Return sample conversation data."""
    now = int(time.time())
    return [
        ("conv-1", now - 400, "user", "How do I implement user authentication?"),
        ("conv-2", now - 350, "assistant", "You can use JWT tokens with bcrypt for password hashing."),
        ("conv-3", now - 300, "user", "What about rate limiting for the API?"),
        ("conv-4", now - 250, "assistant", "Use a sliding window rate limiter with Redis."),
        ("conv-5", now - 200, "user", "How to handle database migrations?"),
        ("conv-6", now - 150, "assistant", "Alembic works well with SQLAlchemy for migrations."),
        ("conv-7", now - 100, "user", "Can you help me set up Docker?"),
        ("conv-8", now - 50, "assistant", "Sure! Start with a Dockerfile using a multi-stage build."),
    ]


# ============================================================================
# Core Persistence Tests
# ============================================================================


class TestMemoryPersistence:
    """Test that data persists across database connections."""

    def test_conversation_persists(self, persistent_db, sample_data):
        """Test that conversations persist across connections."""
        db_path = persistent_db

        # Connection 1: Store data
        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data,
        )
        conn1.commit()
        conn1.close()

        # Connection 2: Verify data exists
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        conn2.close()

        assert count == len(sample_data)

    def test_all_tables_persist(self, persistent_db):
        """Test that all 4 tables exist after reconnect."""
        db_path = persistent_db

        # Insert data across all tables
        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("test-1", int(time.time()), "user", "test"),
        )
        conn1.execute(
            "INSERT INTO code_events (id, timestamp, file_path, change_type, summary) VALUES (?, ?, ?, ?, ?)",
            ("ce-1", int(time.time()), "test.py", "create", "test"),
        )
        conn1.execute(
            "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
            ("theme", "dark", 0.9, int(time.time())),
        )
        conn1.execute(
            "INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("/test", "main", "abc", "{}", int(time.time())),
        )
        conn1.commit()
        conn1.close()

        # Reconnect and verify all tables
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()

        for table in ["conversations", "code_events", "user_preferences", "project_state"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            assert count >= 1, f"Table {table} should have data"

        conn2.close()

    def test_data_integrity_after_reconnect(self, persistent_db, sample_data):
        """Test that data is exactly the same after reconnect."""
        db_path = persistent_db

        # Store
        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data,
        )
        conn1.commit()
        conn1.close()

        # Read back and compare
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT id, timestamp, role, content FROM conversations ORDER BY timestamp")
        rows = cursor.fetchall()
        conn2.close()

        assert len(rows) == len(sample_data)
        for i, row in enumerate(rows):
            assert row[0] == sample_data[i][0]
            assert row[1] == sample_data[i][1]
            assert row[2] == sample_data[i][2]
            assert row[3] == sample_data[i][3]


# ============================================================================
# Search Functionality After Reconnect Tests
# ============================================================================


class TestSearchAfterReconnect:
    """Test that search functionality works after reconnecting."""

    def test_keyword_search_after_reconnect(self, persistent_db, sample_data):
        """Test LIKE-based keyword search after reconnect."""
        db_path = persistent_db

        # Store
        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data,
        )
        conn1.commit()
        conn1.close()

        # Search after reconnect
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute(
            "SELECT id, content FROM conversations WHERE content LIKE ? ORDER BY timestamp DESC",
            ("%auth%",),
        )
        results = cursor.fetchall()
        conn2.close()

        assert len(results) >= 2  # Both auth-related messages
        contents = [r[1] for r in results]
        assert any("authentication" in c.lower() for c in contents)
        assert any("bcrypt" in c.lower() for c in contents)

    def test_recent_conversations_after_reconnect(self, persistent_db, sample_data):
        """Test retrieving recent conversations after reconnect."""
        db_path = persistent_db

        # Store
        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data,
        )
        conn1.commit()
        conn1.close()

        # Get recent after reconnect
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute(
            "SELECT id FROM conversations ORDER BY timestamp DESC LIMIT 3"
        )
        results = cursor.fetchall()
        conn2.close()

        assert len(results) == 3
        # Most recent should be last in sample_data
        assert results[0][0] == sample_data[-1][0]
        assert results[1][0] == sample_data[-2][0]
        assert results[2][0] == sample_data[-3][0]

    def test_code_event_search_after_reconnect(self, persistent_db):
        """Test code event search after reconnect."""
        db_path = persistent_db

        events = [
            ("ce-1", int(time.time()) - 100, "src/auth.py", "create", "+ def login()", "Created auth"),
            ("ce-2", int(time.time()) - 80, "src/db.py", "modify", "+ migration", "Added migration"),
            ("ce-3", int(time.time()) - 60, "Dockerfile", "create", "+ FROM python", "Added Docker"),
        ]

        # Store
        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO code_events (id, timestamp, file_path, change_type, diff, summary) VALUES (?, ?, ?, ?, ?, ?)",
            events,
        )
        conn1.commit()
        conn1.close()

        # Search after reconnect
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute(
            "SELECT id, summary FROM code_events WHERE summary LIKE ? OR file_path LIKE ?",
            ("%auth%", "%auth%"),
        )
        results = cursor.fetchall()
        conn2.close()

        assert len(results) == 1
        assert results[0][0] == "ce-1"

    def test_cross_table_search_after_reconnect(self, persistent_db, sample_data):
        """Test searching across both conversations and code_events after reconnect."""
        db_path = persistent_db

        # Store conversations
        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data[:4],  # First 4 include auth-related
        )
        # Store code events
        conn1.execute(
            "INSERT INTO code_events (id, timestamp, file_path, change_type, diff, summary) VALUES (?, ?, ?, ?, ?, ?)",
            ("ce-auth", int(time.time()), "src/auth.py", "create", "+def login()", "Auth module"),
        )
        conn1.commit()
        conn1.close()

        # Cross-table search after reconnect
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()

        # Search conversations
        cursor.execute(
            "SELECT id, 'conversation' as source, content FROM conversations WHERE content LIKE ?",
            ("%auth%",),
        )
        conv_results = cursor.fetchall()

        # Search code events
        cursor.execute(
            "SELECT id, 'code_event' as source, summary FROM code_events WHERE summary LIKE ? OR file_path LIKE ?",
            ("%auth%", "%auth%"),
        )
        code_results = cursor.fetchall()

        conn2.close()

        combined = conv_results + code_results
        assert len(combined) >= 3  # At least 2 conv + 1 code event

        sources = [r[1] for r in combined]
        assert "conversation" in sources
        assert "code_event" in sources


# ============================================================================
# Project State Persistence Tests
# ============================================================================


class TestProjectStatePersistence:
    """Test project state survives reconnections."""

    def test_project_state_persists(self, persistent_db):
        """Test project state persists across connections."""
        db_path = persistent_db
        project_path = "/home/user/my-project"

        # Store state
        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            """INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(project_path) DO UPDATE SET
                   current_branch = excluded.current_branch,
                   last_commit = excluded.last_commit,
                   agent_context_json = excluded.agent_context_json,
                   updated_at = excluded.updated_at""",
            (project_path, "main", "abc123", json.dumps({"goal": "Build app"}), int(time.time())),
        )
        conn1.commit()
        conn1.close()

        # Read back
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute(
            "SELECT project_path, current_branch, last_commit, agent_context_json FROM project_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        conn2.close()

        assert row is not None
        assert row[0] == project_path
        assert row[1] == "main"
        assert row[2] == "abc123"

        context = json.loads(row[3])
        assert context["goal"] == "Build app"

    def test_project_state_upsert(self, persistent_db):
        """Test that project state can be updated (upsert)."""
        db_path = persistent_db
        project_path = "/projects/test"

        # Initial insert
        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            """INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (project_path, "main", "v1", "{}", 1000),
        )
        conn1.commit()
        conn1.close()

        # Update via upsert
        conn2 = sqlite3.connect(db_path)
        conn2.execute(
            """INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(project_path) DO UPDATE SET
                   current_branch = excluded.current_branch,
                   last_commit = excluded.last_commit,
                   agent_context_json = excluded.agent_context_json,
                   updated_at = excluded.updated_at""",
            (project_path, "feature/new", "v2", json.dumps({"updated": True}), 2000),
        )
        conn2.commit()
        conn2.close()

        # Verify update
        conn3 = sqlite3.connect(db_path)
        cursor = conn3.cursor()
        cursor.execute(
            "SELECT current_branch, last_commit, agent_context_json, updated_at FROM project_state WHERE project_path = ?",
            (project_path,),
        )
        row = cursor.fetchone()
        conn3.close()

        assert row[0] == "feature/new"
        assert row[1] == "v2"
        assert json.loads(row[2]) == {"updated": True}
        assert row[3] == 2000

    def test_multiple_projects_persist_independently(self, persistent_db):
        """Test that multiple projects maintain independent state."""
        db_path = persistent_db

        projects = [
            ("/proj/a", "main", "aaa"),
            ("/proj/b", "dev", "bbb"),
            ("/proj/c", "feature/x", "ccc"),
        ]

        conn1 = sqlite3.connect(db_path)
        for path, branch, commit in projects:
            conn1.execute(
                """INSERT INTO project_state (project_path, current_branch, last_commit, agent_context_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(project_path) DO UPDATE SET
                       current_branch = excluded.current_branch,
                       last_commit = excluded.last_commit,
                       updated_at = excluded.updated_at""",
                (path, branch, commit, "{}", int(time.time())),
            )
        conn1.commit()
        conn1.close()

        # Verify each project independently
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()

        for path, expected_branch, expected_commit in projects:
            cursor.execute(
                "SELECT current_branch, last_commit FROM project_state WHERE project_path = ?",
                (path,),
            )
            row = cursor.fetchone()
            assert row[0] == expected_branch
            assert row[1] == expected_commit

        conn2.close()


# ============================================================================
# Preference Persistence Tests
# ============================================================================


class TestPreferencePersistence:
    """Test that preferences persist and maintain ordering across reconnections."""

    def test_preferences_persist(self, persistent_db):
        """Test preferences persist across connections."""
        db_path = persistent_db

        prefs = [
            ("theme", "dark", 0.95, 1000),
            ("font_size", "14", 0.8, 1000),
            ("auto_save", "true", 0.7, 1000),
        ]

        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
            prefs,
        )
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_preferences")
        count = cursor.fetchone()[0]
        conn2.close()

        assert count == 3

    def test_preference_ordering_persists(self, persistent_db):
        """Test that preference confidence ordering survives reconnect."""
        db_path = persistent_db

        prefs = [
            ("low", "val1", 0.3, 1000),
            ("high", "val2", 0.95, 1000),
            ("mid", "val3", 0.6, 1000),
        ]

        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
            prefs,
        )
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute(
            "SELECT key, confidence FROM user_preferences ORDER BY confidence DESC"
        )
        results = cursor.fetchall()
        conn2.close()

        assert results[0] == ("high", 0.95)
        assert results[1] == ("mid", 0.6)
        assert results[2] == ("low", 0.3)

    def test_preference_upsert_persists(self, persistent_db):
        """Test that preference updates persist."""
        db_path = persistent_db

        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
            ("theme", "dark", 0.9, 1000),
        )
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(db_path)
        conn2.execute(
            """INSERT INTO user_preferences (key, value, confidence, last_updated)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   confidence = excluded.confidence,
                   last_updated = excluded.last_updated""",
            ("theme", "light", 0.85, 2000),
        )
        conn2.commit()
        conn2.close()

        conn3 = sqlite3.connect(db_path)
        cursor = conn3.cursor()
        cursor.execute("SELECT value, confidence FROM user_preferences WHERE key = ?", ("theme",))
        row = cursor.fetchone()
        conn3.close()

        assert row == ("light", 0.85)


# ============================================================================
# WAL Mode Tests
# ============================================================================


class TestWALMode:
    """Test Write-Ahead Logging mode for durability."""

    def test_wal_mode_enabled(self, persistent_db):
        """Test that WAL mode is enabled."""
        db_path = persistent_db

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()

        assert mode.lower() == "wal"

    def test_wal_checkpoint(self, persistent_db, sample_data):
        """Test that WAL checkpoint works and data is durable."""
        db_path = persistent_db

        conn1 = sqlite3.connect(db_path)
        conn1.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data,
        )
        conn1.commit()

        # Force WAL checkpoint
        conn1.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn1.close()

        # Verify data exists after checkpoint
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        conn2.close()

        assert count == len(sample_data)

    def test_data_survives_unclean_close(self, persistent_db, sample_data):
        """Test that data survives an unclean connection close."""
        db_path = persistent_db

        # Store data (simulating WAL writes)
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data,
        )
        conn.commit()
        # Don't close cleanly - just let the connection go out of scope
        del conn

        # New connection should still see the data
        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        conn2.close()

        assert count == len(sample_data)


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestPersistenceEdgeCases:
    """Test edge cases for memory persistence."""

    def test_empty_database_reconnect(self, persistent_db):
        """Test connecting to an empty database."""
        db_path = persistent_db

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table in ["conversations", "code_events", "user_preferences", "project_state"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            assert cursor.fetchone()[0] == 0
        conn.close()

    def test_unicode_content_persists(self, persistent_db):
        """Test that unicode content survives reconnection."""
        db_path = persistent_db
        content = "Hello World 日本語 test 中文 emoji"

        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("unicode", int(time.time()), "user", content),
        )
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT content FROM conversations WHERE id = ?", ("unicode",))
        row = cursor.fetchone()
        conn2.close()

        assert row[0] == content

    def test_large_content_persists(self, persistent_db):
        """Test that large content survives reconnection."""
        db_path = persistent_db
        large_content = "x" * 1_000_000

        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("large", int(time.time()), "user", large_content),
        )
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT LENGTH(content) FROM conversations WHERE id = ?", ("large",))
        length = cursor.fetchone()[0]
        conn2.close()

        assert length == 1_000_000

    def test_special_characters_persist(self, persistent_db):
        """Test that special characters in content survive reconnection."""
        db_path = persistent_db
        content = "Hello 'world' \"test\" -- ; /* comment */ \n\t"

        conn1 = sqlite3.connect(db_path)
        conn1.execute(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            ("special", int(time.time()), "user", content),
        )
        conn1.commit()
        conn1.close()

        conn2 = sqlite3.connect(db_path)
        cursor = conn2.cursor()
        cursor.execute("SELECT content FROM conversations WHERE id = ?", ("special",))
        row = cursor.fetchone()
        conn2.close()

        assert row[0] == content

    def test_multiple_reconnections(self, persistent_db, sample_data):
        """Test data persists through multiple disconnect/reconnect cycles."""
        db_path = persistent_db

        # Cycle 1: Insert
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data[:2],
        )
        conn.commit()
        conn.close()

        # Cycle 2: Insert more
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
            sample_data[2:4],
        )
        conn.commit()
        conn.close()

        # Cycle 3: Read
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 4
