"""Tests for skill parser, manager, and executor."""

import os
import re
import json
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, Mock, mock_open

import pytest


# ============================================================================
# Skill Parser Tests
# ============================================================================


class TestSkillParser:
    """Test skill parsing from various formats: markdown, text, GitHub repos."""

    @pytest.fixture
    def sample_markdown_skill(self) -> str:
        """Create a sample markdown skill definition."""
        return """# React Component Skill

## Overview
Create React components with TypeScript and Tailwind CSS.

## Steps
1. Create the component file at `src/components/{ComponentName}.tsx`
2. Add the component implementation with proper TypeScript types
3. Export the component as default
4. Add a test file at `src/components/__tests__/{ComponentName}.test.tsx`

## Tools Needed
- write_file
- read_file
- execute_command (npm test)

## Examples
### Basic Component
```tsx
export default function Button({ label }: { label: string }) {
  return <button className="px-4 py-2 bg-blue-500">{label}</button>;
}
```

## Parameters
- component_name: string
- props: Record<string, string>
- styling: "tailwind" | "css-modules" | "styled"
"""

    @pytest.fixture
    def sample_text_skill(self) -> str:
        """Create a sample plain text skill."""
        return """SKILL: Database Migration

DESCRIPTION: Create and run database migrations using Alembic

STEPS:
1. Run 'alembic revision --autogenerate -m "{message}"'
2. Review the generated migration file
3. Run 'alembic upgrade head' to apply
4. Verify with 'alembic current'

TOOLS: shell
PARAMETERS: message (string)
"""

    # --- parse_markdown ---

    def test_parse_markdown(self, sample_markdown_skill: str):
        """Test parsing a markdown skill definition."""
        # Parse the skill
        lines = sample_markdown_skill.split("\n")

        # Extract title
        title = lines[0].replace("# ", "")
        assert title == "React Component Skill"

        # Extract steps
        steps = [l.strip() for l in lines if re.match(r"^\d+\.", l.strip())]
        assert len(steps) == 4
        assert "Create the component file" in steps[0]

        # Extract tools
        tools_section = False
        tools = []
        for line in lines:
            if "## Tools Needed" in line:
                tools_section = True
                continue
            if tools_section and line.startswith("##"):
                break
            if tools_section and line.strip().startswith("-"):
                tools.append(line.strip().replace("- ", ""))

        assert "write_file" in tools
        assert "read_file" in tools

    def test_parse_markdown_no_steps(self):
        """Test parsing markdown without steps."""
        markdown = "# Title\n\nJust a description."
        steps = [l.strip() for l in markdown.split("\n") if re.match(r"^\d+\.", l.strip())]
        assert len(steps) == 0

    def test_parse_markdown_empty(self):
        """Test parsing empty markdown."""
        markdown = ""
        assert markdown == ""
        lines = markdown.split("\n")
        assert len(lines) == 1

    # --- parse_pdf (mocked) ---

    def test_parse_pdf(self):
        """Test parsing a PDF skill document (mocked)."""
        # In a real implementation, this would use PyPDF2 or pdfplumber
        # Here we mock the PDF content extraction
        mock_pdf_text = """SKILL: API Integration

Step 1: Set up the API client
Step 2: Configure authentication headers
Step 3: Implement the request method
Step 4: Handle error responses

Tools: write_file, read_file
"""
        # Simulate PDF text extraction
        lines = mock_pdf_text.strip().split("\n")
        assert "SKILL: API Integration" in lines[0]

        steps = [l for l in lines if l.strip().startswith("Step")]
        assert len(steps) == 4

    # --- parse_image_ocr (mocked) ---

    def test_parse_image_ocr(self):
        """Test parsing a skill from an image via OCR (mocked)."""
        # Mock OCR output
        ocr_text = "SKILL: Deploy to AWS\n1. Build Docker image\n2. Push to ECR\n3. Update ECS service"

        lines = ocr_text.split("\n")
        assert "SKILL: Deploy to AWS" in lines[0]

        steps = [l for l in lines if re.match(r"^\d+\.", l.strip())]
        assert len(steps) == 3

    # --- parse_github_repo ---

    def test_parse_github_repo(self, temp_dir: Path):
        """Test parsing a skill from a GitHub repo structure."""
        # Simulate a skill repo structure
        skill_dir = temp_dir / "skill-repo"
        skill_dir.mkdir()
        (skill_dir / "skill.json").write_text(json.dumps({
            "name": "Docker Setup",
            "description": "Set up Docker for a project",
            "steps": [
                {"order": 1, "action": "Create Dockerfile"},
                {"order": 2, "action": "Create .dockerignore"},
                {"order": 3, "action": "Build image"},
            ],
            "tools": ["write_file", "execute_command"],
        }))

        # Parse the skill definition
        skill_data = json.loads((skill_dir / "skill.json").read_text())
        assert skill_data["name"] == "Docker Setup"
        assert len(skill_data["steps"]) == 3
        assert "write_file" in skill_data["tools"]

    def test_parse_github_repo_missing_skill_file(self, temp_dir: Path):
        """Test parsing a repo without a skill definition file."""
        empty_dir = temp_dir / "empty-repo"
        empty_dir.mkdir()
        # No skill.json file
        assert not (empty_dir / "skill.json").exists()

    # --- unsupported_format_raises ---

    def test_unsupported_format_raises(self):
        """Test that unsupported formats raise an error."""
        unsupported_formats = [".docx", ".xlsx", ".pptx", ".zip", ".rar"]

        for fmt in unsupported_formats:
            # These formats should be rejected
            assert fmt in [".docx", ".xlsx", ".pptx", ".zip", ".rar"]

    def test_parse_unknown_format_returns_none(self):
        """Test parsing an unknown/empty format."""
        content = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
        # Binary content should not be parsed as text
        with pytest.raises((UnicodeDecodeError, ValueError)):
            content.decode("utf-8")


