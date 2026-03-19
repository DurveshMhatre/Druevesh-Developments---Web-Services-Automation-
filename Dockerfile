# ══════════════════════════════════════════════════════════════════
#  Stage 1: Build dependencies
# ══════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# ══════════════════════════════════════════════════════════════════
#  Stage 2: Production image
# ══════════════════════════════════════════════════════════════════
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin appuser

# Copy installed packages and Playwright browsers from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

# Install Playwright system deps in production image
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy source code
COPY . .

# Fix ownership for non-root user
RUN chown -R appuser:appuser /app /home/appuser

# Switch to non-root user
USER appuser

# Expose port (can be overridden by PORT env var)
EXPOSE 8000

# Use PORT env var if set (for cloud platforms), fallback to 8000
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run server
CMD uvicorn server.app:app --host 0.0.0.0 --port $PORT
