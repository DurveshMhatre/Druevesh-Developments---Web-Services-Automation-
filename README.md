# AI Web Automation — Lead Scraper + WhatsApp Bot

Automated pipeline that scrapes businesses without websites, scores them, and cold-outreaches via WhatsApp with an AI-powered conversation bot.

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
copy config\.env.example .env       # Windows
# cp config/.env.example .env       # Mac/Linux
```

Edit `.env` and fill in:
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
├── config/          # Settings, .env, OAuth credentials
├── phase1_leads/    # Google Maps + JustDial scrapers, scorer, dedup
├── phase2_whatsapp/ # WhatsApp bot, conversation engine, templates
├── utils/           # Sheets client, Gemini client, Telegram alerts, logger
├── server/          # FastAPI server + APScheduler
└── tests/           # Unit + integration tests
```

## Monthly Cost: ₹0

All tools used are free tier: Gemini API, Google Sheets, Telegram Bot, Playwright.
