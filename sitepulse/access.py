"""Role-based, least-privilege access to project data.

Each role sees only the projects it needs. Unknown roles get nothing (deny by default).
"""
import json
from pathlib import Path

DEFAULT_ROLES = {
    "executive":    {"projects": ["P1", "P2", "P3"], "can_see_quarantine": False},
    "data_steward": {"projects": ["P1", "P2", "P3"], "can_see_quarantine": True},
    "pm_P1":        {"projects": ["P1"], "can_see_quarantine": False},
    "pm_P2":        {"projects": ["P2"], "can_see_quarantine": False},
    "pm_P3":        {"projects": ["P3"], "can_see_quarantine": False},
}


def load_roles(path=None):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text())
    return DEFAULT_ROLES


def permissions(role, roles=None):
    roles = roles or DEFAULT_ROLES
    if role not in roles:
        raise PermissionError(f"Role '{role}' is not authorized (deny by default)")
    return roles[role]
