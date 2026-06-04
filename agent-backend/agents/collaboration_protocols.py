"""Collaboration Protocols — standardized multi-agent interaction patterns.

Protocols:
- **CodeReview**: Agent A writes → Agent B reviews → Agent C tests
- **PairProgramming**: Two agents work on same file simultaneously
- **ArchitectureReview**: All agents review major decisions
- **Emergency**: All agents focus on critical error

Example::

    manager = ProtocolManager()
    result = manager.execute(ProtocolType.CODE_REVIEW, {
        "code": "def hello(): pass",
        "author_agent": "dev-1",
        "reviewer_agent": "senior-1",
        "tester_agent": "qa-1",
    })
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProtocolType(str, Enum):
    """Enumeration of supported collaboration protocols."""

    CODE_REVIEW = "code_review"
    PAIR_PROGRAMMING = "pair_programming"
    ARCHITECTURE_REVIEW = "architecture_review"
    EMERGENCY = "emergency"


@dataclass
class ProtocolResult:
    """Structured result returned by any collaboration protocol.

    Attributes:
        protocol: The protocol that was executed.
        success: Whether the protocol completed successfully.
        stages: Ordered list of stage results.
        final_output: The primary deliverable (e.g. reviewed code, decision).
        agents_involved: IDs of all agents that participated.
        decisions: Key decisions made during the protocol.
        errors: Any errors encountered.
        metrics: Timing and quality metrics.
    """

    protocol: ProtocolType
    success: bool = False
    stages: List[Dict[str, Any]] = field(default_factory=list)
    final_output: Optional[str] = None
    agents_involved: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "protocol": self.protocol.value,
            "success": self.success,
            "stages": self.stages,
            "final_output": self.final_output,
            "agents_involved": self.agents_involved,
            "decisions": self.decisions,
            "errors": self.errors,
            "metrics": self.metrics,
        }


class CollaborationProtocol(ABC):
    """Abstract base class for collaboration protocols.

    Subclasses must override :meth:`execute` and define the specific
    sequence of interactions, decision points, and output format.
    """

    protocol_type: ProtocolType

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> ProtocolResult:
        """Execute the protocol with the given context.

        Args:
            context: Dictionary containing all inputs needed by the
                protocol (agent IDs, code, documents, etc.).

        Returns:
            A :class:`ProtocolResult` summarising the execution.
        """

    def _get_agent(
        self, context: Dict[str, Any], key: str, default: str = "unknown"
    ) -> str:
        """Safely extract an agent ID from the context."""
        agent = context.get(key)
        if not agent:
            logger.warning("Missing agent for key '%s', using default", key)
            return default
        return agent

    def _record_stage(
        self,
        result: ProtocolResult,
        name: str,
        agent: str,
        status: str,
        output: Optional[str] = None,
        decision: Optional[str] = None,
    ) -> None:
        """Append a stage record to the result."""
        stage: Dict[str, Any] = {
            "stage": name,
            "agent": agent,
            "status": status,
            "output": output,
        }
        result.stages.append(stage)
        if decision:
            result.decisions.append(decision)
        if agent not in result.agents_involved:
            result.agents_involved.append(agent)
        logger.debug("Stage '%s' by %s: %s", name, agent, status)


class CodeReviewProtocol(CollaborationProtocol):
    """Write → Review → Test pipeline.

    **Sequence:**

    1. **Write** — *author_agent* produces the initial code.
    2. **Review** — *reviewer_agent* inspects the code for style,
       correctness, and security issues.
    3. **Decision** — if review passes, proceed to test; otherwise
       return to author for revision.
    4. **Test** — *tester_agent* runs the test suite.
    5. **Decision** — if tests pass, protocol succeeds; otherwise
       return to author for fixes.

    **Context keys:**

    - ``"code"`` (*str*): The code to review.
    - ``"author_agent"`` (*str*): ID of the writing agent.
    - ``"reviewer_agent"`` (*str*): ID of the reviewing agent.
    - ``"tester_agent"`` (*str*): ID of the testing agent.
    - ``"test_command"`` (*str*, optional): Command to run tests.
    - ``"max_revisions"`` (*int*, optional): Max review→revision loops
      (default 3).
    """

    protocol_type = ProtocolType.CODE_REVIEW

    def execute(self, context: Dict[str, Any]) -> ProtocolResult:
        """Execute the code review pipeline."""
        result = ProtocolResult(protocol=self.protocol_type)
        author = self._get_agent(context, "author_agent")
        reviewer = self._get_agent(context, "reviewer_agent")
        tester = self._get_agent(context, "tester_agent")
        code: Optional[str] = context.get("code")
        max_revisions: int = context.get("max_revisions", 3)

        if code is None:
            result.errors.append("No code provided for review")
            result.success = False
            return result

        current_code = code
        revision = 0

        self._record_stage(
            result, "write", author, "completed", output=current_code
        )

        while revision < max_revisions:
            # Stage 2: Review
            review_passed, review_feedback = self._simulate_review(
                current_code, reviewer, context
            )
            self._record_stage(
                result,
                f"review_{revision + 1}",
                reviewer,
                "passed" if review_passed else "changes_requested",
                output=review_feedback,
                decision=f"Review {'passed' if review_passed else 'failed'} "
                f"for revision {revision + 1}",
            )

            if not review_passed:
                # Return to author for revision
                current_code, revised = self._simulate_revision(
                    current_code, review_feedback, author
                )
                self._record_stage(
                    result,
                    f"revise_{revision + 1}",
                    author,
                    "completed" if revised else "failed",
                    output=current_code,
                )
                if not revised:
                    result.errors.append(
                        f"Author failed to revise at iteration {revision + 1}"
                    )
                    result.success = False
                    return result
                revision += 1
                continue

            # Stage 4: Test
            tests_passed, test_output = self._simulate_test(
                current_code, tester, context
            )
            self._record_stage(
                result,
                f"test_{revision + 1}",
                tester,
                "passed" if tests_passed else "failed",
                output=test_output,
                decision=f"Tests {'passed' if tests_passed else 'failed'} "
                f"for revision {revision + 1}",
            )

            if tests_passed:
                result.success = True
                result.final_output = current_code
                result.metrics["revisions"] = float(revision)
                return result

            # Tests failed — author must fix
            current_code, fixed = self._simulate_fix(
                current_code, test_output, author
            )
            self._record_stage(
                result,
                f"fix_{revision + 1}",
                author,
                "completed" if fixed else "failed",
                output=current_code,
            )
            if not fixed:
                result.errors.append(
                    f"Author failed to fix test failures at iteration {revision + 1}"
                )
                result.success = False
                return result
            revision += 1

        # Max revisions exceeded
        result.errors.append(f"Max revisions ({max_revisions}) exceeded")
        result.success = False
        result.final_output = current_code
        return result

    @staticmethod
    def _simulate_review(
        code: str, reviewer: str, context: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Simulate the review stage.  Returns (passed, feedback)."""
        # Placeholder: in production, invoke the reviewer agent
        issues: List[str] = []
        if len(code) < 10:
            issues.append("Code is too short")
        if "pass" in code and len(code.splitlines()) < 3:
            issues.append("Placeholder 'pass' detected — needs real implementation")
        if "TODO" in code.upper():
            issues.append("Unresolved TODO found")
        if not issues:
            return True, f"Review by {reviewer}: LGTM, no issues found."
        return False, f"Review by {reviewer}: Issues found: {'; '.join(issues)}"

    @staticmethod
    def _simulate_revision(
        code: str, feedback: str, author: str
    ) -> tuple[str, bool]:
        """Simulate the author revising code.  Returns (new_code, success)."""
        # Placeholder: in production, invoke the author agent
        new_code = code + f"\n# Revised by {author} per review feedback"
        return new_code, True

    @staticmethod
    def _simulate_test(
        code: str, tester: str, context: Dict[str, Any]
    ) -> tuple[bool, str]:
        """Simulate the test stage.  Returns (passed, output)."""
        # Placeholder: in production, run actual tests
        if "error" in code.lower() or "fail" in code.lower():
            return False, f"Tests by {tester}: AssertionError in test_run"
        return True, f"Tests by {tester}: 5 passed, 0 failed"

    @staticmethod
    def _simulate_fix(
        code: str, test_output: str, author: str
    ) -> tuple[str, bool]:
        """Simulate the author fixing test failures.  Returns (new_code, success)."""
        new_code = code + f"\n# Fixed by {author} to address: {test_output[:50]}"
        return new_code, True


