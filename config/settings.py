"""
Central configuration module.

Loads all settings from environment variables (.env file) with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ─────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CREDENTIALS_DIR = CONFIG_DIR / "credentials"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Load .env — check config/ first (where the file lives), then project root
_env_config = CONFIG_DIR / ".env"
_env_root = PROJECT_ROOT / ".env"
if _env_config.exists():
    load_dotenv(_env_config)
elif _env_root.exists():
    load_dotenv(_env_root)

# ── AI & Data Config ──────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")

# OAuth credentials paths
OAUTH_CREDENTIALS_FILE: Path = CREDENTIALS_DIR / "oauth_credentials.json"
OAUTH_TOKEN_FILE: Path = CREDENTIALS_DIR / "token.json"

# ── WhatsApp Mode ─────────────────────────────────────────────────
WHATSAPP_MODE: str = os.getenv("WHATSAPP_MODE", "meta_cloud")  # "meta_cloud" or "whatsapp_web_js"

# ── Meta WhatsApp Cloud API (Option A) ────────────────────────────
META_PHONE_NUMBER_ID: str = os.getenv("META_PHONE_NUMBER_ID", "")
META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
META_VERIFY_TOKEN: str = os.getenv("META_VERIFY_TOKEN", "your_custom_verify_token")
META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")

# ── Telegram Admin Alerts ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Business Config ──────────────────────────────────────────────
COMPANY_NAME: str = os.getenv("COMPANY_NAME", "YourCompany")
AGENT_NAME: str = os.getenv("AGENT_NAME", "Priya")
PORTFOLIO_URL: str = os.getenv("PORTFOLIO_URL", "https://yourwebsite.com")
UPI_ID: str = os.getenv("UPI_ID", "name@upi")

# ── Package Pricing ──────────────────────────────────────────────
PACKAGES = {
    "Starter": {
        "name": "Starter",
        "price": 9999,
        "price_display": "₹9,999",
        "features": [
            "Professional 3-page website",
            "Mobile responsive design",
            "Contact form integration",
            "Basic SEO setup",
            "1 month free support",
        ],
    },
    "Business": {
        "name": "Business",
        "price": 19999,
        "price_display": "₹19,999",
        "features": [
            "Up to 7-page website",
            "Premium responsive design",
            "Google Maps integration",
            "WhatsApp chat button",
            "Advanced SEO + Google My Business",
            "Social media integration",
            "3 months free support",
        ],
    },
    "Premium": {
        "name": "Premium",
        "price": 34999,
        "price_display": "₹34,999",
        "features": [
            "Unlimited pages",
            "Custom UI/UX design",
            "Online booking / e-commerce",
            "Payment gateway integration",
            "Full SEO + analytics dashboard",
            "Admin panel",
            "6 months free support",
        ],
    },
}

# ── Scraper Config ───────────────────────────────────────────────
TARGET_CITIES: list[str] = [
    c.strip()
    for c in os.getenv("TARGET_CITIES", "Delhi,Mumbai,Pune").split(",")
    if c.strip()
]

BUSINESS_TYPES: list[str] = [
    b.strip()
    for b in os.getenv("BUSINESS_TYPES", "Restaurant,Clinic,Salon,Gym,Retail").split(",")
    if b.strip()
]

HIGH_VALUE_TYPES: set[str] = {"Salon", "Clinic", "Restaurant", "Gym", "Spa", "Dental"}

SCRAPE_SCHEDULE_HOUR: int = int(os.getenv("SCRAPE_SCHEDULE_HOUR", "6"))
MAX_COLD_MESSAGES_PER_DAY: int = int(os.getenv("MAX_COLD_MESSAGES_PER_DAY", "12"))

# ── WhatsApp-web.js Node server ──────────────────────────────────
WHATSAPP_WEB_JS_URL: str = os.getenv("WHATSAPP_WEB_JS_URL", "http://localhost:3001")

# ── FastAPI Server ───────────────────────────────────────────────
SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
