"""Agent roles package — re-export all role definitions."""
from .code_engineer import ROLE as CODE_ENGINEER
from .test_engineer import ROLE as TEST_ENGINEER
from .security_auditor import ROLE as SECURITY_AUDITOR
from .devops_engineer import ROLE as DEVOPS_ENGINEER
from .architect import ROLE as ARCHITECT
from .reviewer import ROLE as REVIEWER
from .researcher import ROLE as RESEARCHER
from .project_manager import ROLE as PROJECT_MANAGER
from .legal_reviewer import ROLE as LEGAL_REVIEWER
from .ui_designer import ROLE as UI_DESIGNER

ALL_ROLES = [
    CODE_ENGINEER,
    TEST_ENGINEER,
    SECURITY_AUDITOR,
    DEVOPS_ENGINEER,
    ARCHITECT,
    REVIEWER,
    RESEARCHER,
    PROJECT_MANAGER,
    LEGAL_REVIEWER,
    UI_DESIGNER,
]

ROLE_MAP = {role.id: role for role in ALL_ROLES}

__all__ = [
    "CODE_ENGINEER",
    "TEST_ENGINEER",
    "SECURITY_AUDITOR",
    "DEVOPS_ENGINEER",
    "ARCHITECT",
    "REVIEWER",
    "RESEARCHER",
    "PROJECT_MANAGER",
    "LEGAL_REVIEWER",
    "UI_DESIGNER",
    "ALL_ROLES",
    "ROLE_MAP",
]