class PairProgrammingProtocol(CollaborationProtocol):
    """Two agents collaborate on the same task simultaneously.

    **Sequence:**

    1. **Plan** — Both agents agree on an approach.
    2. **Implement** — *driver_agent* writes code while
       *navigator_agent* reviews in real-time.
    3. **Swap** — Roles swap at configurable intervals.
    4. **Review** — Both agents review the final output.
    5. **Decide** — If both approve, protocol succeeds; otherwise
       iterate.

    **Context keys:**

    - ``"task_description"`` (*str*): What to implement.
    - ``"driver_agent"`` (*str*): ID of the initial driver.
    - ``"navigator_agent"`` (*str*): ID of the initial navigator.
    - ``"swap_interval_minutes"`` (*float*, optional): How often to
      swap roles (default 15.0).
    - ``"max_iterations"`` (*int*, optional): Max refinement loops
      (default 3).
    """

    protocol_type = ProtocolType.PAIR_PROGRAMMING

    def execute(self, context: Dict[str, Any]) -> ProtocolResult:
        """Execute the pair programming protocol."""
        result = ProtocolResult(protocol=self.protocol_type)
        driver = self._get_agent(context, "driver_agent")
        navigator = self._get_agent(context, "navigator_agent")
        task = context.get("task_description", "Unnamed task")
        swap_interval: float = context.get("swap_interval_minutes", 15.0)
        max_iterations: int = context.get("max_iterations", 3)

        # Stage 1: Plan
        plan = f"Plan: Break down '{task}' into functions and data structures"
        self._record_stage(
            result, "plan", driver, "completed", output=plan
        )
        self._record_stage(
            result, "plan_agree", navigator, "completed", decision=f"Both agreed on plan for: {task}"
        )

        current_code = f"# {task}\n# Planned by {driver} and {navigator}\n"
        iteration = 0

        while iteration < max_iterations:
            # Stage 2: Implement (driver writes, navigator reviews)
            code_chunk = self._simulate_implementation(
                current_code, driver, navigator, task
            )
            self._record_stage(
                result,
                f"implement_{iteration + 1}",
                driver,
                "completed",
                output=code_chunk[:100] + "..." if len(code_chunk) > 100 else code_chunk,
            )
            current_code += code_chunk

            # Real-time navigation feedback
            nav_feedback = self._simulate_navigation(code_chunk, navigator)
            self._record_stage(
                result,
                f"navigate_{iteration + 1}",
                navigator,
                "feedback_provided",
                output=nav_feedback,
            )

            # Stage 3: Role swap
            driver, navigator = navigator, driver
            self._record_stage(
                result,
                f"swap_{iteration + 1}",
                f"{driver}/{navigator}",
                "completed",
                decision=f"Roles swapped; new driver is {driver}",
            )

            # Stage 4: Joint review
            review_passed = self._simulate_joint_review(current_code, driver, navigator)
            self._record_stage(
                result,
                f"joint_review_{iteration + 1}",
                f"{driver}+{navigator}",
                "passed" if review_passed else "changes_needed",
                decision=f"Joint review {'passed' if review_passed else 'failed'} "
                f"at iteration {iteration + 1}",
            )

            if review_passed:
                result.success = True
                result.final_output = current_code
                result.metrics["swaps"] = float(iteration + 1)
                result.metrics["swap_interval_minutes"] = swap_interval
                return result

            iteration += 1

        result.errors.append(f"Max iterations ({max_iterations}) reached without agreement")
        result.success = False
        result.final_output = current_code
        return result

    @staticmethod
    def _simulate_implementation(
        existing_code: str, driver: str, navigator: str, task: str
    ) -> str:
        """Simulate the driver writing code."""
        return f"\ndef implement_{driver}():\n    # Driven by {driver}, navigated by {navigator}\n    return '{task}_result'\n"

    @staticmethod
    def _simulate_navigation(code: str, navigator: str) -> str:
        """Simulate the navigator providing feedback."""
        return f"{navigator}: Consider adding type hints and docstrings."

    @staticmethod
    def _simulate_joint_review(code: str, agent_a: str, agent_b: str) -> bool:
        """Simulate both agents reviewing together."""
        # Placeholder: more iterations = higher chance of eventual pass
        return len(code) > 50


