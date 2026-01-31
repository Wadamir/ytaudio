FROM node:20-bookworm-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY bot/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# App
COPY bot /app/bot
COPY cookies.txt /cookies.txt

ENV PYTHONPATH=/app

CMD ["python3", "-m", "bot.main"]
