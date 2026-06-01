"""Language Server Protocol manager — spawn, connect, bridge to WebSocket.

Supports TypeScript, Python, and Rust language servers via stdio transport.
The LSP manager spawns each server as a subprocess, communicates over
stdin/stdout using the LSP base protocol (Content-Length header framing),
and bridges messages to/from WebSocket clients connected from the Monaco
editor frontend.

Architecture:
    Frontend (Monaco) ←→ WebSocket ←→ Python Backend ←→ stdio ←→ Language Server
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import os
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LSPConnection:
    """Represents an active connection to a language server process."""

    process: subprocess.Popen
    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    capabilities: Dict[str, Any] = field(default_factory=dict)
    initialized: bool = False
    request_id: int = 0
    project_path: str = ""
    pending_requests: Dict[int, asyncio.Future] = field(default_factory=dict)
    notification_handlers: list = field(default_factory=list)


class LSPManager:
    """Manages LSP server processes and WebSocket bridges.

    Spawns language server processes on demand, handles the LSP initialize
    handshake, and provides methods to send requests and receive responses.
    Each language server runs as a long-lived subprocess communicating via
    stdio using the LSP base protocol (Content-Length header framing).

    Usage:
        manager = LSPManager()
        started = await manager.start("typescript", "/path/to/project")
        if started:
            result = await manager.request("typescript", "textDocument/hover", {...})
    """

    SERVERS = {
        "typescript": {
            "command": ["typescript-language-server", "--stdio"],
            "install_hint": "npm install -g typescript-language-server typescript",
            "languages": ["typescript", "javascript", "typescriptreact", "javascriptreact"],
        },
        "python": {
            "command": ["pylsp"],
            "install_hint": "pip install python-lsp-server[all]",
            "languages": ["python"],
        },
        "rust": {
            "command": ["rust-analyzer"],
            "install_hint": "rustup component add rust-analyzer",
            "languages": ["rust"],
        },
    }

    def __init__(self) -> None:
        self.connections: Dict[str, LSPConnection] = {}
        self._reader_tasks: Dict[str, asyncio.Task] = {}

    def _get_server_for_language(self, language: str) -> Optional[str]:
        """Map a Monaco language ID to an LSP server key."""
        for server_key, config in self.SERVERS.items():
            if language in config.get("languages", []):
                return server_key
        return None

    def is_installed(self, language: str) -> bool:
        """Check if the LSP server for a language is installed."""
        server_key = self._get_server_for_language(language)
        if not server_key:
            return False
        config = self.SERVERS[server_key]
        try:
            result = subprocess.run(
                [config["command"][0], "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_install_hint(self, language: str) -> Optional[str]:
        """Get the install command for a language's LSP server."""
        server_key = self._get_server_for_language(language)
        if not server_key:
            return None
        return self.SERVERS[server_key].get("install_hint")

    async def start(self, language: str, project_path: str) -> bool:
        """Start an LSP server for the given language.

        Args:
            language: Monaco language ID (e.g. "typescript", "python", "rust").
            project_path: Root directory of the project for LSP context.

        Returns:
            True if the server started and initialized successfully.
        """
        server_key = self._get_server_for_language(language)
        if not server_key:
            logger.warning("No LSP server configured for language: %s", language)
            return False

        # Already running?
        if server_key in self.connections and self.connections[server_key].initialized:
            logger.info("LSP server '%s' already running", server_key)
            return True

        config = self.SERVERS[server_key]

        # Check if installed
        if not self.is_installed(language):
            logger.warning(
                "LSP server for '%s' not installed. Install with: %s",
                server_key,
                config.get("install_hint", "N/A"),
            )
            return False

        try:
            # Spawn process
            logger.info("Starting LSP server '%s' for project: %s", server_key, project_path)
            process = subprocess.Popen(
                config["command"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_path,
                env={**os.environ},
            )

            conn = LSPConnection(
                process=process,
                project_path=project_path,
            )
            self.connections[server_key] = conn

            # Set up async streams
            loop = asyncio.get_event_loop()

            # Reader
            reader = asyncio.StreamReader()
            reader_protocol = asyncio.StreamReaderProtocol(reader)
            await loop.connect_read_pipe(lambda: reader_protocol, process.stdout)
            conn.reader = reader

            # Writer
            writer_transport, writer_protocol = await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, process.stdin
            )
            conn.writer = asyncio.StreamWriter(
                writer_transport, writer_protocol, None, loop
            )

            # Start background reader task
            reader_task = asyncio.create_task(
                self._read_loop(server_key), name=f"lsp-reader-{server_key}"
            )
            self._reader_tasks[server_key] = reader_task

            # Initialize
            await self._initialize(conn, project_path, server_key)

            logger.info(
                "LSP server '%s' initialized successfully (capabilities: %s)",
                server_key,
                list(conn.capabilities.keys()),
            )
            return True

        except Exception as exc:
            logger.error("Failed to start LSP server '%s': %s", server_key, exc)
            # Clean up
            if server_key in self.connections:
                conn = self.connections.pop(server_key)
                if conn.process.poll() is None:
                    conn.process.terminate()
            return False

    async def _initialize(self, conn: LSPConnection, root_path: str, server_key: str) -> None:
        """Send LSP initialize request and wait for response."""
        conn.request_id += 1
        init_id = conn.request_id

        root_uri = f"file://{root_path}"

        init_params = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "rootPath": root_path,
            "capabilities": {
                "textDocument": {
                    "completion": {
                        "completionItem": {
                            "snippetSupport": True,
                            "resolveSupport": {"properties": ["documentation", "detail"]},
                        },
                        "contextSupport": True,
                    },
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "definition": {"linkSupport": True},
                    "publishDiagnostics": {
                        "relatedInformation": True,
                        "versionSupport": True,
                    },
                    "signatureHelp": {"signatureInformation": {"documentationFormat": ["markdown", "plaintext"]}},
                    "semanticTokens": {
                        "full": True,
                        "delta": True,
                    },
                },
                "workspace": {
                    "applyEdit": True,
                    "didChangeConfiguration": {"dynamicRegistration": True},
                },
            },
        }

        # Create future for the response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        conn.pending_requests[init_id] = future

        # Send initialize request
        await self._send_message(conn, {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": init_params,
        })

        # Wait for response (with timeout)
        try:
            response = await asyncio.wait_for(future, timeout=15.0)
            result = response.get("result", {})
            conn.capabilities = result.get("capabilities", {})
            conn.initialized = True
        except asyncio.TimeoutError:
            logger.error("LSP initialize request timed out for '%s'", server_key)
            raise
        finally:
            conn.pending_requests.pop(init_id, None)

        # Send initialized notification
        await self._send_message(conn, {
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {},
        })

    async def _send_message(self, conn: LSPConnection, message: Dict[str, Any]) -> None:
        """Send an LSP message with Content-Length header framing."""
        if conn.writer is None:
            raise RuntimeError("LSP connection writer not initialized")

        body = json.dumps(message)
        header = f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n"
        conn.writer.write((header + body).encode("utf-8"))
        await conn.writer.drain()

    async def _read_loop(self, server_key: str) -> None:
        """Background task that reads LSP messages from a server process."""
        conn = self.connections.get(server_key)
        if not conn or conn.reader is None:
            return

        try:
            while conn.process.poll() is None:
                try:
                    message = await self._read_message(conn)
                    if message is None:
                        continue

                    # Handle response to a pending request
                    msg_id = message.get("id")
                    if msg_id is not None and msg_id in conn.pending_requests:
                        future = conn.pending_requests.pop(msg_id, None)
                        if future and not future.done():
                            future.set_result(message)
                    # Handle notifications (e.g. textDocument/publishDiagnostics)
                    elif message.get("method"):
                        for handler in conn.notification_handlers:
                            try:
                                handler(server_key, message)
                            except Exception as exc:
                                logger.debug("Notification handler error: %s", exc)

                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    if conn.process.poll() is None:
                        logger.debug("LSP read error for '%s': %s", server_key, exc)
                    break

        except asyncio.CancelledError:
            pass
        finally:
            logger.info("LSP reader task exiting for '%s'", server_key)

    async def _read_message(self, conn: LSPConnection, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Read a single LSP message from the server's stdout."""
        if conn.reader is None:
            return None

        # Read header lines until blank line
        content_length = 0
        while True:
            try:
                line = await asyncio.wait_for(conn.reader.readline(), timeout=timeout)
            except asyncio.TimeoutError:
                return None

            if not line:
                return None  # EOF

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                break  # Blank line separates header from body

            if line_str.startswith("Content-Length:"):
                try:
                    content_length = int(line_str.split(":")[1].strip())
                except ValueError:
                    pass

        if content_length <= 0:
            return None

        # Read body
        try:
            body = await asyncio.wait_for(
                conn.reader.read(content_length), timeout=timeout
            )
        except asyncio.TimeoutError:
            return None

        if not body:
            return None

        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Failed to decode LSP message body")
            return None

    async def request(self, language: str, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send an LSP request and wait for the response.

        Args:
            language: Monaco language ID.
            method: LSP method name (e.g. "textDocument/hover").
            params: LSP request parameters.

        Returns:
            The LSP response dict, or None on error.
        """
        server_key = self._get_server_for_language(language)
        if not server_key or server_key not in self.connections:
            return None

        conn = self.connections[server_key]
        if not conn.initialized:
            return None

        conn.request_id += 1
        req_id = conn.request_id

        # Create future for response
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        conn.pending_requests[req_id] = future

        try:
            await self._send_message(conn, {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            })

            # Wait for response (with timeout)
            response = await asyncio.wait_for(future, timeout=10.0)
            return response

        except asyncio.TimeoutError:
            logger.warning("LSP request '%s' timed out for '%s'", method, server_key)
            conn.pending_requests.pop(req_id, None)
            return None
        except Exception as exc:
            logger.error("LSP request error: %s", exc)
            conn.pending_requests.pop(req_id, None)
            return None

    async def notify(self, language: str, method: str, params: Dict[str, Any]) -> None:
        """Send an LSP notification (no response expected).

        Args:
            language: Monaco language ID.
            method: LSP notification method.
            params: Notification parameters.
        """
        server_key = self._get_server_for_language(language)
        if not server_key or server_key not in self.connections:
            return

        conn = self.connections[server_key]
        if not conn.initialized:
            return

        await self._send_message(conn, {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

    def add_notification_handler(self, language: str, handler) -> None:
        """Register a handler for LSP notifications.

        Handler signature: handler(server_key: str, message: dict)
        """
        server_key = self._get_server_for_language(language)
        if server_key and server_key in self.connections:
            self.connections[server_key].notification_handlers.append(handler)

    async def did_open(self, language: str, file_path: str, content: str, version: int = 1) -> None:
        """Send textDocument/didOpen notification."""
        await self.notify(language, "textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{file_path}",
                "languageId": language,
                "version": version,
                "text": content,
            }
        })

    async def did_change(self, language: str, file_path: str, content: str, version: int) -> None:
        """Send textDocument/didChange notification with full text sync."""
        await self.notify(language, "textDocument/didChange", {
            "textDocument": {
                "uri": f"file://{file_path}",
                "version": version,
            },
            "contentChanges": [{"text": content}],
        })

    async def did_close(self, language: str, file_path: str) -> None:
        """Send textDocument/didClose notification."""
        await self.notify(language, "textDocument/didClose", {
            "textDocument": {
                "uri": f"file://{file_path}",
            }
        })

    def stop(self, language: str) -> None:
        """Stop an LSP server for the given language."""
        server_key = self._get_server_for_language(language)
        if server_key and server_key in self.connections:
            conn = self.connections.pop(server_key)
            # Cancel reader task
            task = self._reader_tasks.pop(server_key, None)
            if task and not task.done():
                task.cancel()
            # Terminate process
            if conn.process.poll() is None:
                conn.process.terminate()
                try:
                    conn.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    conn.process.kill()
            logger.info("LSP server '%s' stopped", server_key)

    def stop_all(self) -> None:
        """Stop all running LSP servers."""
        for server_key in list(self.connections.keys()):
            self.stop(server_key)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all LSP servers."""
        status = {}
        for key, config in self.SERVERS.items():
            conn = self.connections.get(key)
            status[key] = {
                "installed": self.is_installed(config["languages"][0] if config["languages"] else ""),
                "running": conn is not None and conn.initialized,
                "languages": config.get("languages", []),
                "install_hint": config.get("install_hint", ""),
            }
        return status
