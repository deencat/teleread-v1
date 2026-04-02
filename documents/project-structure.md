telegram-signal-extractor/
│
├── main.py                        # Entry point
├── config.yaml                    # Your configuration (edit this)
├── .env                           # API keys (never commit)
├── requirements.txt               # Python dependencies
│
├── config/
│   └── selectors.yaml             # Telegram Web DOM selectors
│
├── src/
│   ├── __init__.py
│   ├── browser_controller.py      # Playwright wrapper (Phase 1)
│   ├── telegram_extractor.py      # Telegram Web automation (Phase 1)
│   ├── storage.py                 # SQLite DB layer (Phase 1)
│   └── logger.py                  # Structured JSON logger
│
├── data/
│   ├── signals.db                 # SQLite database (auto-created)
│   └── screenshots/               # Fallback screenshots (auto-created)
│
├── logs/
│   └── system.jsonl               # JSON Lines log (auto-created)
│
└── tests/
    ├── test_browser_controller.py
    ├── test_telegram_extractor.py
    └── test_storage.py