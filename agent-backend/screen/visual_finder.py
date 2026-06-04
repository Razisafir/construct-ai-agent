"""Visual Element Finder — locate UI elements using CV + OCR.

Methods:
- Template matching: find button/image by screenshot
- OCR: find element by text label
- Color matching: find elements by color
- Wait: poll until element appears

Dependencies (optional but recommended):
    pip install opencv-python-headless numpy pytesseract Pillow

For OCR to work, Tesseract must be installed on the system:
    Ubuntu: sudo apt-get install tesseract-ocr
    macOS:  brew install tesseract
    Windows: https://github.com/UB-Mannheim/tesseract/wiki
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------
try:
    import cv2
    import numpy as np

    HAS_OPENCV = True
except ImportError:  # pragma: no cover
    HAS_OPENCV = False
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

try:
    import pytesseract

    HAS_TESSERACT = True
except ImportError:  # pragma: no cover
    HAS_TESSERACT = False
    pytesseract = None  # type: ignore[assignment]

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:  # pragma: no cover
    HAS_PIL = False
    Image = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Point:
    """2-D screen coordinate."""

    x: int
    y: int


@dataclass
class Rect:
    """Bounding rectangle with match confidence."""

    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0


@dataclass
class TextRegion:
    """OCR-detected text region."""

    text: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    confidence: float


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class VisualElementFinder:
    """Find UI elements on screen using computer vision.

    Args:
        screenshot_fn: Callable that returns a PIL ``Image`` or a ``numpy.ndarray``
            in RGB format. If *None*, the finder can still be used with images
            passed directly to the low-level helpers.
    """

    # Scales used for multi-resolution template matching.
    _DEFAULT_SCALES: Tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5)

    def __init__(
        self,
        screenshot_fn: Optional[callable] = None,
        scales: Optional[Tuple[float, ...]] = None,
    ) -> None:
        self._screenshot: Optional[callable] = screenshot_fn
        self._last_screenshot: Optional[Any] = None
        self._scales: Tuple[float, ...] = scales or self._DEFAULT_SCALES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_by_image(
        self,
        template_path: str,
        confidence: float = 0.8,
        scales: Optional[Tuple[float, ...]] = None,
    ) -> Optional[Point]:
        """Find an element by template image.

        Performs multi-scale template matching so that the same template can be
        used across different screen resolutions / DPI settings.

        Args:
            template_path: Filesystem path to the template image (PNG/JPG).
            confidence: Minimum correlation coefficient (0.0-1.0).  Higher is
                stricter.  Default ``0.8``.
            scales: Override the default scale factors.  Each scale is applied
                to the *template* before matching.

        Returns:
            Centre ``Point`` of the best match, or *None* if no match exceeds
            *confidence*.

        Raises:
            FileNotFoundError: If *template_path* does not exist.
        """
        if not HAS_OPENCV:
            logger.warning("OpenCV not available — cannot perform template matching")
            return None

        template_path_obj = Path(template_path)
        if not template_path_obj.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        haystack = self._take_screenshot()
        if haystack is None:
            logger.error("Screenshot function returned None")
            return None

        needle = cv2.imread(str(template_path_obj), cv2.IMREAD_COLOR)
        if needle is None:
            logger.error("Failed to load template image: %s", template_path)
            return None

        haystack_cv = self._pil_to_cv(haystack) if HAS_PIL and isinstance(haystack, Image.Image) else haystack
        if haystack_cv is None or not isinstance(haystack_cv, np.ndarray):
            logger.error("Screenshot could not be converted to OpenCV format")
            return None

        search_scales = scales or self._scales
        best_val: float = -1.0
        best_loc: Optional[Tuple[int, int]] = None
        best_scale: float = 1.0

        for scale in search_scales:
            scaled_needle = self._resize_image(needle, scale)
            if scaled_needle is None:
                continue

            # Template matching requires template <= haystack
            if scaled_needle.shape[0] > haystack_cv.shape[0] or scaled_needle.shape[1] > haystack_cv.shape[1]:
                logger.debug("Scale %.2f: template larger than screenshot — skipping", scale)
                continue

            result = cv2.matchTemplate(haystack_cv, scaled_needle, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            logger.debug("Scale %.2f: match confidence = %.3f", scale, max_val)

            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_scale = scale

        if best_val < confidence or best_loc is None:
            logger.info("No match found above confidence %.2f (best was %.3f)", confidence, best_val)
            return None

        # Reload best-scale needle to compute centre
        best_needle = self._resize_image(needle, best_scale)
        centre_x = best_loc[0] + best_needle.shape[1] // 2
        centre_y = best_loc[1] + best_needle.shape[0] // 2

        logger.info(
            "Found match at (%d, %d) — confidence=%.3f, scale=%.2f",
            centre_x,
            centre_y,
            best_val,
            best_scale,
        )
        return Point(centre_x, centre_y)

    def find_all_by_image(
        self,
        template_path: str,
        confidence: float = 0.8,
        max_results: int = 10,
    ) -> List[Rect]:
        """Find **all** occurrences of a template image on screen.

        Non-maximum suppression is applied so overlapping detections are merged.

        Args:
            template_path: Path to the template image.
            confidence: Minimum match confidence.
            max_results: Maximum number of distinct matches to return.

        Returns:
            List of ``Rect`` objects sorted by confidence (highest first).
        """
        if not HAS_OPENCV:
            logger.warning("OpenCV not available")
            return []

        template_path_obj = Path(template_path)
        if not template_path_obj.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        haystack = self._take_screenshot()
        if haystack is None:
            return []

        needle = cv2.imread(str(template_path_obj), cv2.IMREAD_COLOR)
        if needle is None:
            return []

        haystack_cv = self._pil_to_cv(haystack) if HAS_PIL and isinstance(haystack, Image.Image) else haystack
        if haystack_cv is None or not isinstance(haystack_cv, np.ndarray):
            return []

        results: List[Rect] = []
        for scale in self._scales:
            scaled_needle = self._resize_image(needle, scale)
            if scaled_needle is None:
                continue
            if scaled_needle.shape[0] > haystack_cv.shape[0] or scaled_needle.shape[1] > haystack_cv.shape[1]:
                continue

            match_result = cv2.matchTemplate(haystack_cv, scaled_needle, cv2.TM_CCOEFF_NORMED)
            loc = np.where(match_result >= confidence)
            h, w = scaled_needle.shape[:2]
            for pt in zip(*loc[::-1]):
                results.append(
                    Rect(
                        x=int(pt[0]),
                        y=int(pt[1]),
                        width=w,
                        height=h,
                        confidence=float(match_result[pt[1], pt[0]]),
                    )
                )

        # Non-maximum suppression — merge overlapping boxes
        filtered = self._nms(results, overlap_thresh=0.3)
        filtered.sort(key=lambda r: r.confidence, reverse=True)
        return filtered[:max_results]

    def find_by_text(
        self,
        text: str,
        case_sensitive: bool = False,
        min_confidence: float = 60.0,
    ) -> Optional[Point]:
        """Find an element by its text label using OCR.

        Uses Tesseract's image-to-data mode to obtain per-word bounding boxes,
        then scores each region against *text* using simple string containment.
        If multiple words make up the target phrase, a clustering step merges
        adjacent boxes.

        Args:
            text: The text label to search for.
            case_sensitive: If *False* (default), matching is case-insensitive.
            min_confidence: Minimum OCR confidence (0-100) for a word to be
                considered.

        Returns:
            Centre ``Point`` of the best-matching text region, or *None*.
        """
        if not HAS_TESSERACT:
            logger.warning("Tesseract (pytesseract) not available — cannot perform OCR")
            return None

        haystack = self._take_screenshot()
        if haystack is None:
            logger.error("Screenshot function returned None")
            return None

        pil_image = haystack if (HAS_PIL and isinstance(haystack, Image.Image)) else self._cv_to_pil(haystack)
        if pil_image is None:
            logger.error("Screenshot could not be converted to PIL format")
            return None

        try:
            data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
        except Exception as exc:
            logger.error("OCR failed: %s", exc)
            return None

        regions = self._extract_text_regions(data, min_confidence=min_confidence)
        if not regions:
            logger.info("No text regions detected by OCR")
            return None

        # Cluster adjacent regions for multi-word phrases
        clustered = self._cluster_regions(regions)

        search_text = text if case_sensitive else text.lower()
        best_score: float = 0.0
        best_region: Optional[TextRegion] = None

        for region in clustered:
            region_text = region.text if case_sensitive else region.text.lower()
            score = self._text_similarity(search_text, region_text)
            if score > best_score:
                best_score = score
                best_region = region

        if best_region is None or best_score < 0.5:
            logger.info("Text '%s' not found (best score: %.2f)", text, best_score)
            return None

        x, y, w, h = best_region.bbox
        centre = Point(x + w // 2, y + h // 2)
        logger.info(
            "Found text '%s' at (%d, %d) — OCR confidence=%.1f, match score=%.2f",
            text,
            centre.x,
            centre.y,
            best_region.confidence,
            best_score,
        )
        return centre

    def find_all_text_regions(
        self,
        min_confidence: float = 60.0,
    ) -> List[TextRegion]:
        """Return **all** OCR-detected text regions on screen.

        Useful for debugging / building a text-based element map.
        """
        if not HAS_TESSERACT:
            logger.warning("Tesseract not available")
            return []

        haystack = self._take_screenshot()
        if haystack is None:
            return []

        pil_image = haystack if (HAS_PIL and isinstance(haystack, Image.Image)) else self._cv_to_pil(haystack)
        if pil_image is None:
            return []

        try:
            data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
        except Exception as exc:
            logger.error("OCR failed: %s", exc)
            return []

        return self._extract_text_regions(data, min_confidence=min_confidence)

    def find_by_color(
        self,
        color: Tuple[int, int, int],
        tolerance: int = 10,
        min_area: int = 50,
    ) -> List[Point]:
        """Find all elements matching a BGR colour.

        Args:
            color: Target colour as ``(B, G, R)``.
            tolerance: Per-channel distance allowed (default 10).
            min_area: Minimum contour area in pixels.  Small noise blobs are
                discarded.

        Returns:
            List of centre ``Point`` objects for each matching region.
        """
        if not HAS_OPENCV:
            logger.warning("OpenCV not available — cannot perform colour matching")
            return []

        haystack = self._take_screenshot()
        if haystack is None:
            logger.error("Screenshot function returned None")
            return []

        haystack_cv = self._pil_to_cv(haystack) if HAS_PIL and isinstance(haystack, Image.Image) else haystack
        if haystack_cv is None or not isinstance(haystack_cv, np.ndarray):
            return []

        lower = np.array([max(0, c - tolerance) for c in color], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in color], dtype=np.uint8)

        mask = cv2.inRange(haystack_cv, lower, upper)

        # Morphological open to remove speckle noise
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        points: List[Point] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            points.append(Point(cx, cy))

        logger.info("Found %d region(s) matching color %s (tolerance=%d)", len(points), color, tolerance)
        return points

    def wait_for_element(
        self,
        template_path: str,
        timeout: int = 30,
        confidence: float = 0.8,
        poll_interval: float = 0.5,
    ) -> Optional[Point]:
        """Poll until an element appears (or *timeout* expires).

        Args:
            template_path: Path to the template image.
            timeout: Maximum seconds to wait.
            confidence: Minimum match confidence.
            poll_interval: Seconds between attempts (default 0.5).

        Returns:
            Centre ``Point`` once found, or *None* on timeout.
        """
        logger.info("Waiting for element '%s' (timeout=%ds, confidence≥%.2f)", template_path, timeout, confidence)
        deadline = time.monotonic() + timeout
        attempts = 0

        while time.monotonic() < deadline:
            attempts += 1
            try:
                result = self.find_by_image(template_path, confidence=confidence)
                if result is not None:
                    logger.info("Element found after %d attempt(s) at (%d, %d)", attempts, result.x, result.y)
                    return result
            except Exception as exc:
                logger.debug("Poll attempt %d failed: %s", attempts, exc)

            remaining = deadline - time.monotonic()
            sleep_time = min(poll_interval, max(0, remaining))
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.warning("Timeout after %d attempt(s) — element not found", attempts)
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _take_screenshot(self) -> Optional[Any]:
        """Capture a screenshot using the configured callable."""
        if self._screenshot is None:
            logger.error("No screenshot function configured")
            return None
        try:
            self._last_screenshot = self._screenshot()
        except Exception as exc:
            logger.error("Screenshot function raised %s: %s", type(exc).__name__, exc)
            self._last_screenshot = None
        return self._last_screenshot

    @staticmethod
    def _pil_to_cv(pil_image: Any) -> Optional[Any]:
        """Convert a PIL ``Image`` (RGB) to an OpenCV BGR ``ndarray``."""
        if not HAS_OPENCV or np is None:
            return None
        if not HAS_PIL or not isinstance(pil_image, Image.Image):
            return None
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _cv_to_pil(cv_image: Any) -> Optional[Any]:
        """Convert an OpenCV BGR ``ndarray`` to a PIL ``Image`` (RGB)."""
        if not HAS_PIL or Image is None:
            return None
        if not HAS_OPENCV or np is None or not isinstance(cv_image, np.ndarray):
            return None
        rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @staticmethod
    def _resize_image(image: Any, scale: float) -> Optional[Any]:
        """Resize *image* by *scale* using cubic interpolation."""
        if not HAS_OPENCV or image is None or np is None:
            return None
        if scale <= 0:
            return None
        new_w = max(1, int(image.shape[1] * scale))
        new_h = max(1, int(image.shape[0] * scale))
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def _extract_text_regions(
        ocr_data: dict,
        min_confidence: float = 60.0,
    ) -> List[TextRegion]:
        """Build ``TextRegion`` list from Tesseract *image_to_data* output."""
        regions: List[TextRegion] = []
        n_boxes = len(ocr_data.get("text", []))
        for i in range(n_boxes):
            conf = float(ocr_data["conf"][i])
            if conf < min_confidence:
                continue
            text = ocr_data["text"][i].strip()
            if not text:
                continue
            x, y, w, h = (
                ocr_data["left"][i],
                ocr_data["top"][i],
                ocr_data["width"][i],
                ocr_data["height"][i],
            )
            regions.append(TextRegion(text=text, bbox=(x, y, w, h), confidence=conf))
        return regions

    @staticmethod
    def _cluster_regions(regions: List[TextRegion], max_gap_x: int = 20, max_gap_y: int = 10) -> List[TextRegion]:
        """Merge horizontally-adjacent text regions into phrases.

        This improves matching for multi-word labels such as "Submit Form".
        """
        if not regions:
            return []

        # Sort left-to-right, top-to-bottom
        sorted_regions = sorted(regions, key=lambda r: (r.bbox[1], r.bbox[0]))
        clusters: List[List[TextRegion]] = []
        current: List[TextRegion] = [sorted_regions[0]]

        for region in sorted_regions[1:]:
            prev = current[-1]
            prev_x2 = prev.bbox[0] + prev.bbox[2]
            prev_cy = prev.bbox[1] + prev.bbox[3] // 2
            cur_cy = region.bbox[1] + region.bbox[3] // 2

            gap_x = region.bbox[0] - prev_x2
            gap_y = abs(cur_cy - prev_cy)

            if gap_x <= max_gap_x and gap_y <= max_gap_y:
                current.append(region)
            else:
                clusters.append(current)
                current = [region]
        clusters.append(current)

        merged: List[TextRegion] = []
        for cluster in clusters:
            if len(cluster) == 1:
                merged.append(cluster[0])
                continue
            texts = [r.text for r in cluster]
            full_text = " ".join(texts)
            min_x = min(r.bbox[0] for r in cluster)
            min_y = min(r.bbox[1] for r in cluster)
            max_x2 = max(r.bbox[0] + r.bbox[2] for r in cluster)
            max_y2 = max(r.bbox[1] + r.bbox[3] for r in cluster)
            avg_conf = sum(r.confidence for r in cluster) / len(cluster)
            merged.append(
                TextRegion(
                    text=full_text,
                    bbox=(min_x, min_y, max_x2 - min_x, max_y2 - min_y),
                    confidence=avg_conf,
                )
            )

        return merged

    @staticmethod
    def _text_similarity(query: str, target: str) -> float:
        """Score how well *query* matches *target* (0.0-1.0).

        Simple containment with length normalisation.  Override for fuzzy
        algorithms (Levenshtein, TF-IDF, etc.).
        """
        if query == target:
            return 1.0
        if query in target:
            return 0.7 + 0.3 * (len(query) / len(target))
        # Partial word overlap
        query_words = set(query.split())
        target_words = set(target.split())
        if query_words and target_words:
            overlap = len(query_words & target_words) / max(len(query_words), len(target_words))
            return overlap * 0.6
        return 0.0

    @staticmethod
    def _nms(rects: List[Rect], overlap_thresh: float = 0.3) -> List[Rect]:
        """Greedy non-maximum suppression for overlapping rectangles.

        Args:
            rects: Detections sorted by confidence (highest first) is
                preferred, but the function re-sorts internally.
            overlap_thresh: IoU threshold above which weaker boxes are
                suppressed.

        Returns:
            Filtered list of rectangles.
        """
        if not rects:
            return []

        sorted_rects = sorted(rects, key=lambda r: r.confidence, reverse=True)
        keep: List[Rect] = []

        while sorted_rects:
            current = sorted_rects.pop(0)
            keep.append(current)
            sorted_rects = [r for r in sorted_rects if VisualElementFinder._iou(current, r) < overlap_thresh]

        return keep

    @staticmethod
    def _iou(a: Rect, b: Rect) -> float:
        """Intersection-over-Union of two rectangles."""
        x1 = max(a.x, b.x)
        y1 = max(a.y, b.y)
        x2 = min(a.x + a.width, b.x + b.width)
        y2 = min(a.y + a.height, b.y + b.height)

        inter_w = max(0, x2 - x1)
        inter_h = max(0, y2 - y1)
        inter_area = inter_w * inter_h

        area_a = a.width * a.height
        area_b = b.width * b.height
        union_area = area_a + area_b - inter_area

        return inter_area / union_area if union_area > 0 else 0.0
