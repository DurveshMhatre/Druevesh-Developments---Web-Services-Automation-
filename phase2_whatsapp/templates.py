"""
Pre-written message templates for key conversation moments.

Templates use Python string formatting (``{variable}``) and support
Hindi/Hinglish/English variations.
"""

from __future__ import annotations

from config.settings import AGENT_NAME, COMPANY_NAME, PORTFOLIO_URL, UPI_ID

# ══════════════════════════════════════════════════════════════════
#  WELCOME — First cold-outreach message
# ══════════════════════════════════════════════════════════════════

WELCOME_MESSAGE = (
    "🙏 Namaste {business_name} ji!\n\n"
    "Main {agent_name} hoon, {company_name} se.\n\n"
    "Maine dekha ki aapka business bahut accha chal raha hai — "
    "lekin abhi tak aapki koi website nahi hai.\n\n"
    "Aaj kal 80% customers pehle online search karte hain. "
    "Ek professional website se aapke customers aur badh sakte hain! 📈\n\n"
    "Kya aap 2 minute baat kar sakte hain? Main aapko ek affordable "
    "plan ke baare mein bata sakti hoon. 😊"
)

# ══════════════════════════════════════════════════════════════════
#  FOLLOW-UPS — If no reply after 24/48/72 hrs
# ══════════════════════════════════════════════════════════════════

FOLLOW_UP_1 = (
    "Hi {business_name} ji! 👋\n\n"
    "Mera pichla message dekha aapne? Main {agent_name}, {company_name} se.\n\n"
    "Agar aapko website mein interest hai to bas 'Haan' bol dijiye — "
    "main poori details share kar dungi! 😊"
)

FOLLOW_UP_2 = (
    "Namaste {business_name} ji! 🙏\n\n"
    "Bas ek last reminder — hum ₹9,999 se starting professional websites "
    "banate hain jo mobile par bhi perfect dikhti hain.\n\n"
    "Agar interest ho to reply kar dijiye, warna main aapko disturb nahi karungi. 😊"
)

FOLLOW_UP_3 = (
    "Hi {business_name} ji! 👋\n\n"
    "Lagta hai abhi aapke liye sahi time nahi hai — koi baat nahi!\n\n"
    "Jab bhi aapko website ki zaroorat ho, yahan reply kar dijiyega. "
    "Main {agent_name}, {company_name} — hamesha available hoon! 😊\n\n"
    "Aapka din accha ho! 🙏"
)

# ══════════════════════════════════════════════════════════════════
#  PACKAGE — Formatted package recommendation
# ══════════════════════════════════════════════════════════════════

PACKAGE_RECOMMENDATION = (
    "🎯 *{business_name} ji, aapke liye perfect plan:*\n\n"
    "📦 *{package_name} Package*\n"
    "💰 Price: *{price_display}* (one-time)\n\n"
    "✅ *Kya milega:*\n"
    "{features_list}\n\n"
    "🖥️ *Humara kaam dekhiye:* {portfolio_url}\n\n"
    "💳 *Payment:* UPI se simple payment\n"
    "   UPI ID: `{upi_id}`\n\n"
    "Kya aapko ye plan pasand aaya? Agar koi sawal ho to puchiye! 😊"
)

# ══════════════════════════════════════════════════════════════════
#  HANDOFF — Client is interested, alert admin
# ══════════════════════════════════════════════════════════════════

INTERESTED_HANDOFF = (
    "Bahut badhiya {business_name} ji! 🎉\n\n"
    "Main abhi apni team ko inform kar rahi hoon — "
    "wo aapse jaldi connect karenge aur sab finalize karenge.\n\n"
    "Aapka phone: {phone}\n"
    "Thank you for choosing {company_name}! 🙏"
)

# ══════════════════════════════════════════════════════════════════
#  NOT INTERESTED — Graceful goodbye
# ══════════════════════════════════════════════════════════════════

NOT_INTERESTED_RESPONSE = (
    "Koi baat nahi {business_name} ji! 🙏\n\n"
    "Jab bhi aapko website ki zaroorat ho, yahan message kar dijiyega.\n\n"
    "Agar aapko humara conversation accha laga ho to ek chhoti si request — "
    "kya aap hume Google par ek review de sakte hain? ⭐\n\n"
    "Dhanyawad aur aapka din shubh ho! 😊"
)


# ══════════════════════════════════════════════════════════════════
#  TELEGRAM ADMIN ALERTS
# ══════════════════════════════════════════════════════════════════

ADMIN_NEW_INTERESTED_LEAD = (
    "🎉 <b>New Interested Lead!</b>\n\n"
    "📛 Business: {business_name}\n"
    "📱 Phone: {phone}\n"
    "🏷️ Type: {business_type}\n"
    "📍 City: {city}\n\n"
    "📋 <b>Requirements:</b>\n"
    "{requirements_summary}\n\n"
    "📦 <b>Recommended Package:</b> {package_name} ({price_display})\n\n"
    "👉 Please contact them to finalize payment via UPI."
)

ADMIN_DAILY_SUMMARY = (
    "📊 <b>Daily Summary</b>\n\n"
    "🔍 Leads scraped today: {leads_scraped}\n"
    "📤 Messages sent: {messages_sent}\n"
    "📥 Replies received: {replies_received}\n"
    "🎯 Interested leads: {interested_count}\n"
    "❌ Not interested: {not_interested_count}"
)


# ══════════════════════════════════════════════════════════════════
#  FORMAT HELPERS
# ══════════════════════════════════════════════════════════════════

def format_template(template: str, **kwargs) -> str:
    """
    Safely format a template, filling in defaults for missing keys.

    Adds ``agent_name``, ``company_name``, ``portfolio_url``, and ``upi_id``
    automatically if not provided.
    """
    defaults = {
        "agent_name": AGENT_NAME,
        "company_name": COMPANY_NAME,
        "portfolio_url": PORTFOLIO_URL,
        "upi_id": UPI_ID,
    }
    merged = {**defaults, **kwargs}

    try:
        return template.format(**merged)
    except KeyError:
        # If a key is missing, return the template with unfilled placeholders
        safe = _SafeDict(merged)
        return template.format_map(safe)


class _SafeDict(dict):
    """Dict subclass that returns the key placeholder for missing keys."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def format_features_list(features: list[str]) -> str:
    """Convert a list of feature strings into a bullet-pointed list."""
    return "\n".join(f"  • {f}" for f in features)
