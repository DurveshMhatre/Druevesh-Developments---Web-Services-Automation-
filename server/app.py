"""
FastAPI web server.

Serves webhook endpoints for WhatsApp (both Meta Cloud API and whatsapp-web.js)
and starts the APScheduler on startup.

Includes HMAC-SHA256 webhook signature verification for security.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response

from config.settings import META_VERIFY_TOKEN, META_APP_SECRET, WHATSAPP_MODE
from phase2_whatsapp.bot import handle_incoming_message
from phase2_whatsapp.meta_cloud_api import parse_webhook_message
from server.scheduler import start_scheduler, shutdown_scheduler
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Webhook signature verification ──────────────────────────────
def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify the X-Hub-Signature-256 header from Meta's webhook.

    Handles both ``sha256=<hex>`` (standard Meta format) and raw hex.

    Args:
        payload: Raw request body bytes.
        signature: Value of X-Hub-Signature-256 header.
        secret: META_APP_SECRET from environment.

    Returns:
        True if signature is valid.
    """
    if not secret or not signature:
        logger.debug("Signature verification skipped: secret=%s, sig=%s",
                     bool(secret), bool(signature))
        return False

    expected = hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()

    # Handle both "sha256=<hex>" and raw hex formats
    if signature.startswith("sha256="):
        sig_hex = signature[7:]  # strip "sha256=" prefix
    else:
        sig_hex = signature

    is_valid = hmac.compare_digest(expected, sig_hex)
    if not is_valid:
        logger.debug(
            "Webhook signature mismatch: expected=%s, received=%s",
            expected[:16] + "...", sig_hex[:16] + "...",
        )
    return is_valid


# ── Lifespan (startup / shutdown) ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config, start scheduler on startup, shut down on exit."""
    logger.info("🚀 Starting AI Web Automation server...")

    # Validate environment variables at startup
    try:
        from utils.config_validator import validate_env
        validate_env(strict=False)  # Log warnings, don't crash
    except Exception as exc:
        logger.error("Config validation error: %s", exc)

    start_scheduler()
    yield
    shutdown_scheduler()
    logger.info("🛑 Server shut down.")


app = FastAPI(
    title="AI Web Automation",
    description="Lead scraping + WhatsApp bot automation server",
    version="1.0.0",
    lifespan=lifespan,
)


# ══════════════════════════════════════════════════════════════════
#  HEALTH CHECK (enhanced with quota reporting)
# ══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """Return system health with quota usage stats."""
    from utils.gemini_client import get_quota_status

    gemini_quota = get_quota_status()

    return {
        "status": "ok",
        "whatsapp_mode": WHATSAPP_MODE,
        "gemini_quota": gemini_quota,
    }


@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check for debugging (includes local storage, circuit breakers)."""
    from utils.gemini_client import get_quota_status
    from utils.local_storage import get_status as local_status
    from utils.circuit_breaker import gemini_breaker, whatsapp_breaker, sheets_breaker

    return {
        "status": "ok",
        "whatsapp_mode": WHATSAPP_MODE,
        "gemini_quota": get_quota_status(),
        "local_storage": local_status(),
        "circuit_breakers": {
            "gemini": gemini_breaker.get_status(),
            "whatsapp": whatsapp_breaker.get_status(),
            "sheets": sheets_breaker.get_status(),
        },
    }


# ══════════════════════════════════════════════════════════════════
#  META WHATSAPP CLOUD API WEBHOOK (Option A)
# ══════════════════════════════════════════════════════════════════

@app.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    """Handle Meta's webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        logger.info("Meta webhook verified successfully.")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("Meta webhook verification failed.")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook/whatsapp")
async def meta_webhook(request: Request):
    """Receive incoming messages from Meta WhatsApp Cloud API."""
    # Read raw body for signature verification
    raw_body = await request.body()

    # Verify HMAC-SHA256 signature if META_APP_SECRET is configured
    if META_APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(raw_body, signature, META_APP_SECRET):
            logger.warning("Meta webhook: invalid signature — rejecting payload.")
            return Response(content="Invalid signature", status_code=403)

    import json
    body = json.loads(raw_body)
    parsed = parse_webhook_message(body)

    if parsed and parsed.get("message"):
        # Process in background to respond quickly to Meta
        asyncio.create_task(
            handle_incoming_message(
                phone=parsed["phone"],
                message=parsed["message"],
                name=parsed.get("name", ""),
            )
        )

    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
#  WHATSAPP-WEB.JS WEBHOOK (Option B)
# ══════════════════════════════════════════════════════════════════

@app.post("/webhook/incoming")
async def wjs_webhook(request: Request):
    """Receive incoming messages from the Node.js whatsapp-web.js server."""
    body: dict[str, Any] = await request.json()
    phone = body.get("phone", "")
    message = body.get("message", "")
    name = body.get("name", "")

    if phone and message:
        asyncio.create_task(
            handle_incoming_message(phone=phone, message=message, name=name)
        )

    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    from config.settings import SERVER_HOST, SERVER_PORT

    uvicorn.run(
        "server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )
