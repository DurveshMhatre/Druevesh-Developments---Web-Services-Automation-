@echo off
REM ══════════════════════════════════════════════════════════════
REM  AI Web Automation — One-Click Setup (Windows)
REM ══════════════════════════════════════════════════════════════
REM  Usage: setup.bat
REM  Installs all dependencies, validates config, and starts server.
REM ══════════════════════════════════════════════════════════════

echo.
echo ====================================================
echo   AI Web Automation - Setup Script
echo ====================================================
echo.

REM ── Step 1: Check Python ───────────────────────────────────
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Install from: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

REM ── Step 2: Create virtual environment ─────────────────────
echo [2/6] Setting up virtual environment...
if not exist "venv" (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
call venv\Scripts\activate
echo.

REM ── Step 3: Install Python dependencies ────────────────────
echo [3/6] Installing Python dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies.
    echo Check requirements.txt and your internet connection.
    pause
    exit /b 1
)
echo Dependencies installed successfully.
echo.

REM ── Step 4: Install Playwright browsers ────────────────────
echo [4/6] Installing Playwright Chromium browser...
playwright install chromium
if errorlevel 1 (
    echo WARNING: Playwright browser install failed.
    echo You can retry later with: playwright install chromium
)
echo.

REM ── Step 5: Check .env file ────────────────────────────────
echo [5/6] Checking configuration...
if not exist "config\.env" (
    echo WARNING: config\.env not found.
    echo Copying config\.env.example to config\.env...
    copy config\.env.example config\.env
    echo.
    echo IMPORTANT: Edit config\.env and fill in your API keys:
    echo   - GEMINI_API_KEY (from https://aistudio.google.com/app/apikey)
    echo   - GOOGLE_SHEETS_ID (from your spreadsheet URL)
    echo   - TELEGRAM_BOT_TOKEN (from @BotFather)
    echo   - WhatsApp credentials (Meta or whatsapp-web.js)
    echo.
    echo After editing config\.env, run this script again.
    pause
    exit /b 0
) else (
    echo config\.env found. Validating...
    python -c "from utils.config_validator import validate_env; validate_env(strict=False)"
)
echo.

REM ── Step 6: Run Google OAuth (if needed) ───────────────────
echo [6/6] Checking Google OAuth credentials...
if not exist "config\credentials\token.json" (
    echo First-time setup: running Google Sheets OAuth flow...
    echo A browser window will open — please authorize the application.
    python auth_sheets.py
    if errorlevel 1 (
        echo WARNING: OAuth setup failed. You can retry with: python auth_sheets.py
    ) else (
        echo OAuth authorized successfully!
    )
) else (
    echo Google OAuth token already exists.
)
echo.

REM ── Done ───────────────────────────────────────────────────
echo ====================================================
echo   Setup complete! Starting server...
echo ====================================================
echo.
echo Server will start on http://localhost:8000
echo Health check: http://localhost:8000/health
echo Press Ctrl+C to stop.
echo.

python -m server.app
