"""
Gemini-powered AI conversation handler.

Builds context-aware prompts including conversation history, stage info,
and business context, then extracts structured JSON responses.
"""

from __future__ import annotations

from typing import Any

from config.settings import (
    AGENT_NAME,
    COMPANY_NAME,
    PACKAGES,
    PORTFOLIO_URL,
    UPI_ID,
)
from phase2_whatsapp.stage_manager import Stage, get_missing_fields
from utils.gemini_client import generate_json
from utils.logger import get_logger
from utils.telegram_alert import send_alert

logger = get_logger(__name__)

# ══════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ══════════════════════════════════════════════════════════════════

_BASE_SYSTEM_PROMPT = """\
You are {agent_name}, a friendly and professional sales agent for {company_name}, \
a website development company. You are chatting with a potential client via WhatsApp.

COMPANY INFO:
- Company: {company_name}
- Portfolio: {portfolio_url}
- Payment: UPI ({upi_id})
- Packages:
{packages_text}

COMMUNICATION STYLE:
- Be warm, friendly, and professional
- Use Hindi/Hinglish naturally — match the client's language
- Use emojis sparingly (1-2 per message)
- Keep messages concise (max 3-4 short paragraphs)
- NEVER be pushy. If client says no, accept gracefully
- Sound like a real person, NOT a bot

CURRENT STAGE: {current_stage}
{stage_instructions}

CONVERSATION HISTORY (most recent):
{history_text}

COLLECTED DATA SO FAR:
{collected_data_text}

RESPOND STRICTLY AS JSON with this schema:
{{
  "response": "Your WhatsApp reply message text here",
  "data_collected": {{"field_name": "value", ...}},
  "should_advance_stage": true/false,
  "sentiment": "positive" | "neutral" | "negative",
  "is_not_interested": true/false
}}

RULES:
- "response" must be a natural, conversational reply
- "data_collected" should contain any NEW information the client just shared \
  (business_name, services_description, pages_needed, features, budget, design_preferences)
- "should_advance_stage" = true ONLY when all required info for current stage is collected
- "is_not_interested" = true ONLY if the client clearly declines / refuses
- If the client asks irrelevant questions, gently steer back to the topic
"""

_STAGE_INSTRUCTIONS = {
    Stage.WELCOME: (
        "GOAL: The client just received our intro message. Gauge their interest.\n"
        "- If they seem interested, ask about their business\n"
        "- If they ask what we do, explain briefly with examples\n"
        "- set should_advance_stage=true when client shows interest and is willing to talk"
    ),
    Stage.REQUIREMENTS: (
        "GOAL: Collect business requirements. You need these fields:\n"
        "- business_name (their business/shop name)\n"
        "- services_description (what they sell/do)\n"
        "- pages_needed (how many pages, or what pages they want)\n"
        "Optional: features, budget, design_preferences\n\n"
        "MISSING FIELDS: {missing_fields}\n\n"
        "Ask about missing fields naturally — DO NOT ask all at once.\n"
        "Set should_advance_stage=true ONLY when business_name, services_description, "
        "and pages_needed are ALL collected."
    ),
    Stage.PACKAGE: (
        "GOAL: You've already collected requirements. Now recommend a package.\n"
        "The package recommendation has been sent. Answer follow-up questions, "
        "address concerns, and guide toward acceptance.\n"
        "If the client agrees/accepts, set should_advance_stage=true.\n"
        "Share UPI ID for payment when asked."
    ),
}


def _format_packages() -> str:
    """Format package info for the system prompt."""
    lines: list[str] = []
    for pkg in PACKAGES.values():
        features = ", ".join(pkg["features"])
        lines.append(f"  • {pkg['name']}: {pkg['price_display']} — {features}")
    return "\n".join(lines)


def _format_history(history: list[dict[str, Any]]) -> str:
    """Format conversation history for the system prompt."""
    if not history:
        return "(No previous messages)"

    lines: list[str] = []
    for msg in history:
        direction = msg.get("Direction", msg.get("direction", ""))
        text = msg.get("Message", msg.get("message", ""))
        speaker = "CLIENT" if direction == "in" else "YOU"
        lines.append(f"[{speaker}]: {text}")
    return "\n".join(lines)


