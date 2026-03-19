"""
Main WhatsApp bot orchestrator.

Routes incoming messages through the stage manager and conversation engine,
sends responses via the configured WhatsApp handler (Meta Cloud or whatsapp-web.js).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from config.settings import PACKAGES, WHATSAPP_MODE
from phase2_whatsapp import meta_cloud_api
from phase2_whatsapp.conversation_engine import process_message, recommend_package
from phase2_whatsapp.stage_manager import (
    Stage,
    advance,
    get_next_stage,
    get_stage,
    has_all_required_fields,
)
from phase2_whatsapp.templates import (
    ADMIN_NEW_INTERESTED_LEAD,
    INTERESTED_HANDOFF,
    NOT_INTERESTED_RESPONSE,
    PACKAGE_RECOMMENDATION,
    format_features_list,
    format_template,
)
from phase2_whatsapp.whatsapp_web_js import bridge as wjs_bridge
from utils.logger import get_logger
from utils.sheets_client import (
    append_conversation,
    append_leads,
    get_conversation_history,
    get_lead_by_phone,
    get_requirements,
    save_package_recommendation,
    save_requirements,
    update_lead_field,
    update_lead_status,
)
from utils.telegram_alert import send_alert

logger = get_logger(__name__)


# ── Send abstraction ─────────────────────────────────────────────

async def _send(phone: str, text: str) -> None:
    """Send a message using the active WhatsApp handler."""
    if WHATSAPP_MODE == "meta_cloud":
        await meta_cloud_api.send_text_message(phone, text)
    else:
        await wjs_bridge.send_message(phone, text)


# ══════════════════════════════════════════════════════════════════
#  MAIN HANDLER
# ══════════════════════════════════════════════════════════════════

async def handle_incoming_message(
    phone: str,
    message: str,
    name: str = "",
) -> None:
    """
    Process an incoming WhatsApp message end-to-end.

    1. Look up lead in Google Sheets
    2. Get current stage
    3. Load conversation history
    4. Pass to conversation engine → get AI response
    5. Send response via WhatsApp
    6. Save messages to Sheets
    7. Handle stage transitions
    """
    logger.info("Incoming message from %s: %s", phone, message[:100])

    # 1. Look up lead — if not found, auto-create so we never ignore a message
    lead = get_lead_by_phone(phone)
    if not lead:
        logger.info("New inbound sender %s — auto-creating lead entry.", phone)
        append_leads([{
            "name": name or "Unknown",
            "phone": phone,
            "phone_type": "mobile",
            "type": "Inbound",
            "city": "",
            "rating": 0,
            "reviews": 0,
            "score": 100,
            "website": "",
            "source": "inbound",
            "status": "In Conversation",
        }])
        lead = get_lead_by_phone(phone) or {
            "Name": name or "Unknown",
            "Phone": phone,
            "CurrentStage": "WELCOME",
        }

    # 2. Get current stage
    current_stage = get_stage(lead.get("CurrentStage", "WELCOME"))

    # Skip if terminal states
    if current_stage in (Stage.DONE, Stage.NOT_INTERESTED):
        logger.info("Lead %s is in terminal stage %s — ignoring.", phone, current_stage.value)
        return

    # 3. Load conversation history
    history = get_conversation_history(phone, limit=10)

    # 4. Build collected data from previous requirements
    existing_reqs = get_requirements(phone) or {}
    collected_data = {
        "business_name": existing_reqs.get("BusinessName", "") or lead.get("Name", ""),
        "services_description": existing_reqs.get("ServicesDescription", ""),
        "pages_needed": existing_reqs.get("PagesNeeded", ""),
        "features": existing_reqs.get("Features", ""),
        "budget": existing_reqs.get("Budget", ""),
        "design_preferences": existing_reqs.get("DesignPreferences", ""),
    }

    # 5. Save incoming message
    append_conversation(phone, "in", message, current_stage.value)
    update_lead_field(phone, "LastMessageAt", datetime.now().isoformat())

    # 6. Process with AI
    result = process_message(
        incoming_message=message,
        stage=current_stage,
        history=history,
        collected_data=collected_data,
    )

    response_text = result.get("response", "")
    new_data = result.get("data_collected", {})
    should_advance = result.get("should_advance_stage", False)
    is_not_interested = result.get("is_not_interested", False)

    # 7. Merge newly collected data
    for key, val in new_data.items():
        if val and str(val).strip():
            collected_data[key] = str(val).strip()

    # 8. Handle NOT INTERESTED
    if is_not_interested:
        response_text = format_template(
            NOT_INTERESTED_RESPONSE,
            business_name=collected_data.get("business_name", name or ""),
        )
        await _send(phone, response_text)
        append_conversation(phone, "out", response_text, Stage.NOT_INTERESTED.value)
        update_lead_status(phone, "Not Interested")
        update_lead_field(phone, "CurrentStage", Stage.NOT_INTERESTED.value)
        logger.info("Lead %s marked as Not Interested.", phone)
        return

    # 9. Handle stage advancement
    if should_advance:
        next_stage = get_next_stage(current_stage)

        if current_stage == Stage.WELCOME and next_stage == Stage.REQUIREMENTS:
            # Moving to requirements — send AI response
            await _send(phone, response_text)
            append_conversation(phone, "out", response_text, Stage.REQUIREMENTS.value)
            current_stage = advance(current_stage, Stage.REQUIREMENTS)
            update_lead_field(phone, "CurrentStage", Stage.REQUIREMENTS.value)
            update_lead_status(phone, "In Conversation")

        elif current_stage == Stage.REQUIREMENTS and next_stage == Stage.PACKAGE:
            # Save requirements first
            save_requirements(phone, collected_data)

            # Recommend package
            pkg = recommend_package(collected_data)
            pkg_text = format_template(
                PACKAGE_RECOMMENDATION,
                business_name=collected_data.get("business_name", ""),
                package_name=pkg["name"],
                price_display=pkg["price_display"],
                features_list=format_features_list(pkg["features"]),
            )

            # Send AI response + package recommendation
            await _send(phone, response_text)
            append_conversation(phone, "out", response_text, Stage.REQUIREMENTS.value)
            await asyncio.sleep(2)  # Small delay before package message
            await _send(phone, pkg_text)
            append_conversation(phone, "out", pkg_text, Stage.PACKAGE.value)

            current_stage = advance(current_stage, Stage.PACKAGE)
            update_lead_field(phone, "CurrentStage", Stage.PACKAGE.value)
            save_package_recommendation(phone, pkg["name"], pkg["price"])

        elif current_stage == Stage.PACKAGE and next_stage == Stage.DONE:
            # Client accepted — send handoff message
            handoff_text = format_template(
                INTERESTED_HANDOFF,
                business_name=collected_data.get("business_name", ""),
                phone=phone,
            )
            await _send(phone, handoff_text)
            append_conversation(phone, "out", handoff_text, Stage.DONE.value)

            current_stage = advance(current_stage, Stage.DONE)
            update_lead_field(phone, "CurrentStage", Stage.DONE.value)
            update_lead_status(phone, "Interested - Handoff")

            # Alert admin on Telegram
            rec_pkg = recommend_package(collected_data)
            admin_text = format_template(
                ADMIN_NEW_INTERESTED_LEAD,
                business_name=collected_data.get("business_name", ""),
                phone=phone,
                business_type=lead.get("Type", ""),
                city=lead.get("City", ""),
                requirements_summary="\n".join(
                    f"  • {k}: {v}" for k, v in collected_data.items() if v
                ),
                package_name=rec_pkg["name"],
                price_display=rec_pkg["price_display"],
            )
            send_alert(admin_text, level="info")
            logger.info("🎉 Lead %s converted! Admin notified.", phone)

    else:
        # Normal response — no stage change
        if not response_text:
            # AI returned empty response (rare edge case) — use safe fallback
            response_text = "Samajh gaya! Koi aur sawal ho toh puchiye. 😊"
            logger.warning("AI returned empty response for phone %s — using safe fallback.", phone)
        try:
            await _send(phone, response_text)
            append_conversation(phone, "out", response_text, current_stage.value)
        except Exception as send_exc:
            logger.error("Failed to send response to %s: %s", phone, send_exc)

        # Save partial requirements if in REQUIREMENTS stage
        if current_stage == Stage.REQUIREMENTS and any(new_data.values()):
            save_requirements(phone, collected_data)
