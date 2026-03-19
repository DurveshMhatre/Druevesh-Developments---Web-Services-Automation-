"""
Entry point for the AI Web Automation server.

Usage:
    python main.py
"""

import uvicorn

from config.settings import SERVER_HOST, SERVER_PORT


def main():
    """Start the FastAPI server."""
    uvicorn.run(
        "server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
