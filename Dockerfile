FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# Copy source code
COPY . .

# Expose port (can be overridden by PORT env var)
EXPOSE 8000

# Use PORT env var if set (for cloud platforms), fallback to 8000
ENV PORT=8000

# Run server
CMD uvicorn server.app:app --host 0.0.0.0 --port $PORT