def _format_collected_data(data: dict[str, Any]) -> str:
    """Format collected data for the system prompt."""
    if not data:
        return "(Nothing collected yet)"
    lines = [f"  • {k}: {v}" for k, v in data.items() if v]
    return "\n".join(lines) if lines else "(Nothing collected yet)"


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def process_message(
    incoming_message: str,
    stage: Stage,
    history: list[dict[str, Any]],
    collected_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Process an incoming WhatsApp message using Gemini AI.

    Args:
        incoming_message: The client's message text.
        stage: Current conversation stage.
        history: Last N messages from the conversation history.
        collected_data: Previously collected requirement fields.

    Returns:
        Dict with keys: ``response``, ``data_collected``,
        ``should_advance_stage``, ``sentiment``, ``is_not_interested``.
    """
    collected_data = collected_data or {}

    # Build stage-specific instructions
    stage_instr = _STAGE_INSTRUCTIONS.get(stage, "")
    if stage == Stage.REQUIREMENTS:
        missing = get_missing_fields(collected_data)
        stage_instr = stage_instr.format(missing_fields=", ".join(missing) or "None")

    system_prompt = _BASE_SYSTEM_PROMPT.format(
        agent_name=AGENT_NAME,
        company_name=COMPANY_NAME,
        portfolio_url=PORTFOLIO_URL,
        upi_id=UPI_ID,
        packages_text=_format_packages(),
        current_stage=stage.value,
        stage_instructions=stage_instr,
        history_text=_format_history(history),
        collected_data_text=_format_collected_data(collected_data),
    )

    try:
        result = generate_json(system_prompt, incoming_message)

        # Handle parse errors
        if result.get("parse_error"):
            logger.warning("Gemini returned unparseable response — using fallback.")
            return _fallback_response(stage)

        # Validate required keys
        if "response" not in result:
            logger.warning("Gemini response missing 'response' key — using fallback.")
            return _fallback_response(stage)

        # Ensure defaults
        result.setdefault("data_collected", {})
        result.setdefault("should_advance_stage", False)
        result.setdefault("sentiment", "neutral")
        result.setdefault("is_not_interested", False)

        logger.info(
            "Gemini response: stage=%s sentiment=%s advance=%s",
            stage.value,
            result.get("sentiment"),
            result.get("should_advance_stage"),
        )
        return result

    except Exception as exc:
        logger.error("Conversation engine failed: %s", exc)
        send_alert(
            f"Conversation engine error:\n<pre>{exc}</pre>\n\n"
            f"Stage: {stage.value}\nMessage: {str(incoming_message)[:200]}",
            level="error",
        )
        return _fallback_response(stage)


def _fallback_response(stage: Stage) -> dict[str, Any]:
    """Generate a safe fallback response when Gemini fails."""
    fallbacks = {
        Stage.WELCOME: (
            "Namaste! 🙏 Main abhi thoda busy hoon, lekin jaldi reply karungi. "
            "Kya aap mujhe apna business ka naam bata sakte hain?"
        ),
        Stage.REQUIREMENTS: (
            "Dhanyawad! 😊 Mujhe thoda aur detail chahiye aapke business ke baare mein. "
            "Kya aap bata sakte hain ki aap kya services offer karte hain?"
        ),
        Stage.PACKAGE: (
            "Bahut accha! 😊 Agar aapko koi sawal hai package ke baare mein, "
            "to zaroor puchiye. Main yahan help karne ke liye hoon!"
        ),
    }
    return {
        "response": fallbacks.get(stage, "Dhanyawad! Main jaldi reply karungi. 😊"),
        "data_collected": {},
        "should_advance_stage": False,
        "sentiment": "neutral",
        "is_not_interested": False,
    }


def recommend_package(collected_data: dict[str, Any]) -> dict[str, Any]:
    """
    Choose the best package based on collected requirements.

    Returns the package dict from ``PACKAGES``.
    """
    pages = str(collected_data.get("pages_needed", "")).lower()
    features = str(collected_data.get("features", "")).lower()
    budget = str(collected_data.get("budget", "")).lower()

    # Simple rule-based recommendation
    if any(kw in features for kw in ["ecommerce", "e-commerce", "online store", "payment"]):
        return PACKAGES["Premium"]
    if any(kw in features for kw in ["booking", "admin", "dashboard"]):
        return PACKAGES["Premium"]

    # Check page count
    try:
        page_count = int("".join(c for c in pages if c.isdigit()) or "0")
    except ValueError:
        page_count = 0

    if page_count > 7:
        return PACKAGES["Premium"]
    if page_count > 3:
        return PACKAGES["Business"]

    # Check budget hints
    if any(kw in budget for kw in ["low", "kam", "sasta", "cheap", "basic"]):
        return PACKAGES["Starter"]
    if any(kw in budget for kw in ["premium", "best", "full", "unlimited"]):
        return PACKAGES["Premium"]

    # Default to Business (best value)
    return PACKAGES["Business"]
