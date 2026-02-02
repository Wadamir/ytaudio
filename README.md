# 🎧 YT-Audio-Bot

A Telegram bot that downloads audio from YouTube and delivers it in the most suitable way  
(single file, split parts, or external link).

The project is built with a **clean, extensible architecture**, focusing on separation of concerns,
explicit error handling, and long-term maintainability.

---

## ✨ Features

- 🎵 Download audio from YouTube using `yt-dlp`
- ⚡ Automatic fast / slow download mode selection
- ✂️ Audio post-processing (split large files, convert formats, metadata)
- 📦 Smart delivery strategy:
    - single Telegram file
    - split into multiple parts
    - fallback to external link (removed)
- 🌍 Multilingual interface (i18n)
- 🧵 Background workers with queue
- 📊 Download statistics & error tracking
- 🐳 Docker support (development & production)

---

## 🧠 Design Principles

This project follows several core principles:

- **Separation of concerns**  
  Each layer has a single responsibility.

- **Explicit domain errors**  
  Downloaders raise meaningful exceptions instead of silently failing.

- **Worker-driven orchestration**  
  All business decisions happen in workers, not in handlers or downloaders.

- **Extensibility first**  
  New platforms (YouTube, TikTok, SoundCloud, etc.) can be added with minimal effort.

---

## 📁 Project Structure

```text
YT-AUDIO-BOT/
├── bot/
│   ├── admin/
│   │   ├── __init__.py
│   │   ├── actions.py
│   │   ├── keyboards.py
│   │   └── stats.py
│   │
│   ├── assets/
│   │   └── youtube_placeholder.jpg
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── bot.py
│   │   ├── downloaders.py
│   │   ├── network.py
│   │   ├── telegram.py
│   │   ├── text.py
│   │   └── utils.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── db.py
│   │
│   ├── downloaders/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── errors.py
│   │   ├── registry.py
│   │   ├── stages.py
│   │   ├── utils.py
│   │   └── youtube.py
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── callbacks.py
│   │   ├── commands.py
│   │   ├── menu.py
│   │   ├── messages.py
│   │   └── payments.py
│   │
│   ├── i18n/
│   │   ├── __init__.py
│   │   ├── en.py
│   │   ├── ru.py
│   │   ├── helpers.py
│   │   ├── keyboards.py
│   │   ├── service.py
│   │   └── validate.py
│   │
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── main.py
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── delivery.py
│   │   ├── errors.py
│   │   ├── postprocess.py
│   │   └── types.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── format.py
│   │   ├── text.py
│   │   └── time.py
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── download_worker.py
│   │   └── queue.py
│   │
│   ├── __init__.py
│   └── main.py
│
├── nginx/
│   └── nginx.conf
│
├── storage/
│   └── db/
│       └── bot.sqlite3
│
├── .dockerignore
├── .env
├── .gitignore
├── cookies.txt
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🧩 Architecture Overview

### Downloaders (`bot/downloaders`)

Responsible for:

- fetching video metadata
- downloading raw audio files

They never:

- send Telegram messages
- decide delivery strategy

### Workers (`bot/workers`)

Orchestrate jobs, handle errors, post-process files and deliver results.

### Pipeline (`bot/pipeline`)

Contains post-processing and delivery logic.

### Handlers (`bot/handlers`)

Handle Telegram updates and enqueue jobs only.

---

## 🔄 Processing Flow

```text
Telegram Update → Handler → Queue → Worker → Downloader → Post-process → Delivery
```

---

## 🐳 Running with Docker

### Development

```bash
docker compose -f docker-compose.dev.yml up --build
```

### Production

```bash
docker compose up -d --build
```

---

## 🤝 Contributing

Contributions are welcome.
Please keep changes focused and consistent with the architecture.

---

## 📄 License

MIT License
