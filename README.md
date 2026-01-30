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
  - fallback to external link
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
│ ├── admin/ # Admin-side utilities (stats, maintenance tools)
│ │ └── stats.py
│ │
│ ├── assets/ # Static assets (images, placeholders)
│ │ └── youtube_placeholder.jpg
│ │
│ ├── config/ # Application configuration
│ │ ├── app.py # App-level settings
│ │ ├── bot.py # Bot configuration
│ │ ├── downloaders.py # Downloader-related constants
│ │ ├── network.py # Network / IP configuration
│ │ ├── telegram.py # Telegram limits and settings
│ │ ├── text.py # Text-related config
│ │ └── utils.py
│ │
│ ├── db/ # Database layer
│ │ └── db.py # Queries, logging, counters
│ │
│ ├── downloaders/ # Platform-specific downloaders
│ │ ├── base.py # BaseDownloader + DownloadContext
│ │ ├── errors.py # Domain-specific downloader errors
│ │ ├── registry.py # Downloader resolver by URL
│ │ └── youtube.py # YouTube downloader (yt-dlp based)
│ │
│ ├── handlers/ # Telegram update handlers
│ │ ├── commands.py # /start, /help, etc.
│ │ ├── messages.py # Text / URL messages
│ │ └── callbacks.py # Inline keyboard callbacks
│ │
│ ├── i18n/ # Internationalization (i18n)
│ │ ├── en.py
│ │ ├── ru.py
│ │ ├── helpers.py # Translation helpers
│ │ ├── keyboards.py # Localized keyboards
│ │ ├── service.py # Language service
│ │ └── validate.py
│ │
│ ├── pipeline/ # Processing & delivery pipeline
│ │ ├── postprocess.py # Audio post-processing (split, convert, tag)
│ │ ├── delivery.py # Delivery strategies (telegram / split / link)
│ │ └── types.py # Pipeline enums and DTOs
│ │
│ ├── utils/ # Shared utility functions
│ │ ├── format.py # Duration / size formatting
│ │ ├── text.py # Text sanitizing
│ │ └── time.py
│ │
│ ├── workers/ # Background workers
│ │ ├── download_worker.py # Main job orchestrator
│ │ ├── queue.py # Download queue & workers pool
│ │ └── main.py # Worker entrypoint
│ │
│ └── main.py # Bot entrypoint
│
├── nginx/ # Nginx configuration (production)
│ └── nginx.conf
│
├── storage/ # Persistent storage (audio, db, logs)
│
├── docker-compose.yml # Production compose
├── docker-compose.dev.yml # Development compose
├── Dockerfile
├── requirements.txt
├── README.md
└── cookies.txt # YouTube cookies (optional and should NOT be committed to public repo)
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