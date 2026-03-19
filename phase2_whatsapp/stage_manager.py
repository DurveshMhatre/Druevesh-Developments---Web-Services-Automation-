"""
3-stage conversation state machine.

Stages:
    1. WELCOME   — cold outreach / intro
    2. REQUIREMENTS — collect business details
    3. PACKAGE   — recommend package + share price / UPI
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


class Stage(str, Enum):
    """Conversation stages."""

    WELCOME = "WELCOME"
    REQUIREMENTS = "REQUIREMENTS"
    PACKAGE = "PACKAGE"
    DONE = "DONE"
    NOT_INTERESTED = "NOT_INTERESTED"


# Valid forward transitions
_TRANSITIONS: dict[Stage, list[Stage]] = {
    Stage.WELCOME: [Stage.REQUIREMENTS, Stage.NOT_INTERESTED],
    Stage.REQUIREMENTS: [Stage.PACKAGE, Stage.NOT_INTERESTED],
    Stage.PACKAGE: [Stage.DONE, Stage.NOT_INTERESTED],
    Stage.DONE: [],
    Stage.NOT_INTERESTED: [],
}

# Fields we need to collect during REQUIREMENTS
REQUIRED_FIELDS: list[str] = [
    "business_name",
    "services_description",
    "pages_needed",
]

# Optional but nice to have
OPTIONAL_FIELDS: list[str] = [
    "features",
    "budget",
    "design_preferences",
]


def get_stage(stage_str: str) -> Stage:
    """Parse a stage string into its ``Stage`` enum value."""
    try:
        return Stage(stage_str.upper().strip())
    except (ValueError, AttributeError):
        return Stage.WELCOME


def can_advance(current: Stage, target: Stage) -> bool:
    """Return ``True`` if *current → target* is a valid transition."""
    return target in _TRANSITIONS.get(current, [])


def advance(current: Stage, target: Stage) -> Stage:
    """
    Attempt to transition from *current* to *target*.

    Returns the new stage if valid, otherwise returns *current* unchanged.
    """
    if can_advance(current, target):
        logger.info("Stage transition: %s → %s", current.value, target.value)
        return target
    logger.warning("Invalid transition: %s → %s — staying at %s", current.value, target.value, current.value)
    return current


def get_next_stage(current: Stage) -> Stage | None:
    """Return the natural next stage (forward only), or ``None`` if the flow is complete."""
    forward_map: dict[Stage, Stage] = {
        Stage.WELCOME: Stage.REQUIREMENTS,
        Stage.REQUIREMENTS: Stage.PACKAGE,
        Stage.PACKAGE: Stage.DONE,
    }
    return forward_map.get(current)


def has_all_required_fields(collected_data: dict[str, Any]) -> bool:
    """Check whether all required requirement fields have been collected."""
    for field in REQUIRED_FIELDS:
        val = collected_data.get(field, "")
        if not val or str(val).strip() == "":
            return False
    return True


def get_missing_fields(collected_data: dict[str, Any]) -> list[str]:
    """Return a list of required fields that are still missing."""
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        val = collected_data.get(field, "")
        if not val or str(val).strip() == "":
            missing.append(field)
    return missing