class ArchitectureReviewProtocol(CollaborationProtocol):
    """All agents review major architectural decisions.

    **Sequence:**

    1. **Present** — *presenter_agent* describes the proposal.
    2. **Review** — Every *reviewer_agent* evaluates against criteria:
       scalability, maintainability, security, testability.
    3. **Vote** — Each agent votes approve / request_changes / block.
    4. **Decide** — If no blocks and majority approve, protocol
       succeeds; otherwise iterate.
    5. **Document** — Approved decisions are recorded.

    **Context keys:**

    - ``"proposal"`` (*str*): The architectural proposal.
    - ``"presenter_agent"`` (*str*): Agent presenting the proposal.
    - ``"reviewer_agents"`` (*List[str]*): All agents that must review.
    - ``"min_approval_pct"`` (*float*, optional): Minimum approval
      percentage (default 0.6).
    """

    protocol_type = ProtocolType.ARCHITECTURE_REVIEW

    def execute(self, context: Dict[str, Any]) -> ProtocolResult:
        """Execute the architecture review protocol."""
        result = ProtocolResult(protocol=self.protocol_type)
        presenter = self._get_agent(context, "presenter_agent")
        reviewers: List[str] = context.get("reviewer_agents", [])
        proposal: str = context.get("proposal", "No proposal provided")
        min_approval_pct: float = context.get("min_approval_pct", 0.6)

        if not reviewers:
            result.errors.append("No reviewers provided")
            result.success = False
            return result

        # Stage 1: Present
        self._record_stage(
            result,
            "present",
            presenter,
            "completed",
            output=proposal,
        )

        # Stage 2: Individual reviews
        votes: Dict[str, str] = {}  # agent -> vote
        for reviewer in reviewers:
            vote, feedback = self._simulate_individual_review(
                proposal, reviewer
            )
            votes[reviewer] = vote
            self._record_stage(
                result,
                f"review_{reviewer}",
                reviewer,
                vote,
                output=feedback,
            )

        # Stage 3: Tally votes
        total = len(votes)
        approvals = sum(1 for v in votes.values() if v == "approve")
        blocks = sum(1 for v in votes.values() if v == "block")
        approval_pct = approvals / total if total else 0.0

        decision = (
            f"Votes: {approvals} approve, {total - approvals - blocks} request_changes, "
            f"{blocks} block (approval_rate={approval_pct:.0%})"
        )
        result.decisions.append(decision)
        logger.info("Architecture review: %s", decision)

        # Stage 4: Decision
        if blocks > 0:
            result.success = False
            result.errors.append(f"Blocked by {blocks} agent(s)")
            result.metrics["approval_rate"] = approval_pct
            blocking_agents = [a for a, v in votes.items() if v == "block"]
            result.decisions.append(f"Blocked by: {', '.join(blocking_agents)}")
            return result

        if approval_pct >= min_approval_pct:
            result.success = True
            result.final_output = (
                f"APPROVED: {proposal[:100]}...\n"
                f"Approval rate: {approval_pct:.0%}"
            )
        else:
            result.success = False
            result.errors.append(
                f"Approval rate {approval_pct:.0%} below minimum {min_approval_pct:.0%}"
            )
            result.final_output = proposal

        result.metrics["approval_rate"] = approval_pct
        result.metrics["total_reviewers"] = float(total)

        # Stage 5: Document
        if result.success:
            self._record_stage(
                result,
                "document",
                presenter,
                "completed",
                output=f"Decision recorded: APPROVED ({approval_pct:.0%} approval)",
                decision=f"Architecture approved with {approval_pct:.0%} consensus",
            )

        return result

    @staticmethod
    def _simulate_individual_review(
        proposal: str, reviewer: str
    ) -> tuple[str, str]:
        """Simulate a single agent's review.  Returns (vote, feedback)."""
        # Placeholder: in production, invoke each reviewer agent
        proposal_len = len(proposal)
        if proposal_len < 20:
            return "block", f"{reviewer}: Proposal is too vague — needs more detail"
        if "microservice" in proposal.lower() and proposal_len > 200:
            return "approve", f"{reviewer}: Good microservice breakdown, LGTM"
        if "monolith" in proposal.lower():
            return "request_changes", f"{reviewer}: Consider scalability concerns with monolithic approach"
        return "approve", f"{reviewer}: Proposal looks reasonable"


