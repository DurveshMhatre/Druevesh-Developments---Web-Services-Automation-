You are an expert full-stack Python/Node.js engineer specializing in automation, web scraping, and AI integrations. Your task is to audit, fix, and optimize a lead-generation WhatsApp automation system for a web development AI Freelance Web services operating on a **strict $0 budget**. All solutions must use free-tier services only.

---

## 📋 SYSTEM OVERVIEW

**Business Workflow:**
```
1. SCRAPE: Find businesses on Google Maps/JustDial in Mumbai/Delhi/Pune WITHOUT websites
2. FILTER: Keep only leads with valid phone numbers + no website URL
3. SCORE: Rank leads by business type value, rating, review count
4. OUTREACH: Send personalized WhatsApp cold messages via WhatsApp Cloud API or whatsapp-web.js
5. CONVERSE: Use Gemini 2.5 Flash API (free tier) to handle replies, qualify leads, collect requirements
6. CONVERT: Recommend web dev packages (₹9,999-₹34,999), schedule appointments, handoff to human
7. TRACK: Log all interactions to Google Sheets (free), send admin alerts via Telegram Bot (free)
```

**Current Tech Stack (All Free Tier):**
- Python 3.10+, FastAPI, APScheduler, Playwright, google-genai SDK
- WhatsApp: Meta Cloud API (free 1,000 convos/month) OR whatsapp-web.js fallback
- AI: Gemini 2.5 Flash (free tier: 1,500 requests/day, 15 RPM limit)
- Storage: Google Sheets API (free quota)
- Alerts: Telegram Bot API (unlimited free)
- Hosting: Render.com free tier or local machine

**GitHub Repo:** https://github.com/DurveshMhatre/Druevesh-Developments---Web-Services-Automation-

---

## 🐛 CRITICAL BUGS TO FIX (Priority: HIGH)

### 1. Regex Bug in Phone Number Cleaning (`phase1_leads/google_maps_scraper.py`)
```python
# ❌ BUG: This removes only literal "D", not non-digit characters
digits = re.sub(r"D", "", raw_phone)

# ✅ FIX: Escape the backslash to match non-digit characters
digits = re.sub(r"\D", "", raw_phone)
```
**Impact**: Phone numbers are not cleaned properly → leads with formatting like "+91 98765 43210" fail validation.

### 2. Async Event Loop Race Condition (`phase1_leads/google_maps_scraper.py`)
```python
# ❌ BUG: asyncio.run() inside ThreadPoolExecutor causes "RuntimeError: This event loop is already running"
if loop and loop.is_running():
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, _scrape_async(city, business_type)).result()

# ✅ FIX: Use asyncio.to_thread() (Python 3.9+) or nest the coroutine properly
if loop and loop.is_running():
    return asyncio.run_coroutine_threadsafe(_scrape_async(city, business_type), loop).result()
```

### 3. Missing Deduplication Module (`server/scheduler.py`)
```python
# ❌ BUG: Code comments mention dedup.py but file is missing; fallback dedup is phone-only
# ✅ FIX: Create utils/dedup.py with fuzzy matching on business name + address + phone
# Use rapidfuzz (free) for fuzzy string matching to avoid duplicate leads across scrapers
```

### 4. Non-Thread-Safe Gemini Rate Limiter (`utils/gemini_client.py`)
```python
# ❌ BUG: _request_timestamps is a module-level list accessed by multiple threads
# ✅ FIX: Use threading.Lock() or switch to asyncio.Lock() for async safety
import threading
_rate_limit_lock = threading.Lock()

def _wait_for_rate_limit() -> None:
    with _rate_limit_lock:
        # existing logic here
```

