"""MarkItDown Tool — convert 20+ document formats to Markdown.

Uses Microsoft's MarkItDown library as the primary parser with custom
parsers as fallback for unsupported or partially-supported formats.

Supported formats: PDF, DOCX, PPTX, XLSX, HTML, CSV, JSON, XML, ZIP,
EPUB, images (with OCR), audio (transcription), and more.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional markitdown — graceful degradation if not installed
try:
    from markitdown import MarkItDown

    HAS_MARKITDOWN = True
except ImportError:
    HAS_MARKITDOWN = False
    logger.warning("markitdown not installed — document conversion unavailable")


class MarkItDownTool:
    """Convert documents to Markdown using MarkItDown + custom fallbacks."""

    SUPPORTED_EXTENSIONS: set[str] = {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
        ".html",
        ".htm",
        ".csv",
        ".json",
        ".xml",
        ".zip",
        ".epub",
        ".txt",
        ".rtf",
        ".odt",
        ".ods",
        ".odp",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".tiff",
        ".wav",
        ".mp3",
        ".m4a",
        ".ogg",
    }

    # Mapping of extensions to fallback parser methods
    _FALLBACK_MAP: Dict[str, str] = {
        ".txt": "_fallback_txt",
        ".csv": "_fallback_csv",
        ".json": "_fallback_json",
        ".xml": "_fallback_xml",
        ".zip": "_fallback_zip",
        ".html": "_fallback_html",
        ".htm": "_fallback_html",
    }

    def __init__(self) -> None:
        self._md: Optional[Any] = None
        if HAS_MARKITDOWN:
            try:
                self._md = MarkItDown()
                logger.info("MarkItDown initialized")
            except Exception as exc:
                logger.error("Failed to initialize MarkItDown: %s", exc)
                self._md = None
        else:
            logger.warning(
                "MarkItDown not available — install with: pip install markitdown[all]"
            )

    # -- Public API -----------------------------------------------------------

    def convert_file(
        self, file_path: str, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convert a single file to Markdown.

        Parameters
        ----------
        file_path:
            Absolute or relative path to the source document.
        output_path:
            Optional path to write the Markdown output. If omitted,
            the result is only returned in the dict.

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool)
            - ``markdown`` (str) — the converted Markdown text
            - ``title`` (str|None) — document title if extractable
            - ``output_path`` (str|None) — path where output was written
            - ``method`` (str) — "markitdown" or "fallback"
            - ``error`` (str|None) — error message on failure
        """
        logger.info("convert_file: %s", file_path)

        # 1. Validate file exists
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.isfile(abs_path):
            logger.error("File not found: %s", abs_path)
            return {
                "success": False,
                "markdown": "",
                "title": None,
                "output_path": None,
                "method": None,
                "error": f"File not found: {file_path}",
            }

        ext = Path(abs_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            return {
                "success": False,
                "markdown": "",
                "title": None,
                "output_path": None,
                "method": None,
                "error": (
                    f"Unsupported file extension: '{ext}'. "
                    f"Supported: {supported}"
                ),
            }

        # 2. Try MarkItDown first
        markdown_text = ""
        title: Optional[str] = None
        method = "markitdown"

        if self._md is not None:
            try:
                result = self._md.convert(abs_path)
                markdown_text = getattr(result, "text_content", "") or str(result)
                # Try to extract title from first H1
                title = self._extract_title(markdown_text)
                logger.info(
                    "MarkItDown converted '%s' (%d chars)", abs_path, len(markdown_text)
                )
            except Exception as exc:
                logger.warning(
                    "MarkItDown failed for '%s': %s — trying fallback", abs_path, exc
                )
                markdown_text = ""

        # 3. Fallback to custom parsers if MarkItDown failed or is unavailable
        if not markdown_text:
            fallback_method = self._FALLBACK_MAP.get(ext)
            if fallback_method and hasattr(self, fallback_method):
                try:
                    markdown_text = getattr(self, fallback_method)(abs_path)
                    title = self._extract_title(markdown_text)
                    method = "fallback"
                    logger.info(
                        "Fallback parser '%s' converted '%s' (%d chars)",
                        fallback_method,
                        abs_path,
                        len(markdown_text),
                    )
                except Exception as exc:
                    logger.error("Fallback parser '%s' failed: %s", fallback_method, exc)
                    return {
                        "success": False,
                        "markdown": "",
                        "title": None,
                        "output_path": None,
                        "method": None,
                        "error": f"All parsers failed for {file_path}: {exc}",
                    }
            else:
                # No fallback available — return error if MarkItDown also failed
                if not self._md:
                    return {
                        "success": False,
                        "markdown": "",
                        "title": None,
                        "output_path": None,
                        "method": None,
                        "error": (
                            f"No parser available for '{ext}'. "
                            f"Install markitdown: pip install markitdown[all]"
                        ),
                    }

        # 4. Write to output_path if provided
        written_path: Optional[str] = None
        if output_path and markdown_text:
            try:
                out_abs = os.path.abspath(os.path.expanduser(output_path))
                os.makedirs(os.path.dirname(out_abs), exist_ok=True)
                with open(out_abs, "w", encoding="utf-8") as f:
                    if title:
                        f.write(f"# {title}\n\n")
                    f.write(markdown_text)
                written_path = out_abs
                logger.info("Wrote markdown output to: %s", out_abs)
            except Exception as exc:
                logger.error("Failed to write output to '%s': %s", output_path, exc)

        return {
            "success": bool(markdown_text),
            "markdown": markdown_text,
            "title": title,
            "output_path": written_path,
            "method": method,
            "error": None,
        }

    def convert_batch(
        self, directory: str, output_dir: str
    ) -> Dict[str, Any]:
        """Convert all supported files in a directory recursively.

        Parameters
        ----------
        directory:
            Root directory to scan for convertible files.
        output_dir:
            Directory where Markdown outputs will be written.

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool) — True if at least one file converted
            - ``converted_count`` (int)
            - ``failed_count`` (int)
            - ``skipped_count`` (int)
            - ``results`` (list[dict]) — per-file results
        """
        logger.info("convert_batch: %s -> %s", directory, output_dir)

        abs_dir = os.path.abspath(os.path.expanduser(directory))
        abs_out = os.path.abspath(os.path.expanduser(output_dir))

        if not os.path.isdir(abs_dir):
            return {
                "success": False,
                "converted_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "results": [],
                "error": f"Directory not found: {directory}",
            }

        os.makedirs(abs_out, exist_ok=True)

        results: List[Dict[str, Any]] = []
        converted = 0
        failed = 0
        skipped = 0

        for root, _dirs, files in os.walk(abs_dir):
            # Skip hidden and common non-source directories
            _dirs[:] = [
                d
                for d in _dirs
                if not d.startswith(".")
                and d not in {"node_modules", "__pycache__", "venv", ".git", "dist", "build"}
            ]

            for filename in files:
                if filename.startswith("."):
                    continue

                file_path = os.path.join(root, filename)
                ext = Path(filename).suffix.lower()

                if ext not in self.SUPPORTED_EXTENSIONS:
                    skipped += 1
                    continue

                # Compute output path preserving relative structure
                rel_path = os.path.relpath(file_path, abs_dir)
                out_name = os.path.splitext(rel_path)[0] + ".md"
                out_path = os.path.join(abs_out, out_name)

                result = self.convert_file(file_path, output_path=out_path)
                result["input_file"] = file_path
                results.append(result)

                if result["success"]:
                    converted += 1
                else:
                    failed += 1

        logger.info(
            "Batch conversion complete: %d converted, %d failed, %d skipped",
            converted,
            failed,
            skipped,
        )

        return {
            "success": converted > 0,
            "converted_count": converted,
            "failed_count": failed,
            "skipped_count": skipped,
            "results": results,
            "output_dir": abs_out,
            "error": None,
        }

    def extract_structure(self, file_path: str) -> Dict[str, Any]:
        """Extract document structure: headings, tables, lists, word count.

        Parameters
        ----------
        file_path:
            Path to the document to analyze.

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool)
            - ``headings`` (list[dict]) — level, text, line
            - ``tables`` (int) — number of tables
            - ``lists`` (int) — number of list blocks
            - ``word_count`` (int)
            - ``char_count`` (int)
            - ``error`` (str|None)
        """
        logger.info("extract_structure: %s", file_path)

        result = self.convert_file(file_path)
        if not result["success"]:
            return {
                "success": False,
                "headings": [],
                "tables": 0,
                "lists": 0,
                "word_count": 0,
                "char_count": 0,
                "error": result.get("error", "Conversion failed"),
            }

        markdown = result["markdown"]
        headings: List[Dict[str, Any]] = []
        tables = 0
        lists = 0

        for line_no, line in enumerate(markdown.splitlines(), 1):
            stripped = line.strip()

            # Headings: # H1, ## H2, etc.
            heading_match = re.match(r"^(#{1,6})\s+(.+)", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                headings.append({"level": level, "text": text, "line": line_no})

            # Tables: lines starting with |
            if stripped.startswith("|") and "---" in stripped:
                tables += 1

            # Lists: - item, * item, 1. item
            if re.match(r"^([\-\*\+]\s|\d+\.\s)", stripped):
                lists += 1

        words = len(markdown.split())
        chars = len(markdown)

        return {
            "success": True,
            "headings": headings,
            "tables": tables,
            "lists": lists,
            "word_count": words,
            "char_count": chars,
            "title": result.get("title"),
            "error": None,
        }

    def is_supported(self, file_path: str) -> bool:
        """Check if a file format is supported.

        Parameters
        ----------
        file_path:
            Path to the file to check.

        Returns
        -------
        bool
            *True* if the extension is in the supported set.
        """
        return Path(file_path).suffix.lower() in self.SUPPORTED_EXTENSIONS

    # -- Fallback parsers -----------------------------------------------------

    def _fallback_txt(self, file_path: str) -> str:
        """Read a plain text file."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _fallback_csv(self, file_path: str) -> str:
        """Convert CSV to Markdown table."""
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return ""

        md_lines: List[str] = []
        md_lines.append("| " + " | ".join(rows[0]) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
        for row in rows[1:]:
            md_lines.append("| " + " | ".join(row) + " |")
        return "\n".join(md_lines) + "\n"

    def _fallback_json(self, file_path: str) -> str:
        """Convert JSON to Markdown code block."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return "```json\n" + json.dumps(data, indent=2) + "\n```\n"

    def _fallback_xml(self, file_path: str) -> str:
        """Convert XML to Markdown with code block and attempt to extract text."""
        try:
            import xml.etree.ElementTree as ET

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            md = "```xml\n" + content + "\n```\n"

            # Attempt to extract text nodes
            try:
                root = ET.fromstring(content)
                texts: List[str] = []
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        texts.append(elem.text.strip())
                if texts:
                    md += "\n## Extracted Text\n\n"
                    md += "\n\n".join(texts) + "\n"
            except ET.ParseError:
                pass  # Raw content already included in code block

            return md
        except Exception:
            # If XML parsing fails entirely, return as plain text
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    def _fallback_html(self, file_path: str) -> str:
        """Convert HTML to Markdown — try stripping tags if MarkItDown failed."""
        try:
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                """Simple HTML-to-text extractor."""

                def __init__(self) -> None:
                    super().__init__()
                    self.parts: List[str] = []
                    self.skip_tags = {"script", "style"}
                    self._skip_depth = 0

                def handle_starttag(self, tag: str, attrs: Any) -> None:
                    if tag.lower() in self.skip_tags:
                        self._skip_depth += 1
                    if tag.lower() in {"br", "br/", "p"}:
                        self.parts.append("\n")
                    if tag.lower().startswith("h") and len(tag) == 2:
                        try:
                            level = int(tag[1])
                            self.parts.append("\n" + "#" * level + " ")
                        except ValueError:
                            pass

                def handle_endtag(self, tag: str) -> None:
                    if tag.lower() in self.skip_tags:
                        self._skip_depth -= 1
                    if tag.lower() in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6"}:
                        self.parts.append("\n")

                def handle_data(self, data: str) -> None:
                    if self._skip_depth == 0:
                        self.parts.append(data)

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()

            extractor = TextExtractor()
            extractor.feed(html)
            text = "".join(extractor.parts)
            # Collapse multiple blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip() + "\n"
        except Exception:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    def _fallback_zip(self, file_path: str) -> str:
        """List contents of a ZIP archive as Markdown."""
        md_lines: List[str] = ["# ZIP Archive Contents\n"]
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                md_lines.append(f"**Archive:** `{file_path}`\n")
                md_lines.append(f"**Entries:** {len(zf.namelist())}\n")
                md_lines.append("\n| Name | Size | Date |")
                md_lines.append("|------|------|------|")
                for info in zf.infolist():
                    date_str = f"{info.date_time[0]:04d}-{info.date_time[1]:02d}-{info.date_time[2]:02d}"
                    md_lines.append(
                        f"| `{info.filename}` | {info.file_size} | {date_str} |"
                    )
        except zipfile.BadZipFile:
            md_lines.append(f"\n*Error: '{file_path}' is not a valid ZIP archive.*")
        return "\n".join(md_lines) + "\n"

    # -- Internal helpers -----------------------------------------------------

    @staticmethod
    def _extract_title(markdown: str) -> Optional[str]:
        """Extract the document title from the first H1 heading."""
        for line in markdown.splitlines():
            match = re.match(r"^#\s+(.+)", line.strip())
            if match:
                return match.group(1).strip()
        return None
