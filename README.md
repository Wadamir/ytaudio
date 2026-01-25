# ytaudio
YT-AUDIO is a Telegram bot that allows users to download audio from YouTube videos directly within Telegram. It supports multiple languages and provides an easy-to-use interface for downloading and sharing audio files.

YT-AUDIO-BOT/
├── bot/                         # Main application source code
│   │
│   ├── admin/                   # Admin-related functionality
│   │   ├── __init__.py
│   │   └── stats.py              # Bot statistics and admin analytics
│   │
│   ├── assets/                  # Static assets
│   │   └── youtube_placeholder.jpg
│   │
│   ├── config/                  # Application configuration & bootstrap
│   │   ├── __init__.py
│   │   ├── app.py                # App initialization and wiring
│   │   ├── bot.py                # Telegram bot setup
│   │   ├── downloader.py         # Downloader configuration
│   │   ├── telegram.py           # Telegram client configuration
│   │   ├── text.py               # Global text constants
│   │   └── utils.py              # Config-level helpers
│   │
│   ├── db/                      # Database layer
│   │   └── db.py                 # Database connection and queries
│   │
│   ├── handlers/                # Telegram update handlers
│   │   ├── __init__.py
│   │   ├── callbacks.py          # Inline button callbacks
│   │   ├── commands.py           # Bot commands (/start, /help, etc.)
│   │   └── messages.py           # Text and media message handlers
│   │
│   ├── i18n/                    # Internationalization (locales)
│   │   ├── en.py                 # English translations
│   │   ├── ru.py                 # Russian translations
│   │   ├── helpers.py            # i18n helper functions
│   │   ├── keyboards.py          # Localized keyboards
│   │   ├── service.py            # Locale service logic
│   │   └── validate.py           # Translation validation
│   │
│   ├── parsers/                 # External media parsers
│   │   ├── __init__.py
│   │   ├── base.py               # Base parser abstraction
│   │   ├── registry.py           # Parser registry / factory
│   │   └── youtube.py            # YouTube parser implementation
│   │
│   ├── utils/                   # Shared utility functions
│   │   ├── format.py             # Formatting helpers
│   │   ├── text.py               # Text utilities
│   │   └── time.py               # Time and date helpers
│   │
│   ├── workers/                 # Background workers
│   │   ├── __init__.py
│   │   ├── downloader.py         # Media download worker
│   │   └── queue.py              # Task queue management
│   │
│   └── main.py                  # Application entry point
│
├── nginx/                       # Nginx configuration
│   └── nginx.conf
│
├── storage/                     # Persistent storage (downloads, temp files)
│
├── docker-compose.yml           # Production Docker Compose
├── docker-compose.dev.yml       # Development Docker Compose
├── Dockerfile                   # Docker image definition
│
├── .dockerignore
├── .env                         # Environment variables
├── .gitignore
├── cookies.txt                  # Cookies for external services (e.g. YouTube)
├── requirements.txt             # Python dependencies
└── README.md