### 5. WhatsApp Webhook Security Gap (`server/app.py`)
```python
# ❌ BUG: Meta webhook verification doesn't validate X-Hub-Signature-256
# ✅ FIX: Add HMAC-SHA256 signature verification using META_APP_SECRET
import hmac, hashlib

def verify_signature(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### 6. Missing whatsapp-web.js Bridge (`phase2_whatsapp/whatsapp_web_js/bridge.py`)
```python
# ❌ BUG: bot.py imports wjs_bridge but file may not exist or be properly typed
# ✅ FIX: Create robust bridge.py with:
# - Async HTTP client to communicate with Node.js server on localhost:3001
# - Retry logic with exponential backoff
# - QR code status polling for initial auth
# - Message queue for offline handling
```

---

## ⚙️ ARCHITECTURE IMPROVEMENTS (Priority: MEDIUM)

### 7. Add Circuit Breaker for External APIs
```python
# Create utils/circuit_breaker.py
# - Track failure counts for Gemini, WhatsApp API, Google Sheets
# - Auto-pause requests after N failures, retry after cooldown
# - Prevent cascade failures when one service is down
```

### 8. Implement Proper Browser Lifecycle Management (Playwright)
```python
# In google_maps_scraper.py:
# - Add browser context timeout (max 5 mins per scrape)
# - Use try/finally to ensure browser.close() always runs
# - Add screenshot on failure for debugging (already partially implemented)
# - Rotate user agents + add random delays to avoid detection
```

### 9. Add Message Queue for WhatsApp Sends
```python
# Create utils/message_queue.py
# - Queue outgoing messages with priority (new leads > follow-ups)
# - Rate-limit sends to respect WhatsApp's 1 msg/sec limit
# - Retry failed sends up to 3x with jittered delays
# - Log all send attempts to Sheets for audit
```

### 10. Enhance Phone Number Validation for India
```python
# Replace simplistic validation with:
def validate_indian_phone(phone: str) -> tuple[bool, str]:
    # Remove country code, spaces, dashes
    clean = re.sub(r"[\s\-\(\)]", "", phone)
    if clean.startswith("91"): clean = clean[2:]
    if clean.startswith("0"): clean = clean[1:]
    
    # Valid Indian mobile: 10 digits, starts with 6/7/8/9
    if len(clean) == 10 and clean[0] in "6789" and clean.isdigit():
        return True, f"+91{clean}"
    return False, "Invalid Indian mobile number"
```

---

## 💰 $0 BUDGET OPTIMIZATIONS (Critical)

### 11. Enforce Gemini API Free Tier Limits
```python
# In utils/gemini_client.py:
# - Track daily request count in memory + reset at midnight IST
# - Implement request queuing when approaching 1,500/day limit
# - Add fallback to Claude Haiku (if user adds key) or local small model
# - Cache common responses (e.g., package details) to reduce API calls
```

### 12. Optimize WhatsApp Cloud API Usage
```python
# Meta free tier: 1,000 service conversations/month (~33/day)
# Strategy:
# - Only message HIGH_VALUE_TYPES first (Salon, Clinic, Restaurant)
# - Use 3-message max sequence: Intro → Value Prop → Call-to-Action
# - Auto-stop outreach if lead doesn't reply after 2 follow-ups
# - Track conversation_id to avoid re-counting within 24h window
```

### 13. Reduce Google Sheets API Calls
```python
# Sheets free tier: 300 requests/minute/project, 500/day for writes
# Optimizations:
# - Batch append leads (write 10-20 rows per API call)
# - Cache lead lookups in memory with 5-min TTL
# - Use conditional updates: only write if data changed
# - Compress conversation history: store only last 5 messages
```

### 14. Add Local Fallback Storage
```python
# Create utils/local_storage.py
# - If Sheets API quota exhausted, write to local JSON/CSV
# - Sync to Sheets when quota resets (midnight)
# - Ensure no data loss during free-tier limits
```

---

## 🧪 TESTING & RELIABILITY

### 15. Add Comprehensive Unit Tests
```python
# tests/ structure:
# - test_phone_validation.py
# - test_gemini_rate_limit.py  
# - test_lead_dedup.py
# - test_whatsapp_bridge.py
# Use pytest + pytest-asyncio, mock external APIs with responses library
```

### 16. Add Health Checks & Monitoring
```python
# Create utils/health.py:
# - /health endpoint returns: gemini_quota_remaining, whatsapp_quota, sheets_quota
# - Log daily usage stats to Telegram admin
# - Auto-pause non-critical jobs if quotas < 10%
```

### 17. Implement Graceful Degradation
```python
# If Gemini API fails:
# 1. Retry with exponential backoff (already implemented)
# 2. Fallback to pre-written template responses for common queries
# 3. Queue message for human review if AI unavailable > 5 mins

