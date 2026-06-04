#!/usr/bin/env python3
"""
Skill Installer — Install skills from GitHub, URLs, or local files.

Usage:
    from skills.installer import SkillInstaller
    installer = SkillInstaller()
    installer.install_from_github("addyosmani", "agent-skills", "spec-driven-development")
    installer.list_installed()
    installer.uninstall_skill("spec-driven-development")

Architecture:
    - Bundled skills: ``resources/skills/bundled/`` (read-only, shipped with the agent)
    - Installed skills: ``resources/skills/installed/`` (mutable, user-installed)
    - Each skill is a directory containing a ``SKILL.md`` file with YAML frontmatter.
"""

from __future__ import annotations

__all__ = ["Skill", "InstallSource", "SkillInstaller", "SkillInstallError", "SkillNotFoundError"]

import enum
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Protocol, Union

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_DIR = DEFAULT_PROJECT_ROOT / "resources" / "skills" / "bundled"
INSTALLED_DIR = DEFAULT_PROJECT_ROOT / "resources" / "skills" / "installed"
SKILL_FILENAME = "SKILL.md"

# Regex that matches YAML frontmatter inside --- fences.
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SkillInstallError(Exception):
    """Raised when a skill installation fails."""

    def __init__(self, message: str, source: Optional[str] = None) -> None:
        self.source = source
        super().__init__(f"{message}" + (f" (source: {source})" if source else ""))


class SkillNotFoundError(Exception):
    """Raised when a requested skill cannot be found."""

    def __init__(self, skill_name: str) -> None:
        self.skill_name = skill_name
        super().__init__(f"Skill not found: {skill_name}")


# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------

class InstallSource(enum.Enum):
    """Enumeration of supported skill installation sources."""

    BUNDLED = "bundled"          # Shipped with the agent (read-only)
    GITHUB = "github"            # Cloned from a GitHub repository
    URL = "url"                  # Downloaded from an arbitrary URL
    LOCAL = "local"              # Installed from a local file/directory


@dataclass(frozen=True)
class Skill:
    """Immutable representation of an installed skill.

    Attributes:
        name: Machine-friendly skill identifier (e.g. ``spec-driven-development``).
        version: Semantic version string.
        category: Broad classification (coding, design, research, devops, security, testing).
        description: Human-readable one-line summary.
        author: Skill author or organization.
        tools_needed: Tools the skill expects the agent to have available.
        confidence: Default confidence score (0.0 – 1.0).
        source: Where the skill came from.
        installed_at: ISO-8601 timestamp of installation.
        path: Absolute filesystem path to the skill directory.
        raw_frontmatter: Parsed YAML frontmatter as a dict.
        raw_body: Markdown body (everything after the frontmatter).
    """

    name: str
    version: str
    category: str
    description: str
    author: str = "Construct AI"
    tools_needed: List[str] = field(default_factory=list)
    confidence: float = 0.95
    source: InstallSource = InstallSource.BUNDLED
    installed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    path: Path = field(default_factory=lambda: Path("."))
    raw_frontmatter: Dict[str, Any] = field(default_factory=dict, repr=False)
    raw_body: str = field(default="", repr=False)

    @property
    def skill_md_path(self) -> Path:
        """Return the path to the SKILL.md file."""
        return self.path / SKILL_FILENAME

    @property
    def is_bundled(self) -> bool:
        """Whether this skill is a bundled (read-only) skill."""
        return self.source == InstallSource.BUNDLED

    def read_content(self) -> str:
        """Read the full SKILL.md file contents."""
        try:
            return self.skill_md_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SkillNotFoundError(self.name) from exc

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the skill to a dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "tools_needed": self.tools_needed,
            "confidence": self.confidence,
            "source": self.source.value,
            "installed_at": self.installed_at,
            "path": str(self.path),
        }

    def __repr__(self) -> str:
        return (
            f"<Skill {self.name}@{self.version} "
            f"category={self.category} source={self.source.value}>"
        )


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

