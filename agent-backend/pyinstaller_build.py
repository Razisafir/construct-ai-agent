#!/usr/bin/env python3
"""
Build standalone Python sidecar for Tauri desktop app.

Produces a single executable that bundles the entire FastAPI backend
(ChromaDB, sentence-transformers, all ML models) so users don't need
Python installed.

Usage:
    cd agent-backend && python pyinstaller_build.py

Output:
    src/main/bin/agent-backend-<target-triple>[.exe]
"""

from __future__ import annotations

import sys
import os
import platform as plat


def get_target_triple() -> str:
    """Determine Rust-style target triple for current platform."""
    system = plat.system().lower()
    machine = plat.machine().lower()
    
    if system == "windows":
        return "x86_64-pc-windows-msvc"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "aarch64-apple-darwin"
        else:
            return "x86_64-apple-darwin"
    else:  # Linux
        if machine in ("aarch64", "arm64"):
            return "aarch64-unknown-linux-gnu"
        else:
            return "x86_64-unknown-linux-gnu"


def build_sidecar() -> None:
    target = get_target_triple()
    ext = ".exe" if sys.platform == "win32" else ""
    output_name = f"agent-backend-{target}{ext}"
    
    # Output directory (relative to project root)
    dist_path = os.path.join("..", "src", "main", "bin")
    os.makedirs(dist_path, exist_ok=True)
    
    # Build PyInstaller command
    args = [
        os.path.join(os.path.dirname(__file__), "app.py"),
        "--name", output_name,
        "--onefile",
        "--distpath", dist_path,
        "--workpath", os.path.join("..", "build", "pyinstaller"),
        "--specpath", os.path.join("..", "build", "pyinstaller"),
        # Hidden imports for ChromaDB
        "--hidden-import", "chromadb",
        "--hidden-import", "chromadb.config",
        "--hidden-import", "chromadb.telemetry.product.posthog",
        "--hidden-import", "chromadb.db.impl.sqlite",
        "--hidden-import", "chromadb.segment.impl.manager.local",
        "--hidden-import", "chromadb.segment.impl.metadata.sqlite",
        "--hidden-import", "chromadb.segment.impl.vector.local_persistent_hnsw",
        "--hidden-import", "chromadb.api.impl",
        "--hidden-import", "chromadb.quota.simple_quota_enforcer",
        "--hidden-import", "chromadb.rate_limit.simple_rate_limit",
        # Hidden imports for sentence-transformers
        "--hidden-import", "sentence_transformers",
        "--hidden-import", "transformers",
        "--hidden-import", "torch",
        "--hidden-import", "sklearn",
        "--hidden-import", "sklearn.utils._typedefs",
        "--hidden-import", "sklearn.neighbors._partition_nodes",
        "--hidden-import", "sklearn.metrics._pairwise_distances_reduction._datasets_pair",
        "--hidden-import", "sklearn.metrics._pairwise_distances_reduction._middle_term_computer",
        "--hidden-import", "hnswlib",
        "--hidden-import", "numpy",
        "--hidden-import", "scipy",
        "--hidden-import", "tokenizers",
        "--hidden-import", "onnxruntime",
        # Collect packages (use --collect-data instead of --collect-all where possible)
        "--collect-all", "chromadb",
        "--collect-data", "sentence_transformers",
        "--collect-data", "transformers",
        "--hidden-import", "torch.jit",
        "--hidden-import", "torch.nn",
        "--hidden-import", "torch.utils",
        # Exclude unused torch submodules to reduce bundle size
        "--exclude-module", "torch.distributions",
        "--exclude-module", "torch.testing",
        "--exclude-module", "torch.tensorboard",
        "--exclude-module", "torch.benchmark",
        "--exclude-module", "torch.ao",
        "--exclude-module", "torch.export",
        "--exclude-module", "torch._dynamo",
        "--exclude-module", "torch._inductor",
        "--exclude-module", "torch.fx",
        "--exclude-module", "torch.multiprocessing",
        "--collect-data", "tokenizers",
        # Hidden imports for agent roles (PyInstaller can't discover these)
        "--hidden-import", "agents",
        "--hidden-import", "agents.orchestrator",
        "--hidden-import", "agents.roles",
        "--hidden-import", "agents.roles.code_engineer",
        "--hidden-import", "agents.roles.test_engineer",
        "--hidden-import", "agents.roles.security_auditor",
        "--hidden-import", "agents.roles.devops_engineer",
        "--hidden-import", "agents.roles.researcher",
        "--hidden-import", "agents.roles.project_manager",
        "--hidden-import", "agents.roles.legal_reviewer",
        "--hidden-import", "agents.roles.ui_designer",
        # Hidden imports for other backend modules
        "--hidden-import", "core.executor",
        "--hidden-import", "core.llm_service",
        "--hidden-import", "core.agent_session",
        "--hidden-import", "core.safety",
        "--hidden-import", "core.checkpoint",
        "--hidden-import", "core.background_worker",
        "--hidden-import", "core.notifications",
        "--hidden-import", "core.modes",
        "--hidden-import", "core.cache",
        "--hidden-import", "tools",
        "--hidden-import", "tools.file_tools",
        "--hidden-import", "tools.shell_tools",
        "--hidden-import", "tools.git_tools",
        "--hidden-import", "tools.code_tools",
        "--hidden-import", "tools.browser_tools",
        "--hidden-import", "tools.db_tools",
        "--hidden-import", "memory.semantic",
        "--hidden-import", "skills",
        "--hidden-import", "skills.manager",
        "--hidden-import", "mcp",
        "--hidden-import", "mcp.mcp_client",
        "--hidden-import", "mcp.connection_manager",
        # Clean build
        "--clean",
        "--noconfirm",
    ]
    
    # Use console mode for backend (no GUI window)
    args.append("--console")
    
    import PyInstaller.__main__
    PyInstaller.__main__.run(args)
    
    output_path = os.path.join(dist_path, output_name)
    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"Built sidecar: {output_path} ({size_mb:.1f} MB)")
    else:
        print(f"Build failed: {output_path} not found")
        sys.exit(1)


if __name__ == "__main__":
    build_sidecar()
