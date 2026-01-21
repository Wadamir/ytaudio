FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps (rarely change)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		ffmpeg \
		ca-certificates \
		curl \
	&& curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
	&& apt-get install -y nodejs \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

# Python deps (cached)
COPY bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App code (changes often)
COPY bot/ .

# YouTube cookies
COPY cookies.txt /cookies.txt

CMD ["python", "main.py"]