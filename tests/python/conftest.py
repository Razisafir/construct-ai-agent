"""Shared fixtures for all Construct Python tests."""

import os
import sys
import json
import tempfile
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Generator, Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

# Add the project source to the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Common fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that is cleaned up after the test."""
    tmp = tempfile.mkdtemp(prefix="construct_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def temp_file(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a temporary file for testing."""
    file_path = temp_dir / "test_file.txt"
    file_path.write_text("Hello, World!\n")
    yield file_path


@pytest.fixture
def sample_project_dir(temp_dir: Path) -> Path:
    """Create a sample project directory structure."""
    # Create a realistic project structure
    src = temp_dir / "src"
    src.mkdir()
    (src / "main.py").write_text(
        'def main():\n    print("Hello")\n\nif __name__ == "__main__":\n    main()\n'
    )
    (src / "utils.py").write_text(
        "def helper():\n    return 42\n"
    )
    tests = temp_dir / "tests"
    tests.mkdir()
    (tests / "test_main.py").write_text(
        "def test_main():\n    assert True\n"
    )
    (temp_dir / "README.md").write_text("# Sample Project\n")
    (temp_dir / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools"]\n'
    )
    return temp_dir


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_db(temp_dir: Path) -> Generator[sqlite3.Connection, None, None]:
    """Create an in-memory SQLite database with the Construct schema."""
    conn = sqlite3.connect(":memory:")
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
    yield conn
    conn.close()


@pytest.fixture
def populated_db(sqlite_db: sqlite3.Connection) -> sqlite3.Connection:
    """Populate the database with sample data."""
    cursor = sqlite_db.cursor()

    # Insert sample conversations
    conversations = [
        ("conv-1", 1000, "user", "How do I set up authentication?"),
        ("conv-2", 1010, "assistant", "You can use JWT tokens for auth."),
        ("conv-3", 1020, "user", "What about database migrations?"),
        ("conv-4", 1030, "assistant", "Use Alembic for SQLAlchemy migrations."),
        ("conv-5", 1040, "user", "How to deploy to production?"),
    ]
    cursor.executemany(
        "INSERT INTO conversations (id, timestamp, role, content) VALUES (?, ?, ?, ?)",
        conversations,
    )

    # Insert sample code events
    code_events = [
        ("ce-1", 2000, "src/auth.py", "create", "+ def login(): ...", "Created auth module"),
        ("ce-2", 2010, "src/db.py", "modify", "+ migration support", "Added migrations"),
        ("ce-3", 2020, "Dockerfile", "create", "+ FROM python:3.11", "Added Dockerfile"),
    ]
    cursor.executemany(
        "INSERT INTO code_events (id, timestamp, file_path, change_type, diff, summary) VALUES (?, ?, ?, ?, ?, ?)",
        code_events,
    )

    # Insert sample preferences
    preferences = [
        ("theme", "dark", 0.95, 1000),
        ("font_size", "14", 0.80, 1000),
        ("auto_save", "true", 0.65, 1000),
    ]
    cursor.executemany(
        "INSERT INTO user_preferences (key, value, confidence, last_updated) VALUES (?, ?, ?, ?)",
        preferences,
    )

    sqlite_db.commit()
    return sqlite_db


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client() -> Generator[MagicMock, None, None]:
    """Create a mock LLM client for testing."""
    client = MagicMock()
    client.complete.return_value = {
        "content": "I'll help you with that task.",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    client.stream_complete.return_value = (
        chunk for chunk in [
            {"content": "I'll ", "done": False},
            {"content": "help ", "done": False},
            {"content": "you.", "done": True},
        ]
    )
    yield client


@pytest.fixture
def mock_chromadb() -> Generator[MagicMock, None, None]:
    """Create a mock ChromaDB collection for testing."""
    collection = MagicMock()
    collection.add.return_value = None
    collection.query.return_value = {
        "ids": [["doc-1", "doc-2"]],
        "documents": [["Document 1 content", "Document 2 content"]],
        "metadatas": [[{"source": "test"}, {"source": "test"}]],
        "distances": [[0.1, 0.3]],
    }
    yield collection


@pytest.fixture
def mock_git_repo(temp_dir: Path) -> Path:
    """Initialize a mock git repository."""
    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    # Create initial commit
    (temp_dir / "README.md").write_text("# Test Repo\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        capture_output=True,
        check=True,
    )
    return temp_dir


# ---------------------------------------------------------------------------
# Environment fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_env_mutations() -> Generator[None, None, None]:
    """Automatically save and restore environment variables."""
    orig_env = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(orig_env)


@pytest.fixture
def env_vars() -> Generator[None, None, None]:
    """Set test environment variables."""
    os.environ["CONSTRUCT_ENV"] = "test"
    os.environ["OPENAI_API_KEY"] = "sk-test-key-12345"
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-67890"
    yield