# If WhatsApp fails:
# 1. Retry via alternate method (Cloud API ↔ whatsapp-web.js)
# 2. Send Telegram alert to admin with lead details
# 3. Queue message for manual send later
```

---

## 📦 DEPLOYMENT & MAINTENANCE

### 18. Dockerize for Easy Deployment
```dockerfile
# Dockerfile improvements:
# - Multi-stage build to reduce image size
# - Add healthcheck instruction
# - Use non-root user for security
# - Include playwright dependencies pre-installed
```

### 19. Add .env.example with Clear Documentation
```bash
# config/.env.example should include:
GEMINI_API_KEY=your_key_here  # Get free key: https://aistudio.google.com/app/apikey
# FREE TIER LIMIT: 1,500 requests/day, 15 RPM
META_ACCESS_TOKEN=your_token  # From Meta Developer Portal
# FREE TIER: 1,000 conversations/month
WHATSAPP_MODE=meta_cloud      # Options: "meta_cloud" or "whatsapp_web_js"
# ... add comments explaining each free-tier limit
```

### 20. Create One-Click Setup Script
```bash
# setup.sh for Linux/Mac:
# 1. Install Python dependencies
# 2. Install Playwright browsers
# 3. Validate .env variables
# 4. Run OAuth flow for Google Sheets
# 5. Start server with proper logging
# Include clear error messages for common setup issues
```

---

## 🎯 DELIVERABLES FOR ANTIGRAVITY

1. **Fix all HIGH priority bugs** with tested code changes
2. **Implement $0 budget safeguards** to prevent quota exhaustion
3. **Add missing modules**: dedup.py, circuit_breaker.py, message_queue.py, local_storage.py
4. **Write/update tests** for critical paths (phone validation, rate limiting, dedup)
5. **Update documentation**: README.md with troubleshooting guide for free-tier limits
6. **Provide a migration guide** for users switching between WhatsApp modes
7. **Add monitoring dashboard** (simple CLI or Telegram-based) showing quota usage

---

## 🚫 CONSTRAINTS (Non-Negotiable)

- **NO paid services**: All solutions must work within free tiers
- **NO breaking changes**: Maintain backward compatibility with existing .env structure
- **NO external dependencies beyond free tier**: Avoid libraries requiring paid API keys
- **Privacy-first**: Never store client phone numbers/messages outside user's Google Sheets
- **Compliance**: Respect WhatsApp Business Policy, Google Maps ToS, and Indian spam regulations

---

## ✅ SUCCESS CRITERIA

The system should:
1. Run 24/7 on a free Render.com instance or local machine without crashing
2. Stay within all API free-tier limits automatically (no manual intervention)
3. Successfully scrape 50-100 qualified leads/day in target cities
4. Convert 5-10% of messaged leads into appointments
5. Provide clear admin alerts when human attention is needed
6. Recover gracefully from network failures, API outages, or quota limits

---

> **Antigravity, please proceed step-by-step**: Start with the critical regex bug and async loop fix, then move to rate limiting thread-safety, then implement the missing modules. After each fix, provide a brief test case to verify the change. Prioritize stability and quota management over new features.

Let me know if you need clarification on any part of the codebase or business logic! 🛠️✨