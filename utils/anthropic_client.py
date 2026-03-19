# DEPRECATED — Not used. All AI calls now route through utils.gemini_client.
# Kept for reference only. Do not import from this module.
"""
DEPRECATED: This module is no longer used.
The project now exclusively uses utils.gemini_client (Google Gemini 2.5 Flash).

The anthropic package is NOT in requirements.txt.
Attempting to import from this module will raise RuntimeError.
"""

from __future__ import annotations

from typing import Any


def generate(system_prompt: str, user_message: str) -> str:
    """DEPRECATED — raises RuntimeError. Use utils.gemini_client.generate instead."""
    raise RuntimeError(
        "anthropic_client is DEPRECATED. Use 'from utils.gemini_client import generate' instead."
    )


def generate_json(system_prompt: str, user_message: str) -> dict[str, Any]:
    """DEPRECATED — raises RuntimeError. Use utils.gemini_client.generate_json instead."""
    raise RuntimeError(
        "anthropic_client is DEPRECATED. Use 'from utils.gemini_client import generate_json' instead."
    )
