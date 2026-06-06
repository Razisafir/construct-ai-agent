#!/bin/bash
# Ghidra MCP Server Entrypoint
#
# Starts the Ghidra headless analyzer with MCP server integration.
# The MCP server listens on port 8765 for incoming analysis requests.

set -e

echo "=== CONSTRUCT Ghidra MCP Server ==="
echo "Ghidra version: ${GHIDRA_VERSION:-unknown}"
echo "Ghidra install: ${GHIDRA_INSTALL_DIR:-/opt/ghidra}"
echo "MCP port: 8765"
echo ""

# Verify Ghidra installation
if [ ! -f "${GHIDRA_INSTALL_DIR}/support/analyzeHeadless" ]; then
    echo "ERROR: Ghidra installation not found at ${GHIDRA_INSTALL_DIR}"
    echo "Expected: ${GHIDRA_INSTALL_DIR}/support/analyzeHeadless"
    exit 1
fi

# Create workspace directory
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
mkdir -p "${WORKSPACE_DIR}/binaries"
mkdir -p "${WORKSPACE_DIR}/projects"
mkdir -p /tmp/ghidra-project

echo "Workspace: ${WORKSPACE_DIR}"
echo ""

# Check for MCP server script
MCP_SCRIPT=""
if [ -f "/opt/ghidra-mcp-src/mcp_server.py" ]; then
    MCP_SCRIPT="/opt/ghidra-mcp-src/mcp_server.py"
elif [ -f "/opt/ghidra-mcp/mcp_server.py" ]; then
    MCP_SCRIPT="/opt/ghidra-mcp/mcp_server.py"
fi

# Start MCP HTTP server on port 8765
echo "Starting Ghidra MCP HTTP server on port 8765..."

python3 -c "
import http.server
import json
import subprocess
import os
import tempfile
import threading

GHIDRA_PATH = os.environ.get('GHIDRA_INSTALL_DIR', '/opt/ghidra')
ANALYZE = os.path.join(GHIDRA_PATH, 'support', 'analyzeHeadless')
WORKSPACE = '/workspace'

class MCPServer(http.server.HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.analysis_lock = threading.Lock()

class MCPHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self._json_response(200, {
                'status': 'ok',
                'service': 'construct-ghidra-mcp',
                'ghidra_available': os.path.exists(ANALYZE),
                'workspace': WORKSPACE,
            })
        elif self.path == '/':
            self._json_response(200, {
                'service': 'construct-ghidra-mcp',
                'version': '0.1.0',
                'endpoints': ['/health', '/analyze', '/decompile'],
            })
        else:
            self._json_response(404, {'error': 'Not found'})

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json_response(400, {'error': 'Invalid JSON'})
            return

        if self.path == '/analyze':
            self._handle_analyze(data)
        elif self.path == '/decompile':
            self._handle_decompile(data)
        else:
            self._json_response(404, {'error': 'Not found'})

    def _handle_analyze(self, data):
        binary_path = data.get('binary_path', '')
        if not binary_path or not os.path.isfile(binary_path):
            self._json_response(400, {'error': f'Binary not found: {binary_path}'})
            return

        with self.server.analysis_lock:
            project_dir = tempfile.mkdtemp(prefix='ghidra_mcp_')
            try:
                cmd = [
                    ANALYZE,
                    project_dir, 'mcp_project',
                    '-import', binary_path,
                    '-deleteProject',
                    '-postScript', 'ghidra_export.py', os.path.join(project_dir, 'result.json'),
                ]

                env = os.environ.copy()
                env['_JAVA_OPTIONS'] = '-Xmx4g'

                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=600, env=env,
                )

                result_path = os.path.join(project_dir, 'result.json')
                if os.path.exists(result_path):
                    with open(result_path) as f:
                        analysis = json.load(f)
                    self._json_response(200, {'success': True, 'analysis': analysis})
                else:
                    self._json_response(200, {
                        'success': result.returncode == 0,
                        'stdout': result.stdout[-2000:],
                        'stderr': result.stderr[-2000:],
                    })
            except subprocess.TimeoutExpired:
                self._json_response(504, {'error': 'Analysis timed out (600s)'})
            except Exception as e:
                self._json_response(500, {'error': str(e)})
            finally:
                import shutil
                shutil.rmtree(project_dir, ignore_errors=True)

    def _handle_decompile(self, data):
        binary_path = data.get('binary_path', '')
        function_name = data.get('function_name', 'main')
        if not binary_path or not os.path.isfile(binary_path):
            self._json_response(400, {'error': f'Binary not found: {binary_path}'})
            return

        with self.server.analysis_lock:
            project_dir = tempfile.mkdtemp(prefix='ghidra_decompile_')
            try:
                cmd = [
                    ANALYZE,
                    project_dir, 'mcp_decompile',
                    '-import', binary_path,
                    '-deleteProject',
                    '-postScript', 'ghidra_decompile.py', function_name,
                    os.path.join(project_dir, 'decompile_result.json'),
                ]

                env = os.environ.copy()
                env['_JAVA_OPTIONS'] = '-Xmx4g'

                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=300, env=env,
                )

                result_path = os.path.join(project_dir, 'decompile_result.json')
                if os.path.exists(result_path):
                    with open(result_path) as f:
                        decomp = json.load(f)
                    self._json_response(200, {'success': True, 'decompilation': decomp})
                else:
                    self._json_response(200, {
                        'success': False,
                        'stdout': result.stdout[-2000:],
                        'stderr': result.stderr[-2000:],
                    })
            except subprocess.TimeoutExpired:
                self._json_response(504, {'error': 'Decompilation timed out (300s)'})
            except Exception as e:
                self._json_response(500, {'error': str(e)})
            finally:
                import shutil
                shutil.rmtree(project_dir, ignore_errors=True)

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f'[MCP] {args[0]}')

if __name__ == '__main__':
    server = MCPServer(('0.0.0.0', 8765), MCPHandler)
    print('Ghidra MCP server listening on http://0.0.0.0:8765')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down MCP server...')
        server.shutdown()
" &

MCP_PID=$!

# Wait for MCP server to be ready
echo "Waiting for MCP server to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8765/health > /dev/null 2>&1; then
        echo "MCP server is ready!"
        break
    fi
    sleep 1
done

# Keep container running
echo "Ghidra MCP server is running. Press Ctrl+C to stop."
wait $MCP_PID
