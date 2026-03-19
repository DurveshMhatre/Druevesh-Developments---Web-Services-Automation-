"""
Script to trigger the initial OAuth 2.0 Desktop authentication for Google Sheets.
Run this script once to open your browser, log in, and generate `token.json`.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.sheets_client import get_all_leads

def main():
    print("🔄 Initializing Google Sheets OAuth Flow...")
    print("If you haven't authenticated yet, a browser window will open.")
    print("Please log in with the Google Account that has access to the Sheet.")
    
    try:
        # Calling this will trigger gspread.oauth() and open the browser
        leads = get_all_leads()
        print(f"✅ Authentication Successful! `token.json` has been generated.")
        print(f"📊 Successfully read {len(leads)} rows from the Leads sheet.")
    except Exception as e:
        print(f"❌ Error during authentication: {e}")

if __name__ == "__main__":
    main()
