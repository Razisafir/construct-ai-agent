"""Git automation toolkit for the agent backend.

Modules:
    commit_generator   — LLM + rule-based conventional commit generation
    branch_manager     — automated branch lifecycle management
    precommit_pipeline — pre-commit checks (tests, lint, types, security)
"""

from __future__ import annotations

from git.commit_generator import (
    CommitMessageGenerator,
    CommitSuggestion,
    CommitType,
)
from git.branch_manager import (
    BranchManager,
    BranchStatus,
)
from git.precommit_pipeline import (
    CheckResult,
    CheckStatus,
    PipelineResult,
    PreCommitPipeline,
)

__all__ = [
    "CommitMessageGenerator",
    "CommitSuggestion",
    "CommitType",
    "BranchManager",
    "BranchStatus",
    "CheckResult",
    "CheckStatus",
    "PipelineResult",
    "PreCommitPipeline",
]
