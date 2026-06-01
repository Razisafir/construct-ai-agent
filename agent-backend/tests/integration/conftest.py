"""
Shared fixtures for integration tests.

Uses httpx.AsyncClient with the running FastAPI backend.
No mocks — all calls hit real endpoints with real databases.
"""

import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture
async def client():
    """Yield an async HTTP client connected to the running backend."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as c:
        yield c
