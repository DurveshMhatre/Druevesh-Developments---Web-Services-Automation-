"""
FastAPI web server.

Serves webhook endpoints for WhatsApp (both Meta Cloud API and whatsapp-web.js)
and starts the APScheduler on startup.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response

from config.settings import META_VERIFY_TOKEN, WHATSAPP_MODE
from phase2_whatsapp.bot import handle_incoming_message
from phase2_whatsapp.meta_cloud_api import parse_webhook_message
from server.scheduler import start_scheduler, shutdown_scheduler
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on startup, shut down on exit."""
    logger.info("🚀 Starting AI Web Automation server...")
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
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "whatsapp_mode": WHATSAPP_MODE}


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
    body = await request.json()
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