class EmergencyProtocol(CollaborationProtocol):
    """When error rate exceeds threshold, all agents focus on the critical fix.

    **Sequence:**

    1. **Assess** — Evaluate severity of the emergency.
    2. **Mobilise** — All available agents are assigned to the fix.
    3. **Diagnose** — Agents collaboratively identify root cause.
    4. **Fix** — One agent implements; others review in real-time.
    5. **Verify** — All agents confirm the fix.
    6. **Retrospect** — Document what went wrong and how to prevent.

    **Context keys:**

    - ``"error_description"`` (*str*): What went wrong.
    - ``"affected_systems"`` (*List[str]*): Systems impacted.
    - ``"available_agents"`` (*List[str]*): All agents to mobilise.
    - ``"severity"`` (*str*, optional): ``"critical"``, ``"high"``,
      ``"medium"`` (default ``"critical"``).
    """

    protocol_type = ProtocolType.EMERGENCY

    def execute(self, context: Dict[str, Any]) -> ProtocolResult:
        """Execute the emergency response protocol."""
        result = ProtocolResult(protocol=self.protocol_type)
        error_desc: str = context.get("error_description", "Unknown error")
        affected: List[str] = context.get("affected_systems", [])
        agents: List[str] = context.get("available_agents", [])
        severity: str = context.get("severity", "critical")

        if not agents:
            result.errors.append("No agents available for emergency response")
            result.success = False
            return result

        # Stage 1: Assess
        assessment = (
            f"SEVERITY: {severity.upper()} | "
            f"Error: {error_desc} | "
            f"Affected: {', '.join(affected)}"
        )
        self._record_stage(
            result, "assess", "coordinator", "completed", output=assessment
        )
        result.decisions.append(f"Emergency declared: {severity}")

        # Stage 2: Mobilise
        for agent in agents:
            if agent not in result.agents_involved:
                result.agents_involved.append(agent)
        self._record_stage(
            result,
            "mobilise",
            "coordinator",
            "completed",
            output=f"Mobilised {len(agents)} agents: {', '.join(agents)}",
        )

        # Stage 3: Diagnose (collaborative)
        root_cause = self._simulate_diagnosis(error_desc, agents)
        lead_agent = agents[0]
        self._record_stage(
            result,
            "diagnose",
            lead_agent,
            "completed",
            output=root_cause,
            decision=f"Root cause identified: {root_cause[:80]}",
        )

        # Stage 4: Fix (lead implements, others review)
        fix_code = self._simulate_fix(error_desc, root_cause, lead_agent)
        self._record_stage(
            result, "fix", lead_agent, "completed", output=fix_code
        )

        # Collaborative review of fix
        for agent in agents[1:]:
            review_ok = self._simulate_emergency_review(fix_code, agent)
            self._record_stage(
                result,
                f"fix_review_{agent}",
                agent,
                "approved" if review_ok else "concerns",
            )
            if not review_ok:
                result.errors.append(f"{agent} raised concerns about the fix")

        # Stage 5: Verify
        all_verified = self._simulate_verification(fix_code, affected)
        self._record_stage(
            result,
            "verify",
            "all_agents",
            "passed" if all_verified else "failed",
            output="All systems operational" if all_verified else "Verification failed",
        )

        # Stage 6: Retrospect
        retro = self._simulate_retrospective(error_desc, root_cause, agents)
        self._record_stage(
            result,
            "retrospect",
            "coordinator",
            "completed",
            output=retro,
            decision="Post-mortem documented",
        )

        result.success = all_verified
        result.final_output = fix_code
        result.metrics["agents_mobilized"] = float(len(agents))
        result.metrics["severity_score"] = {"critical": 1.0, "high": 0.7, "medium": 0.4}.get(severity, 0.5)
        return result

    @staticmethod
    def _simulate_diagnosis(error: str, agents: List[str]) -> str:
        """Simulate collaborative root cause analysis."""
        return f"Root cause of '{error[:40]}...': Race condition in async handler (diagnosed by {', '.join(agents[:2])})"

    @staticmethod
    def _simulate_fix(error: str, root_cause: str, agent: str) -> str:
        """Simulate implementing the emergency fix."""
        return f"# Emergency fix by {agent}\n# Issue: {error[:30]}...\nasync def patched_handler():\n    async with lock:\n        return safe_result\n"

    @staticmethod
    def _simulate_emergency_review(fix: str, reviewer: str) -> bool:
        """Simulate rapid review during emergency."""
        return "patched" in fix.lower() or "fix" in fix.lower()

    @staticmethod
    def _simulate_verification(fix: str, affected: List[str]) -> bool:
        """Simulate post-fix verification."""
        return bool(fix) and len(affected) > 0

    @staticmethod
    def _simulate_retrospective(error: str, root_cause: str, agents: List[str]) -> str:
        """Simulate post-mortem documentation."""
        return (
            f"Post-mortem: Error '{error[:30]}...' caused by {root_cause[:40]}. "
            f"Reviewed by {len(agents)} agents. Action items: add tests, improve monitoring."
        )


class ProtocolManager:
    """Manages and executes collaboration protocols.

    The manager is a registry of all available protocols.  It can
    execute a protocol by type and auto-detect which protocol applies
    to a given situation.

    Attributes:
        _protocols: Mapping from :class:`ProtocolType` to protocol
            instances.
    """

    def __init__(self) -> None:
        self._protocols: Dict[ProtocolType, CollaborationProtocol] = {
            ProtocolType.CODE_REVIEW: CodeReviewProtocol(),
            ProtocolType.PAIR_PROGRAMMING: PairProgrammingProtocol(),
            ProtocolType.ARCHITECTURE_REVIEW: ArchitectureReviewProtocol(),
            ProtocolType.EMERGENCY: EmergencyProtocol(),
        }
        logger.info(
            "ProtocolManager initialized with %d protocols",
            len(self._protocols),
        )

    def execute(
        self, protocol: ProtocolType, context: Dict[str, Any]
    ) -> ProtocolResult:
        """Execute a collaboration protocol.

        Args:
            protocol: The protocol type to run.
            context: Input data for the protocol.

        Returns:
            A :class:`ProtocolResult` with full execution details.

        Raises:
            ValueError: If the protocol type is not registered.
        """
        if protocol not in self._protocols:
            raise ValueError(f"Unknown protocol: {protocol.value}")

        logger.info("Executing protocol %s", protocol.value)
        start_time = __import__("time").time()
        result = self._protocols[protocol].execute(context)
        elapsed = (__import__("time").time() - start_time) * 1000
        result.metrics["protocol_execution_ms"] = round(elapsed, 2)

        logger.info(
            "Protocol %s finished: success=%s, stages=%d, agents=%s",
            protocol.value,
            result.success,
            len(result.stages),
            result.agents_involved,
        )
        return result

    def detect_protocol(
        self, situation: Dict[str, Any]
    ) -> Optional[ProtocolType]:
        """Auto-detect which protocol applies to a situation.

        Heuristic rules:

        - Emergency: ``error_rate`` > 0.2 or ``severity`` is
          ``"critical"``.
        - ArchitectureReview: ``affected_systems`` > 2 or
          ``is_architectural_decision`` is ``True``.
        - CodeReview: ``code`` is present and ``reviewer_agent`` is
          specified.
        - PairProgramming: ``task_description`` is present and exactly
          2 agents are specified.

        Args:
            situation: Dictionary describing the current situation.

        Returns:
            The best matching :class:`ProtocolType`, or ``None``.
        """
        error_rate = situation.get("error_rate", 0.0)
        severity = situation.get("severity", "")
        is_architectural = situation.get("is_architectural_decision", False)
        affected_systems = situation.get("affected_systems", [])
        has_code = "code" in situation
        has_reviewer = "reviewer_agent" in situation
        has_task = "task_description" in situation
        agent_count = len(situation.get("agents", []))

        # Priority: emergency first
        if error_rate > 0.2 or severity == "critical":
            logger.info(
                "Detected emergency situation (error_rate=%.2f, severity=%s)",
                error_rate,
                severity,
            )
            return ProtocolType.EMERGENCY

        # Architecture review
        if is_architectural or len(affected_systems) > 2:
            logger.info("Detected architecture review situation")
            return ProtocolType.ARCHITECTURE_REVIEW

        # Code review
        if has_code and has_reviewer:
            logger.info("Detected code review situation")
            return ProtocolType.CODE_REVIEW

        # Pair programming
        if has_task and agent_count == 2:
            logger.info("Detected pair programming situation")
            return ProtocolType.PAIR_PROGRAMMING

        # Fallback: if code present but no reviewer, assume code review
        if has_code:
            logger.info("Fallback: code review (code present)")
            return ProtocolType.CODE_REVIEW

        # Default: architecture review for ambiguous situations
        if has_task:
            logger.info("Fallback: architecture review (task present)")
            return ProtocolType.ARCHITECTURE_REVIEW

        logger.warning("Could not detect suitable protocol for situation")
        return None

    def list_protocols(self) -> List[str]:
        """Return a list of available protocol type names."""
        return sorted(p.value for p in self._protocols.keys())

    def register_protocol(
        self, protocol_type: ProtocolType, protocol: CollaborationProtocol
    ) -> None:
        """Register a custom protocol implementation.

        Args:
            protocol_type: The type key for the protocol.
            protocol: The protocol instance.
        """
        self._protocols[protocol_type] = protocol
        logger.info("Registered custom protocol: %s", protocol_type.value)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Demonstrate all collaboration protocols."""
    manager = ProtocolManager()

    print(f"Available protocols: {manager.list_protocols()}\n")

    # 1. Code Review
    print("=" * 60)
    print("1. CODE REVIEW PROTOCOL")
    print("=" * 60)
    cr_result = manager.execute(ProtocolType.CODE_REVIEW, {
        "code": "def hello():\n    pass",
        "author_agent": "dev-1",
        "reviewer_agent": "senior-1",
        "tester_agent": "qa-1",
        "max_revisions": 2,
    })
    print(f"Success: {cr_result.success}")
    print(f"Stages: {len(cr_result.stages)}")
    for s in cr_result.stages:
        print(f"  [{s['stage']}] {s['agent']}: {s['status']}")
    print(f"Decisions: {cr_result.decisions}")
    if cr_result.errors:
        print(f"Errors: {cr_result.errors}")

    # 2. Pair Programming
    print("\n" + "=" * 60)
    print("2. PAIR PROGRAMMING PROTOCOL")
    print("=" * 60)
    pp_result = manager.execute(ProtocolType.PAIR_PROGRAMMING, {
        "task_description": "Implement user authentication",
        "driver_agent": "dev-1",
        "navigator_agent": "dev-2",
        "max_iterations": 2,
    })
    print(f"Success: {pp_result.success}")
    print(f"Agents involved: {pp_result.agents_involved}")
    for s in pp_result.stages:
        print(f"  [{s['stage']}] {s['agent']}: {s['status']}")

    # 3. Architecture Review
    print("\n" + "=" * 60)
    print("3. ARCHITECTURE REVIEW PROTOCOL")
    print("=" * 60)
    ar_result = manager.execute(ProtocolType.ARCHITECTURE_REVIEW, {
        "proposal": "Migrate to microservices with API gateway, "
                    "service mesh for inter-service communication, "
                    "and event-driven architecture for async processing. "
                    "Each service will have its own database to ensure loose coupling. "
                    "Kubernetes will orchestrate container deployments.",
        "presenter_agent": "arch-1",
        "reviewer_agents": ["dev-1", "dev-2", "sec-1", "ops-1"],
        "min_approval_pct": 0.6,
    })
    print(f"Success: {ar_result.success}")
    print(f"Approval rate: {ar_result.metrics.get('approval_rate', 0):.0%}")
    for s in ar_result.stages:
        print(f"  [{s['stage']}] {s['agent']}: {s['status']}")
    print(f"Decisions: {ar_result.decisions}")

    # 4. Emergency
    print("\n" + "=" * 60)
    print("4. EMERGENCY PROTOCOL")
    print("=" * 60)
    em_result = manager.execute(ProtocolType.EMERGENCY, {
        "error_description": "Database connection pool exhausted, "
                             "all requests timing out",
        "affected_systems": ["api", "auth", "payments"],
        "available_agents": ["dev-1", "dev-2", "ops-1", "sec-1"],
        "severity": "critical",
    })
    print(f"Success: {em_result.success}")
    print(f"Agents mobilized: {int(em_result.metrics.get('agents_mobilized', 0))}")
    for s in em_result.stages:
        print(f"  [{s['stage']}] {s['agent']}: {s['status']}")

    # 5. Auto-detection
    print("\n" + "=" * 60)
    print("5. PROTOCOL AUTO-DETECTION")
    print("=" * 60)
    situations = [
        {"error_rate": 0.35, "severity": "critical"},
        {"code": "x = 1", "reviewer_agent": "senior-1"},
        {"task_description": "Refactor login", "agents": ["a", "b"]},
        {"is_architectural_decision": True, "affected_systems": ["db", "api", "cache"]},
    ]
    for s in situations:
        detected = manager.detect_protocol(s)
        print(f"  Situation: {s}")
        print(f"  Detected:  {detected.value if detected else 'None'}\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print("=" * 60)
    print("Collaboration Protocols Demo")
    print("=" * 60)
    _demo()
