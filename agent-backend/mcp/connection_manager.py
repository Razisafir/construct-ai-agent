"""MCP Connection Manager — pooled connections, health monitoring, auto-reconnect.

Manages connections to 50+ MCP servers with connection pooling,
health checks, and automatic reconnection.

Example::
    manager = MCPConnectionManager()
    config = ServerConfig(name="github", url="http://localhost:3001/sse")
    await manager.connect("github", config)
    result = await manager.request("github", "POST", "/tools/call", json={...})
    await manager.disconnect("github")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientTimeout, ClientError, ClientResponseError

logger = logging.getLogger(__name__)


class ConnectionStatus(str, Enum):
    """Lifecycle states for an MCP connection."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    DEGRADED = "degraded"


@dataclass
class HealthStatus:
    """Snapshot of connection health metrics."""

    status: ConnectionStatus
    latency_ms: float
    last_error: Optional[str]
    last_success: float
    consecutive_failures: int
    total_requests: int
    success_rate: float


@dataclass
class ServerConfig:
    """Configuration for a single MCP server connection."""

    name: str
    url: str
    api_key: Optional[str] = None
    timeout_sec: float = 30.0
    max_retries: int = 3
    headers: Dict[str, str] = field(default_factory=dict)
    retry_backoff_base: float = 1.0
    retry_backoff_max: float = 60.0
    pool_size: int = 10


