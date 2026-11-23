FROM node:20-bookworm-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create and configure python virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install application dependencies along with SOCKS5 proxy support extension
COPY bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir "python-telegram-bot[socks]"

# Copy application source code and authentication files
COPY bot /app/bot
COPY cookies.txt /cookies.txt

ENV PYTHONPATH=/app

# Hardcode the global proxy routing flag for the core yt-dlp binary layer
ENV YTDLP_PROXY="socks5h://127.0.0.1:1080"

# Execute the main module of the application
CMD ["python", "-m", "bot.main"]
