FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY bot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ⬇️ КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
COPY bot /app/bot

# YouTube cookies
COPY cookies.txt /cookies.txt

ENV PYTHONPATH=/app

# ⬇️ КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
CMD ["python", "-m", "bot.main"]