class MCPConnection:
    """A single connection to an MCP server.

    Wraps an :class:`aiohttp.ClientSession` with health tracking,
    automatic retry logic, and graceful disconnect.
    """

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.session: Optional[aiohttp.ClientSession] = None
        self._health = HealthStatus(
            status=ConnectionStatus.DISCONNECTED,
            latency_ms=0.0,
            last_error=None,
            last_success=0.0,
            consecutive_failures=0,
            total_requests=0,
            success_rate=1.0,
        )
        self._lock = asyncio.Lock()
        self._active_requests = 0
        self._semaphore = asyncio.Semaphore(config.pool_size)

    async def connect(self) -> bool:
        """Establish connection to the MCP server.

        Creates a persistent :class:`aiohttp.ClientSession` and sends a
        lightweight health-check probe to verify reachability.

        Returns:
            ``True`` if the server responded with 2xx, ``False`` otherwise.
        """
        async with self._lock:
            if self.status == ConnectionStatus.CONNECTED and self.session is not None:
                logger.debug("Connection to %s already established", self.config.name)
                return True

            self.status = ConnectionStatus.CONNECTING
            try:
                timeout = ClientTimeout(total=self.config.timeout_sec)
                default_headers: Dict[str, str] = dict(self.config.headers)
                if self.config.api_key:
                    default_headers["Authorization"] = f"Bearer {self.config.api_key}"
                default_headers["Content-Type"] = "application/json"

                connector = aiohttp.TCPConnector(
                    limit=self.config.pool_size,
                    limit_per_host=self.config.pool_size,
                    enable_cleanup_closed=True,
                    force_close=False,
                )
                self.session = aiohttp.ClientSession(
                    base_url=self.config.url.rstrip("/"),
                    headers=default_headers,
                    timeout=timeout,
                    connector=connector,
                )

                # Probe with a lightweight health endpoint or root GET
                probe_path = "/health" if not self.config.url.endswith("/sse") else "/"
                probe_url = f"{self.config.url.rstrip('/')}{probe_path}"
                async with aiohttp.ClientSession(timeout=timeout) as probe_session:
                    async with probe_session.get(probe_url, headers=default_headers) as resp:
                        if resp.status < 500:
                            self.status = ConnectionStatus.CONNECTED
                            self._health.status = ConnectionStatus.CONNECTED
                            self._health.last_success = time.time()
                            logger.info(
                                "Connected to MCP server %s at %s (probe_status=%s)",
                                self.config.name,
                                self.config.url,
                                resp.status,
                            )
                            return True
            except asyncio.TimeoutError:
                logger.warning(
                    "Connection timeout to %s at %s", self.config.name, self.config.url
                )
                self.status = ConnectionStatus.ERROR
                self._health.status = ConnectionStatus.ERROR
                self._health.last_error = "Connection timeout"
            except ClientError as exc:
                logger.warning(
                    "Connection error to %s: %s", self.config.name, exc
                )
                self.status = ConnectionStatus.ERROR
                self._health.status = ConnectionStatus.ERROR
                self._health.last_error = str(exc)
            except Exception as exc:
                logger.error(
                    "Unexpected error connecting to %s: %s",
                    self.config.name,
                    exc,
                    exc_info=True,
                )
                self.status = ConnectionStatus.ERROR
                self._health.status = ConnectionStatus.ERROR
                self._health.last_error = str(exc)

            return False

    async def disconnect(self) -> None:
        """Close the connection and release resources."""
        async with self._lock:
            if self.session is not None:
                try:
                    await self.session.close()
                except Exception as exc:
                    logger.warning(
                        "Error closing session for %s: %s", self.config.name, exc
                    )
                finally:
                    self.session = None
            self.status = ConnectionStatus.DISCONNECTED
            self._health.status = ConnectionStatus.DISCONNECTED
            logger.info("Disconnected from MCP server %s", self.config.name)

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make an HTTP request through this connection.

        Tracks latency, updates health metrics, and applies retry logic
        with exponential backoff.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path (relative to base URL).
            **kwargs: Extra arguments forwarded to :meth:`aiohttp.ClientSession.request`.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ClientError: After exhausting all retries.
            RuntimeError: If the connection is not established.
        """
        if self.session is None or self.status != ConnectionStatus.CONNECTED:
            raise RuntimeError(
                f"Connection to {self.config.name} is not established. "
                "Call connect() first."
            )

        last_exception: Optional[Exception] = None
        for attempt in range(1, self.config.max_retries + 1):
            async with self._semaphore:
                start = time.perf_counter()
                try:
                    async with self.session.request(method, path, **kwargs) as resp:
                        latency_ms = (time.perf_counter() - start) * 1000
                        self._record_success(latency_ms)

                        if resp.status == 204:
                            return {"ok": True}

                        body = await resp.json()
                        return body

                except (ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
                    latency_ms = (time.perf_counter() - start) * 1000
                    last_exception = exc
                    self._record_failure(str(exc), latency_ms)
                    if attempt < self.config.max_retries:
                        backoff = min(
                            self.config.retry_backoff_base * (2 ** (attempt - 1)),
                            self.config.retry_backoff_max,
                        )
                        jitter = backoff * 0.1 * (asyncio.get_event_loop().time() % 1)
                        logger.warning(
                            "Request to %s %s failed (attempt %d/%d): %s. "
                            "Retrying in %.2fs",
                            self.config.name,
                            path,
                            attempt,
                            self.config.max_retries,
                            exc,
                            backoff + jitter,
                        )
                        await asyncio.sleep(backoff + jitter)
                except Exception as exc:
                    self._record_failure(str(exc), 0.0)
                    logger.error(
                        "Unexpected error on %s %s: %s",
                        self.config.name,
                        path,
                        exc,
                        exc_info=True,
                    )
                    raise

        raise last_exception or ClientError(
            f"All {self.config.max_retries} retries exhausted for {self.config.name}"
        )

    def _record_success(self, latency_ms: float) -> None:
        """Update health metrics after a successful request."""
        self._health.total_requests += 1
        self._health.consecutive_failures = 0
        self._health.last_success = time.time()
        self._health.latency_ms = latency_ms
        total = self._health.total_requests
        successes = total - self._health.consecutive_failures
        self._health.success_rate = successes / total if total > 0 else 1.0
        if self._health.status == ConnectionStatus.ERROR:
            self._health.status = ConnectionStatus.CONNECTED
            self.status = ConnectionStatus.CONNECTED

    def _record_failure(self, error_msg: str, latency_ms: float) -> None:
        """Update health metrics after a failed request."""
        self._health.total_requests += 1
        self._health.consecutive_failures += 1
        self._health.last_error = error_msg
        self._health.latency_ms = latency_ms
        total = self._health.total_requests
        successes = total - self._health.consecutive_failures
        self._health.success_rate = successes / total if total > 0 else 0.0

        if self._health.consecutive_failures >= 3:
            self._health.status = ConnectionStatus.ERROR
            self.status = ConnectionStatus.ERROR
        elif self._health.consecutive_failures >= 1:
            self._health.status = ConnectionStatus.DEGRADED
            self.status = ConnectionStatus.DEGRADED

    @property
    def health(self) -> HealthStatus:
        """Return a snapshot of the current health status."""
        return self._health


class MCPConnectionManager:
    """Manages pooled connections to multiple MCP servers.

    Features:
    * Persistent connection pool keyed by server name.
    * Automatic health monitoring with a background task.
    * Auto-reconnect with exponential backoff for failed servers.
    * Thread-safe concurrent access.

    Example::
        manager = MCPConnectionManager(health_check_interval=30)
        await manager.connect("github", ServerConfig(name="github", url="..."))
        await manager.start_health_monitor()
        result = await manager.request("github", "POST", "/tools/call", json={...})
    """

    def __init__(
        self,
        health_check_interval: int = 60,
        auto_reconnect: bool = True,
    ) -> None:
        self._connections: Dict[str, MCPConnection] = {}
        self._configs: Dict[str, ServerConfig] = {}
        self._health_check_interval = health_check_interval
        self._auto_reconnect = auto_reconnect
        self._running = False
        self._health_task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

    async def connect(self, server_name: str, config: ServerConfig) -> bool:
        """Connect to an MCP server and add it to the pool.

        Args:
            server_name: Unique identifier for this server.
            config: Connection configuration.

        Returns:
            ``True`` if the connection was established successfully.
        """
        async with self._lock:
            if server_name in self._connections:
                logger.debug("Connection %s already exists, disconnecting first", server_name)
                old = self._connections.pop(server_name)
                await old.disconnect()

            conn = MCPConnection(config)
            self._configs[server_name] = config
            self._connections[server_name] = conn

        success = await conn.connect()
        if not success and self._auto_reconnect:
            logger.info("Initial connection to %s failed, will retry in background", server_name)
        return success

    async def test_connection(self, server_name: str) -> bool:
        """Test if a server connection is healthy.

        Sends a lightweight probe request and updates the health status.

        Args:
            server_name: The server to test.

        Returns:
            ``True`` if the server responded successfully.
        """
        conn = await self._get_connection(server_name)
        if conn is None:
            return False

        try:
            start = time.perf_counter()
            await conn.request("GET", "/health")
            latency_ms = (time.perf_counter() - start) * 1000
            conn._health.latency_ms = latency_ms
            conn._health.last_success = time.time()
            conn._health.consecutive_failures = 0
            conn._health.status = ConnectionStatus.CONNECTED
            conn.status = ConnectionStatus.CONNECTED
            return True
        except Exception as exc:
            conn._record_failure(str(exc), 0.0)
            logger.debug("Health check failed for %s: %s", server_name, exc)
            return False

    def get_health(self, server_name: str) -> Optional[HealthStatus]:
        """Get the health status of a server.

        Args:
            server_name: The server to query.

        Returns:
            :class:`HealthStatus` if the server is known, ``None`` otherwise.
        """
        conn = self._connections.get(server_name)
        return conn.health if conn else None

    def get_all_health(self) -> Dict[str, HealthStatus]:
        """Return health status for every known server.

        Returns:
            Mapping of server name -> :class:`HealthStatus`.
        """
        return {name: conn.health for name, conn in self._connections.items()}

    async def auto_reconnect(self, server_name: str) -> bool:
        """Attempt to reconnect to a failed server.

        Disconnects the old session (if any) and creates a fresh one.

        Args:
            server_name: The server to reconnect.

        Returns:
            ``True`` if reconnection succeeded.
        """
        async with self._lock:
            conn = self._connections.get(server_name)
            if conn is None:
                logger.warning("Cannot reconnect unknown server %s", server_name)
                return False

        logger.info("Attempting auto-reconnect to %s", server_name)
        await conn.disconnect()
        success = await conn.connect()
        if success:
            logger.info("Auto-reconnect to %s succeeded", server_name)
        else:
            logger.warning("Auto-reconnect to %s failed", server_name)
        return success

    async def disconnect(self, server_name: str) -> None:
        """Disconnect from a server and remove it from the pool.

        Args:
            server_name: The server to disconnect.
        """
        async with self._lock:
            conn = self._connections.pop(server_name, None)
            self._configs.pop(server_name, None)
        if conn is not None:
            await conn.disconnect()

    async def disconnect_all(self) -> None:
        """Disconnect from every server in the pool."""
        async with self._lock:
            names = list(self._connections.keys())
        await asyncio.gather(
            *[self.disconnect(name) for name in names],
            return_exceptions=True,
        )
        logger.info("All MCP connections closed (%d servers)", len(names))

    async def request(
        self,
        server_name: str,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make a request to a specific server.

        Args:
            server_name: The target server.
            method: HTTP method.
            path: URL path.
            **kwargs: Forwarded to :meth:`MCPConnection.request`.

        Returns:
            Parsed JSON response.

        Raises:
            KeyError: If the server is not in the pool.
        """
        conn = await self._get_connection(server_name)
        if conn is None:
            raise KeyError(f"Server '{server_name}' is not in the connection pool")

        if conn.status != ConnectionStatus.CONNECTED:
            if self._auto_reconnect:
                success = await self.auto_reconnect(server_name)
                if not success:
                    raise RuntimeError(
                        f"Server '{server_name}' is unreachable and auto-reconnect failed"
                    )
            else:
                raise RuntimeError(
                    f"Server '{server_name}' is not connected (status={conn.status.value})"
                )

        return await conn.request(method, path, **kwargs)

    async def start_health_monitor(self) -> None:
        """Start a background task that runs periodic health checks.

        The task checks every ``health_check_interval`` seconds and
        attempts auto-reconnect for failed connections.
        """
        if self._running:
            logger.debug("Health monitor already running")
            return
        self._running = True
        self._health_task = asyncio.create_task(self._health_monitor_loop())
        logger.info("Health monitor started (interval=%ds)", self._health_check_interval)

    async def stop_health_monitor(self) -> None:
        """Stop the background health-monitor task."""
        self._running = False
        if self._health_task is not None:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None
        logger.info("Health monitor stopped")

    async def _health_monitor_loop(self) -> None:
        """Internal loop for periodic health checks."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                if not self._running:
                    break
                await self._run_health_checks()
            except asyncio.CancelledError:
                logger.debug("Health monitor loop cancelled")
                break
            except Exception as exc:
                logger.error("Health monitor loop error: %s", exc, exc_info=True)
                await asyncio.sleep(5)

    async def _run_health_checks(self) -> None:
        """Check every connection and trigger auto-reconnect where needed."""
        tasks: List[Coroutine[Any, Any, bool]] = []
        targets: List[str] = []

        for name, conn in self._connections.items():
            if conn.health.status in (ConnectionStatus.ERROR, ConnectionStatus.DISCONNECTED):
                if self._auto_reconnect:
                    tasks.append(self.auto_reconnect(name))
                    targets.append(name)
            else:
                tasks.append(self.test_connection(name))
                targets.append(name)

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(targets, results):
            if isinstance(result, Exception):
                logger.debug("Health check error for %s: %s", name, result)
            elif result is True:
                logger.debug("Health check OK for %s", name)
            else:
                logger.debug("Health check FAILED for %s", name)

    def list_servers(self) -> List[str]:
        """List all connected server names.

        Returns:
            List of server identifiers currently in the pool.
        """
        return list(self._connections.keys())

    def get_server_count(self) -> int:
        """Return the number of servers in the pool.

        Returns:
            Count of registered servers.
        """
        return len(self._connections)

    async def _get_connection(self, server_name: str) -> Optional[MCPConnection]:
        """Safely retrieve a connection by name.

        Args:
            server_name: The server identifier.

        Returns:
            The :class:`MCPConnection` if present, ``None`` otherwise.
        """
        async with self._lock:
            return self._connections.get(server_name)

    async def __aenter__(self) -> MCPConnectionManager:
        """Async context manager entry — start health monitor."""
        await self.start_health_monitor()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Async context manager exit — stop monitor and disconnect all."""
        await self.stop_health_monitor()
        await self.disconnect_all()
