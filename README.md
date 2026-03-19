# AI Web Automation — Lead Scraper + WhatsApp Bot

Automated pipeline that scrapes businesses without websites, scores them, and cold-outreaches via WhatsApp with an AI-powered conversation bot. Runs entirely on free-tier services (₹0/month).

## Features

- 🔍 **Lead Scraping** — Google Maps + JustDial, with fuzzy deduplication
- 📱 **WhatsApp Bot** — AI-powered conversations via Gemini 2.5 Flash
- 📊 **Google Sheets** — Auto-managed lead database with caching
- 🔄 **Circuit Breaker** — Auto-recovery from API failures
- 📬 **Message Queue** — Priority-based sending with rate limiting
- 🛡️ **Webhook Security** — HMAC-SHA256 signature verification
- 💾 **Local Fallback** — Zero data loss when Sheets quota is exhausted
- 📈 **Quota Monitoring** — `/health` endpoint with real-time usage stats

## Quick Start

### 1. Install Python dependencies

```bash
cd ai-web-automation
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up credentials

```bash
# Copy the env template
copy config\.env.example config\.env     # Windows
# cp config/.env.example config/.env     # Mac/Linux
```

Edit `config/.env` and fill in:
- `GEMINI_API_KEY` — from https://aistudio.google.com/app/apikey
- `GOOGLE_SHEETS_ID` — the spreadsheet ID from its URL
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — from @BotFather
- WhatsApp credentials (Meta or whatsapp-web.js mode)

Place your OAuth credentials file at:
```
config/credentials/oauth_credentials.json
```

### 3. First run (OAuth authorization)

The first time you access Google Sheets, a browser window will open asking you to authorize. After that, a `token.json` is saved and subsequent runs are automatic.

### 4. If using whatsapp-web.js (Option B)

```bash
cd phase2_whatsapp/whatsapp_web_js
npm install
npm start
# Scan the QR code with WhatsApp
```

### 5. Start the server

```bash
cd ai-web-automation
python -m server.app
```

This starts:
- FastAPI server on `http://localhost:8000`
- Daily scraper (6 AM)
- Outreach scheduler (every 2 hrs, 9 AM – 8 PM)
- Daily Telegram summary (9 PM)

### 6. Manual test scrape

```bash
python -c "from phase1_leads.google_maps_scraper import scrape; print(scrape('Delhi', 'Restaurant'))"
```

## Run Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
ai-web-automation/
├── config/              # Settings, .env, OAuth credentials
├── phase1_leads/        # Google Maps + JustDial scrapers, scorer, dedup
├── phase2_whatsapp/     # WhatsApp bot, conversation engine, templates
│   └── whatsapp_web_js/ # Node.js bridge for whatsapp-web.js (Option B)
├── utils/               # Sheets client, Gemini client, Telegram alerts
│   ├── circuit_breaker.py   # Auto-recovery from API failures
│   ├── message_queue.py     # Priority queue for WhatsApp sends
│   └── local_storage.py     # Fallback when Sheets quota exhausted
├── server/              # FastAPI server + APScheduler
├── tests/               # Unit + integration tests
└── data/                # Local fallback storage (auto-created)
```

## Free-Tier Limits & Troubleshooting

| Service | Free Tier Limit | What Happens When Exhausted |
|---------|----------------|----------------------------|
| **Gemini 2.5 Flash** | 1,500 req/day, 15 RPM | Requests blocked until midnight IST, auto-resumes |
| **WhatsApp Cloud API** | 1,000 convos/month | Outreach paused, admin alerted via Telegram |
| **Google Sheets** | 300 reads/min, 60 writes/min | Falls back to local JSON storage, syncs later |
| **Telegram Bot** | Unlimited | Always available |
| **Playwright** | N/A (local) | No limits, runs headless Chromium |

### Common Issues

**"Gemini daily quota exhausted"**
- The system automatically blocks requests after 1,450 calls/day (safety margin)
- Check quota: `GET http://localhost:8000/health` → `gemini_quota.daily_remaining`
- Resets at midnight IST automatically

**"Circuit breaker OPEN"**
- A service failed too many times consecutively
- The circuit breaker auto-recovers after the cooldown period (60-120s)
- Check: `GET http://localhost:8000/health`

**"Failed to append to Sheets — falling back to local storage"**
- Sheets API quota exhausted; data saved to `data/local_fallback/`
- Auto-syncs when quota resets; zero data loss

### Switching WhatsApp Modes

Switch between Meta Cloud API and whatsapp-web.js by changing `WHATSAPP_MODE` in your `.env`:

```bash
# Option A: Meta Cloud API (recommended, most reliable)
WHATSAPP_MODE=meta_cloud

# Option B: whatsapp-web.js (requires Node.js, no Meta account needed)
WHATSAPP_MODE=whatsapp_web_js
```

After switching, restart the server. If using whatsapp-web.js, ensure the Node server is running first.

## Monthly Cost: ₹0

All tools used are free tier: Gemini API, Google Sheets, Telegram Bot, Meta WhatsApp Cloud API, Playwright.