class SkillInstaller:
    """Install, manage, and discover skills for the Construct AI agent.

    Skills can come from three sources:
    1. **Bundled** — read-only skills shipped with the agent.
    2. **GitHub** — cloned from a public or private GitHub repository.
    3. **URL** — downloaded directly from an arbitrary HTTP(S) URL.

    All installed (non-bundled) skills are stored under
    ``resources/skills/installed/`` and can be updated or removed independently.

    Example::

        installer = SkillInstaller()

        # Install from GitHub
        skill = installer.install_from_github("org", "repo", "my-skill")

        # Install from URL
        skill = installer.install_from_url("https://example.com/skills/my-skill.md")

        # List what is available
        bundled = installer.list_bundled()
        installed = installer.list_installed()

        # Upgrade
        updated = installer.update_skill("my-skill")

        # Remove
        installer.uninstall_skill("my-skill")
    """

    def __init__(
        self,
        bundled_dir: Optional[Union[str, Path]] = None,
        installed_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        self.bundled_dir = Path(bundled_dir or BUNDLED_DIR)
        self.installed_dir = Path(installed_dir or INSTALLED_DIR)
        self._ensure_directories()

    # -- internal helpers --------------------------------------------------

    def _ensure_directories(self) -> None:
        """Ensure that the bundled and installed directories exist."""
        self.bundled_dir.mkdir(parents=True, exist_ok=True)
        self.installed_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("SkillInstaller initialized: bundled=%s, installed=%s",
                     self.bundled_dir, self.installed_dir)

    @staticmethod
    def _run_git(*args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
        """Run a git command and return the result."""
        cmd = ["git", *args]
        logger.debug("Running: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            return result
        except subprocess.CalledProcessError as exc:
            raise SkillInstallError(
                f"Git command failed: {exc.stderr.strip()}",
                source=" ".join(cmd),
            ) from exc
        except FileNotFoundError as exc:
            raise SkillInstallError(
                "Git is not installed or not in PATH. Please install git."
            ) from exc

    # -- parsing -----------------------------------------------------------

    @staticmethod
    def _parse_skill_md(content: str, path: Optional[Path] = None) -> Skill:
        """Parse a SKILL.md string into a :class:`Skill` instance.

        The file is expected to contain YAML frontmatter between ``---``
        fences, followed by Markdown body content.

        Args:
            content: Raw text content of a ``SKILL.md`` file.
            path: Optional filesystem path for context.

        Returns:
            A fully populated :class:`Skill` dataclass.

        Raises:
            SkillInstallError: If the frontmatter is missing or malformed.
        """
        if not content or not content.strip():
            raise SkillInstallError("SKILL.md content is empty")

        match = _FRONTMATTER_RE.match(content)
        if not match:
            raise SkillInstallError(
                "SKILL.md is missing YAML frontmatter (expected '---' block)"
            )

        frontmatter_raw = match.group(1)
        body = content[match.end():]

        try:
            frontmatter: Dict[str, Any] = yaml.safe_load(frontmatter_raw) or {}
        except yaml.YAMLError as exc:
            raise SkillInstallError(f"Invalid YAML frontmatter: {exc}") from exc

        # Validate required fields
        required_fields = ["name", "version", "category", "description"]
        missing = [f for f in required_fields if f not in frontmatter]
        if missing:
            raise SkillInstallError(
                f"Missing required frontmatter fields: {', '.join(missing)}"
            )

        # Normalize tools_needed
        tools_needed = frontmatter.get("tools_needed", [])
        if isinstance(tools_needed, str):
            tools_needed = [t.strip() for t in tools_needed.split(",") if t.strip()]

        # Parse confidence
        confidence = float(frontmatter.get("confidence", 0.95))

        # Determine source from path
        source = InstallSource.LOCAL
        if path:
            str_path = str(path)
            if "bundled" in str_path:
                source = InstallSource.BUNDLED
            elif "installed" in str_path:
                # Determine if originally from GitHub
                source = InstallSource.GITHUB  # Default assumption

        return Skill(
            name=frontmatter["name"],
            version=frontmatter["version"],
            category=frontmatter["category"],
            description=frontmatter["description"],
            author=frontmatter.get("author", "Construct AI"),
            tools_needed=tools_needed,
            confidence=confidence,
            source=source,
            path=path or Path("."),
            raw_frontmatter=frontmatter,
            raw_body=body,
        )

    @staticmethod
    def _read_skill_from_dir(skill_dir: Path, source: InstallSource) -> Optional[Skill]:
        """Read a skill directory and parse its SKILL.md file.

        Args:
            skill_dir: Directory that should contain ``SKILL.md``.
            source: Installation source classification.

        Returns:
            A :class:`Skill` instance, or ``None`` if the directory does not
            contain a valid ``SKILL.md``.
        """
        md_path = skill_dir / SKILL_FILENAME
        if not md_path.is_file():
            return None
        try:
            content = md_path.read_text(encoding="utf-8")
            skill = SkillInstaller._parse_skill_md(content, path=skill_dir)
            # Override source with the provided classification
            return Skill(
                name=skill.name,
                version=skill.version,
                category=skill.category,
                description=skill.description,
                author=skill.author,
                tools_needed=skill.tools_needed,
                confidence=skill.confidence,
                source=source,
                installed_at=skill.installed_at,
                path=skill_dir,
                raw_frontmatter=skill.raw_frontmatter,
                raw_body=skill.raw_body,
            )
        except (SkillInstallError, OSError) as exc:
            logger.warning("Failed to parse skill from %s: %s", skill_dir, exc)
            return None

    # -- public API: discovery ---------------------------------------------

    def list_bundled(self) -> List[Skill]:
        """List all bundled (pre-installed, read-only) skills.

        Returns:
            A list of :class:`Skill` instances sorted by name.
        """
        skills: List[Skill] = []
        if not self.bundled_dir.exists():
            logger.warning("Bundled skills directory does not exist: %s", self.bundled_dir)
            return skills

        for entry in sorted(self.bundled_dir.iterdir()):
            if entry.is_dir():
                skill = self._read_skill_from_dir(entry, source=InstallSource.BUNDLED)
                if skill:
                    skills.append(skill)

        logger.info("Found %d bundled skill(s)", len(skills))
        return skills

    def list_installed(self) -> List[Skill]:
        """List all user-installed (mutable) skills.

        Returns:
            A list of :class:`Skill` instances sorted by name.
        """
        skills: List[Skill] = []
        if not self.installed_dir.exists():
            return skills

        for entry in sorted(self.installed_dir.iterdir()):
            if entry.is_dir():
                skill = self._read_skill_from_dir(entry, source=InstallSource.GITHUB)
                if skill:
                    skills.append(skill)

        logger.info("Found %d installed skill(s)", len(skills))
        return skills

    def get_skill(self, name: str) -> Skill:
        """Retrieve a skill by name, searching installed first, then bundled.

        Args:
            name: The skill identifier (e.g. ``spec-driven-development``).

        Returns:
            The matching :class:`Skill`.

        Raises:
            SkillNotFoundError: If no skill with the given name exists.
        """
        # Search installed first (user overrides bundled)
        for skill in self.list_installed():
            if skill.name == name:
                return skill

        # Then search bundled
        for skill in self.list_bundled():
            if skill.name == name:
                return skill

        raise SkillNotFoundError(name)

    # -- public API: installation ------------------------------------------

    def install_from_github(
        self,
        owner: str,
        repo: str,
        skill_name: Optional[str] = None,
        branch: str = "main",
        token: Optional[str] = None,
    ) -> Skill:
        """Install a skill from a GitHub repository.

        The repository should contain skill directories, each with a
        ``SKILL.md`` file. If *skill_name* is provided, only that skill
        is installed; otherwise all valid skills in the repo are installed
        and the first one is returned.

        Args:
            owner: GitHub organization or user name.
            repo: Repository name.
            skill_name: Specific skill directory to install (optional).
            branch: Git branch to clone (default: ``main``).
            token: GitHub personal access token for private repos (optional).

        Returns:
            The installed :class:`Skill`.

        Raises:
            SkillInstallError: If cloning or parsing fails.
        """
        clone_url = f"https://github.com/{owner}/{repo}.git"
        if token:
            clone_url = f"https://{token}@github.com/{owner}/{repo}.git"

        with tempfile.TemporaryDirectory(prefix="construct-skill-") as tmp:
            tmp_path = Path(tmp)
            clone_path = tmp_path / "repo"

            logger.info("Cloning %s/%s (branch: %s)", owner, repo, branch)
            self._run_git("clone", "--depth", "1", "--branch", branch, clone_url, str(clone_path))

            # Locate skill directories
            skill_dirs = [d for d in clone_path.iterdir() if d.is_dir() and (d / SKILL_FILENAME).is_file()]
            if not skill_dirs:
                # Try common subdirectories
                for subdir in ["skills", "resources/skills", "src/skills"]:
                    candidate = clone_path / subdir
                    if candidate.exists():
                        skill_dirs = [d for d in candidate.iterdir() if d.is_dir() and (d / SKILL_FILENAME).is_file()]
                        break

            if not skill_dirs:
                raise SkillInstallError(
                    f"No SKILL.md files found in {owner}/{repo}",
                    source=clone_url,
                )

            # Filter to specific skill if requested
            if skill_name:
                matching = [d for d in skill_dirs if d.name == skill_name]
                if not matching:
                    available = ", ".join(sorted(d.name for d in skill_dirs))
                    raise SkillInstallError(
                        f"Skill '{skill_name}' not found in repo. Available: {available}",
                        source=clone_url,
                    )
                skill_dirs = matching

            # Install skills
            installed: List[Skill] = []
            for src_dir in skill_dirs:
                dest_dir = self.installed_dir / src_dir.name
                if dest_dir.exists():
                    logger.info("Removing existing skill: %s", src_dir.name)
                    shutil.rmtree(dest_dir)

                shutil.copytree(src_dir, dest_dir)
                skill = self._read_skill_from_dir(dest_dir, source=InstallSource.GITHUB)
                if skill:
                    installed.append(skill)
                    logger.info("Installed skill: %s@%s", skill.name, skill.version)

        if not installed:
            raise SkillInstallError("No skills could be installed", source=clone_url)

        return installed[0]

    def install_from_url(self, url: str, skill_name: Optional[str] = None) -> Skill:
        """Install a skill by downloading a ``SKILL.md`` from a URL.

        If the URL points directly to a ``SKILL.md`` file it is downloaded
        and saved. If the URL points to a directory (e.g. a GitHub raw
        directory) an attempt is made to enumerate and download skill files.

        Args:
            url: HTTP(S) URL of the skill or skill directory.
            skill_name: Optional name override for the skill directory.

        Returns:
            The installed :class:`Skill`.

        Raises:
            SkillInstallError: If the download or parsing fails.
        """
        logger.info("Downloading skill from URL: %s", url)

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Construct-SkillInstaller/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise SkillInstallError(
                f"HTTP {exc.code}: {exc.reason}", source=url
            ) from exc
        except urllib.error.URLError as exc:
            raise SkillInstallError(
                f"Failed to reach URL: {exc.reason}", source=url
            ) from exc
        except TimeoutError as exc:
            raise SkillInstallError(
                "Download timed out after 30 seconds", source=url
            ) from exc

        skill = self._parse_skill_md(content)
        target_name = skill_name or skill.name
        dest_dir = self.installed_dir / target_name

        if dest_dir.exists():
            logger.info("Removing existing skill: %s", target_name)
            shutil.rmtree(dest_dir)

        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / SKILL_FILENAME).write_text(content, encoding="utf-8")

        # Re-parse with correct path and source
        skill = self._parse_skill_md(content, path=dest_dir)
        skill = Skill(
            name=skill.name,
            version=skill.version,
            category=skill.category,
            description=skill.description,
            author=skill.author,
            tools_needed=skill.tools_needed,
            confidence=skill.confidence,
            source=InstallSource.URL,
            installed_at=datetime.now(timezone.utc).isoformat(),
            path=dest_dir,
            raw_frontmatter=skill.raw_frontmatter,
            raw_body=skill.raw_body,
        )

        logger.info("Installed skill from URL: %s@%s", skill.name, skill.version)
        return skill

    def install_from_local(self, local_path: Union[str, Path], skill_name: Optional[str] = None) -> Skill:
        """Install a skill from a local directory or file.

        Args:
            local_path: Path to a directory containing ``SKILL.md`` or to
                the ``SKILL.md`` file itself.
            skill_name: Optional name override for the installed skill.

        Returns:
            The installed :class:`Skill`.

        Raises:
            SkillInstallError: If the path does not contain a valid skill.
        """
        src_path = Path(local_path).resolve()

        if src_path.is_file():
            content = src_path.read_text(encoding="utf-8")
            skill = self._parse_skill_md(content)
            target_name = skill_name or skill.name
            dest_dir = self.installed_dir / target_name
        elif src_path.is_dir():
            md_path = src_path / SKILL_FILENAME
            if not md_path.is_file():
                raise SkillInstallError(
                    f"Directory does not contain {SKILL_FILENAME}: {src_path}"
                )
            content = md_path.read_text(encoding="utf-8")
            skill = self._parse_skill_md(content)
            target_name = skill_name or src_path.name
            dest_dir = self.installed_dir / target_name
        else:
            raise SkillInstallError(f"Path does not exist: {src_path}")

        if dest_dir.exists():
            logger.info("Removing existing skill: %s", target_name)
            shutil.rmtree(dest_dir)

        if src_path.is_dir():
            shutil.copytree(src_path, dest_dir)
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / SKILL_FILENAME).write_text(content, encoding="utf-8")

        skill = self._read_skill_from_dir(dest_dir, source=InstallSource.LOCAL)
        if skill is None:
            raise SkillInstallError(f"Failed to install skill from {src_path}")

        logger.info("Installed skill from local path: %s@%s", skill.name, skill.version)
        return skill

    # -- public API: management --------------------------------------------

    def uninstall_skill(self, name: str) -> None:
        """Remove an installed (non-bundled) skill.

        Args:
            name: Skill identifier to remove.

        Raises:
            SkillNotFoundError: If the skill is not found in the installed directory.
            SkillInstallError: If the skill is bundled (read-only) and cannot be removed.
        """
        # Check if it's a bundled skill first
        try:
            existing = self.get_skill(name)
            if existing.is_bundled:
                raise SkillInstallError(
                    f"Cannot uninstall bundled skill '{name}'. Bundled skills are read-only."
                )
        except SkillNotFoundError:
            pass

        dest_dir = self.installed_dir / name
        if not dest_dir.exists():
            raise SkillNotFoundError(name)

        shutil.rmtree(dest_dir)
        logger.info("Uninstalled skill: %s", name)

    def update_skill(self, name: str) -> Skill:
        """Check for updates and install the latest version of a skill.

        For GitHub-installed skills, this re-clones the repository.
        For URL-installed skills, this re-downloads from the original URL
        (if stored in metadata).
        For bundled skills, this returns the bundled version without modification.

        Args:
            name: Skill identifier to update.

        Returns:
            The updated :class:`Skill`.

        Raises:
            SkillNotFoundError: If the skill is not found.
            SkillInstallError: If the update fails.
        """
        try:
            existing = self.get_skill(name)
        except SkillNotFoundError:
            raise

        if existing.is_bundled:
            logger.info("Skill '%s' is bundled — cannot update. Returning as-is.", name)
            return existing

        # For now, re-install from the same source if possible
        # In a production system, metadata about the original source would be stored
        logger.info("Updating skill: %s (current: %s)", name, existing.version)

        # Remove old version
        self.uninstall_skill(name)

        # Store metadata for re-installation
        metadata_path = self.installed_dir / f".{name}.meta.json"
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                source = metadata.get("source")
                if source == "github":
                    return self.install_from_github(
                        metadata["owner"], metadata["repo"], name, metadata.get("branch", "main")
                    )
                elif source == "url":
                    return self.install_from_url(metadata["url"], name)
                elif source == "local":
                    return self.install_from_local(metadata["path"], name)
            except (json.JSONDecodeError, KeyError, SkillInstallError) as exc:
                logger.warning("Failed to update from stored metadata: %s", exc)

        # If we can't determine the source, re-read the old content and re-install
        logger.warning("Could not determine update source for '%s'. Skill removed but not re-installed.", name)
        raise SkillInstallError(
            f"Cannot update skill '{name}': original installation source unknown. "
            "Please reinstall manually using install_from_github() or install_from_url()."
        )

    def export_skill(self, name: str, output_path: Optional[Union[str, Path]] = None) -> str:
        """Export a skill as a standalone ``SKILL.md`` file.

        Args:
            name: Skill identifier to export.
            output_path: Destination file path (default: ``{name}-SKILL.md`` in cwd).

        Returns:
            The absolute path to the exported file.

        Raises:
            SkillNotFoundError: If the skill is not found.
        """
        skill = self.get_skill(name)
        content = skill.read_content()

        dest = Path(output_path or f"{name}-SKILL.md").resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

        logger.info("Exported skill '%s' to %s", name, dest)
        return str(dest)

    # -- marketplace search ------------------------------------------------

    def search_marketplace(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """Search GitHub for repositories tagged ``construct-skill``.

        Uses the GitHub search API to find skill repositories matching
        the given query string.

        Args:
            query: Search keywords (e.g. ``testing pytest``).
            limit: Maximum number of results (default: 10).

        Returns:
            A list of dictionaries containing repository metadata.
        """
        search_query = f"topic:construct-skill {query}"
        encoded_query = urllib.parse.quote(search_query)
        url = f"https://api.github.com/search/repositories?q={encoded_query}&sort=stars&order=desc&per_page={limit}"

        logger.info("Searching marketplace for: %s", query)

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Construct-SkillInstaller/1.0",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                logger.warning("GitHub API rate limit exceeded")
                return []
            raise SkillInstallError(f"GitHub API error: {exc.code}") from exc
        except Exception as exc:
            logger.warning("Marketplace search failed: %s", exc)
            return []

        results = []
        for item in data.get("items", []):
            results.append({
                "full_name": item.get("full_name", ""),
                "description": item.get("description", ""),
                "stars": str(item.get("stargazers_count", 0)),
                "url": item.get("html_url", ""),
                "clone_url": item.get("clone_url", ""),
            })

        logger.info("Marketplace search found %d result(s)", len(results))
        return results

    # -- diagnostics -------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Run a diagnostic check on the skill installation system.

        Returns:
            A dictionary with directory status, counts, and any issues.
        """
        bundled = self.list_bundled()
        installed = self.list_installed()

        return {
            "bundled_dir": str(self.bundled_dir),
            "bundled_dir_exists": self.bundled_dir.exists(),
            "installed_dir": str(self.installed_dir),
            "installed_dir_exists": self.installed_dir.exists(),
            "bundled_count": len(bundled),
            "installed_count": len(installed),
            "bundled_skills": [s.name for s in bundled],
            "installed_skills": [s.name for s in installed],
            "git_available": shutil.which("git") is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