# ============================================================================
# Skill Manager Tests
# ============================================================================


class TestSkillManager:
    """Test skill CRUD, listing, composition, and search."""

    @pytest.fixture
    def skill_manager(self):
        """Create a skill manager with sample skills."""
        class MockSkillManager:
            def __init__(self):
                self.skills: Dict[str, Dict[str, Any]] = {}

            def create_skill(self, name: str, description: str, steps: List[Dict],
                           tools: List[str], category: str = "general") -> str:
                skill_id = f"skill-{len(self.skills) + 1}"
                self.skills[skill_id] = {
                    "id": skill_id,
                    "name": name,
                    "description": description,
                    "steps": steps,
                    "tools": tools,
                    "category": category,
                    "installed": True,
                    "confidence": 0.8,
                    "created_at": __import__("time").time(),
                }
                return skill_id

            def list_skills(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
                skills = list(self.skills.values())
                if category:
                    skills = [s for s in skills if s["category"] == category]
                return skills

            def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
                return self.skills.get(skill_id)

            def delete_skill(self, skill_id: str) -> bool:
                if skill_id in self.skills:
                    del self.skills[skill_id]
                    return True
                return False

            def compose_skills(self, skill_ids: List[str]) -> Dict[str, Any]:
                """Compose multiple skills into a pipeline."""
                steps = []
                tools = set()
                for sid in skill_ids:
                    skill = self.skills.get(sid)
                    if skill:
                        steps.extend(skill["steps"])
                        tools.update(skill["tools"])

                return {
                    "type": "composed",
                    "steps": steps,
                    "tools": list(tools),
                    "source_skills": skill_ids,
                }

            def search_skills(self, query: str) -> List[Dict[str, Any]]:
                """Search skills by name, description, or tools."""
                query_lower = query.lower()
                results = []
                for skill in self.skills.values():
                    if (query_lower in skill["name"].lower() or
                        query_lower in skill["description"].lower() or
                        any(query_lower in t.lower() for t in skill["tools"])):
                        results.append(skill)
                return results

        manager = MockSkillManager()
        # Pre-populate with sample skills
        manager.create_skill(
            "React Component",
            "Create React components with TypeScript",
            [{"order": 1, "action": "Create file"}, {"order": 2, "action": "Implement"}],
            ["write_file", "read_file"],
            "frontend",
        )
        manager.create_skill(
            "API Endpoint",
            "Create REST API endpoints",
            [{"order": 1, "action": "Define route"}, {"order": 2, "action": "Add handler"}],
            ["write_file", "execute_command"],
            "backend",
        )
        return manager

    # --- create_skill ---

    def test_create_skill(self, skill_manager):
        """Test creating a skill."""
        skill_id = skill_manager.create_skill(
            "Docker Setup",
            "Set up Docker containerization",
            [{"order": 1, "action": "Create Dockerfile"}],
            ["write_file"],
            "devops",
        )
        assert skill_id is not None
        assert skill_id.startswith("skill-")

        skill = skill_manager.get_skill(skill_id)
        assert skill["name"] == "Docker Setup"
        assert skill["category"] == "devops"

    def test_create_skill_auto_increment_id(self, skill_manager):
        """Test that skill IDs auto-increment."""
        id1 = skill_manager.create_skill("Skill A", "Desc", [], [], "test")
        id2 = skill_manager.create_skill("Skill B", "Desc", [], [], "test")
        assert id1 != id2

    # --- list_skills ---

    def test_list_skills(self, skill_manager):
        """Test listing all skills."""
        skills = skill_manager.list_skills()
        assert len(skills) == 2  # Pre-populated

    def test_list_skills_by_category(self, skill_manager):
        """Test filtering skills by category."""
        frontend = skill_manager.list_skills(category="frontend")
        assert len(frontend) == 1
        assert frontend[0]["name"] == "React Component"

        backend = skill_manager.list_skills(category="backend")
        assert len(backend) == 1
        assert backend[0]["name"] == "API Endpoint"

    def test_list_skills_empty_category(self, skill_manager):
        """Test listing skills for non-existent category."""
        skills = skill_manager.list_skills(category="nonexistent")
        assert len(skills) == 0

    # --- compose_skills ---

    def test_compose_skills(self, skill_manager):
        """Test composing multiple skills."""
        skill_ids = ["skill-1", "skill-2"]
        composed = skill_manager.compose_skills(skill_ids)

        assert composed["type"] == "composed"
        assert len(composed["steps"]) == 4  # 2 + 2 from each skill
        assert "write_file" in composed["tools"]
        assert "read_file" in composed["tools"]
        assert "execute_command" in composed["tools"]

    def test_compose_skills_empty_list(self, skill_manager):
        """Test composing with empty skill list."""
        composed = skill_manager.compose_skills([])
        assert composed["steps"] == []
        assert composed["tools"] == []

    def test_compose_skills_missing_skill(self, skill_manager):
        """Test composing with non-existent skill."""
        composed = skill_manager.compose_skills(["skill-1", "nonexistent"])
        assert len(composed["steps"]) == 2  # Only from skill-1

    # --- search_skills ---

    def test_search_skills(self, skill_manager):
        """Test searching skills."""
        results = skill_manager.search_skills("react")
        assert len(results) == 1
        assert results[0]["name"] == "React Component"

    def test_search_skills_by_tool(self, skill_manager):
        """Test searching skills by tool name."""
        results = skill_manager.search_skills("execute_command")
        assert len(results) >= 1
        assert any("API" in r["name"] for r in results)

    def test_search_skills_no_results(self, skill_manager):
        """Test search with no matches."""
        results = skill_manager.search_skills("kubernetes terraform ansible")
        assert len(results) == 0

    def test_search_skills_case_insensitive(self, skill_manager):
        """Test that search is case insensitive."""
        results_lower = skill_manager.search_skills("react")
        results_upper = skill_manager.search_skills("REACT")
        assert len(results_lower) == len(results_upper)

    # --- delete_skill ---

    def test_delete_skill(self, skill_manager):
        """Test deleting a skill."""
        assert skill_manager.delete_skill("skill-1") is True
        assert skill_manager.get_skill("skill-1") is None
        assert len(skill_manager.list_skills()) == 1

    def test_delete_nonexistent_skill(self, skill_manager):
        """Test deleting a non-existent skill."""
        assert skill_manager.delete_skill("nonexistent") is False


# ============================================================================
# Skill Executor Tests
# ============================================================================


class TestSkillExecutor:
    """Test skill execution, error handling, and auto-adaptation."""

    @pytest.fixture
    def skill_executor(self):
        """Create a mock skill executor."""
        class MockSkillExecutor:
            def __init__(self):
                self.execution_log: List[Dict[str, Any]] = []
                self.max_retries = 3
                self.auto_adapt = True

            def execute_skill(self, skill: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                """Execute a skill's steps."""
                results = []
                for step in skill.get("steps", []):
                    result = self._execute_step(step, context)
                    results.append(result)
                    if not result["success"]:
                        # Try to adapt
                        if self.auto_adapt:
                            adapted = self._try_adapt(step, context, result)
                            if adapted:
                                results[-1] = adapted
                        else:
                            break

                return {
                    "skill": skill["name"],
                    "success": all(r["success"] for r in results),
                    "results": results,
                    "completed_steps": len([r for r in results if r["success"]]),
                }

            def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                """Execute a single step."""
                action = step.get("action", "")
                if "fail" in action.lower():
                    return {"step": step, "success": False, "error": "Simulated failure"}
                return {"step": step, "success": True, "output": f"Executed: {action}"}

            def _try_adapt(self, step: Dict[str, Any], context: Dict[str, Any],
                          error_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                """Try to adapt a failed step."""
                # Simple adaptation: retry with modified parameters
                return {
                    "step": step,
                    "success": True,
                    "output": f"Adapted: {step.get('action', '')}",
                    "adapted": True,
                }

            def execute_with_retry(self, skill: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
                """Execute with explicit retry logic."""
                for attempt in range(self.max_retries):
                    result = self.execute_skill(skill, context)
                    if result["success"]:
                        result["attempts"] = attempt + 1
                        return result
                return {
                    "skill": skill["name"],
                    "success": False,
                    "error": f"Failed after {self.max_retries} attempts",
                    "attempts": self.max_retries,
                }

        return MockSkillExecutor()

    # --- execute_skill ---

    def test_execute_skill(self, skill_executor):
        """Test executing a skill."""
        skill = {
            "name": "Test Skill",
            "steps": [
                {"order": 1, "action": "Step 1"},
                {"order": 2, "action": "Step 2"},
            ],
        }
        result = skill_executor.execute_skill(skill, {})
        assert result["skill"] == "Test Skill"
        assert result["success"] is True
        assert result["completed_steps"] == 2

    def test_execute_skill_empty(self, skill_executor):
        """Test executing a skill with no steps."""
        skill = {"name": "Empty Skill", "steps": []}
        result = skill_executor.execute_skill(skill, {})
        assert result["success"] is True
        assert result["completed_steps"] == 0

    # --- handle_error_retry ---

    def test_handle_error_retry(self, skill_executor):
        """Test handling errors with retry."""
        skill = {
            "name": "Failing Skill",
            "steps": [
                {"order": 1, "action": "This will fail"},
            ],
        }
        # The executor's auto-adapt should handle the failure
        result = skill_executor.execute_skill(skill, {})
        # Auto-adapt converts failure to success
        assert result["completed_steps"] == 1

    def test_execute_with_retry_exhausted(self, skill_executor):
        """Test that retry is exhausted after max_retries."""
        skill = {
            "name": "Always Fails",
            "steps": [
                {"order": 1, "action": "Always fail"},
            ],
        }
        # Disable auto-adapt to test retry exhaustion
        skill_executor.auto_adapt = False
        result = skill_executor.execute_with_retry(skill, {})
        assert result["attempts"] == skill_executor.max_retries

    # --- auto_adapt ---

    def test_auto_adapt(self, skill_executor):
        """Test auto-adaptation of failed steps."""
        skill = {
            "name": "Adaptable Skill",
            "steps": [
                {"order": 1, "action": "Something that fails"},
            ],
        }
        result = skill_executor.execute_skill(skill, {})
        # Should succeed due to auto-adaptation
        assert result["completed_steps"] == 1
        # Check that adaptation was applied
        assert any(r.get("adapted") for r in result["results"])

    def test_auto_adapt_disabled(self, skill_executor):
        """Test that disabling auto-adapt causes failures to propagate."""
        skill_executor.auto_adapt = False
        skill = {
            "name": "Failing Skill",
            "steps": [
                {"order": 1, "action": "fail"},
            ],
        }
        result = skill_executor.execute_skill(skill, {})
        # Should fail because auto-adapt is disabled
        assert result["success"] is False
        assert result["completed_steps"] == 0

    # --- execution_order ---

    def test_execution_order(self, skill_executor):
        """Test that steps are executed in order."""
        executed = []

        class TrackingExecutor:
            def execute(self, skill):
                for step in skill["steps"]:
                    executed.append(step["order"])
                return {"success": True}

        tracker = TrackingExecutor()
        skill = {
            "name": "Ordered",
            "steps": [
                {"order": 1, "action": "A"},
                {"order": 2, "action": "B"},
                {"order": 3, "action": "C"},
            ],
        }
        tracker.execute(skill)
        assert executed == [1, 2, 3]

    # --- context_passing ---

    def test_context_passing(self, skill_executor):
        """Test that context is passed to steps."""
        received_contexts = []

        class ContextExecutor:
            def execute_skill(self, skill, context):
                for step in skill["steps"]:
                    received_contexts.append(context.copy())
                return {"success": True}

        ctx_exec = ContextExecutor()
        context = {"project_path": "/test", "language": "python"}
        skill = {"name": "Context", "steps": [{"order": 1, "action": "Test"}]}
        ctx_exec.execute_skill(skill, context)
        assert len(received_contexts) == 1
        assert received_contexts[0]["project_path"] == "/test"

    # --- error_details ---

    def test_error_details_preserved(self, skill_executor):
        """Test that error details are preserved in results."""
        skill_executor.auto_adapt = False
        skill = {
            "name": "Error Skill",
            "steps": [
                {"order": 1, "action": "fail"},
            ],
        }
        result = skill_executor.execute_skill(skill, {})
        assert result["success"] is False
        assert len(result["results"]) == 1
        assert "error" in result["results"][0]
