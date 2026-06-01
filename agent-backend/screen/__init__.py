"""Screen control and desktop automation package."""
from .screen_controller import ScreenController, Platform, ScreenAction, WindowInfo
from .visual_finder import (
    VisualElementFinder,
    Point,
    Rect,
    TextRegion,
)
from .action_recorder import (
    ActionRecorder,
    Action,
    ActionScript,
    ActionType,
    RiskLevel,
    AuditEntry,
    ReplayResult,
)

__all__ = [
    "ScreenController",
    "Platform",
    "ScreenAction",
    "WindowInfo",
    "VisualElementFinder",
    "Point",
    "Rect",
    "TextRegion",
    "ActionRecorder",
    "Action",
    "ActionScript",
    "ActionType",
    "RiskLevel",
    "AuditEntry",
    "ReplayResult",
]
