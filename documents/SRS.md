# SRS: Telegram Signal Extractor & Automated CFD Trading System

**Version:** 1.0 DRAFT | **Date:** 2026-03-27 | **Classification:** PRIVATE – Internal Use Only

***

## Table of Contents
1. Introduction
2. Overall System Description
3. System Architecture
4. Phased Delivery Plan
5. Phase 1 (MVP) – Functional Requirements
6. Phase 2 – Functional Requirements
7. Phase 3 – Functional Requirements
8. Non-Functional Requirements
9. Security Requirements
10. Data Schema
11. Configuration Schema
12. Assumptions & Constraints
13. Glossary

***

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for an agentic AI system that:
- Monitors a Telegram channel/group for trade idea posts published each trading morning by a designated signal provider.
- Extracts and structures the trade ideas automatically.
- (Later phases) Analyzes them using an LLM and executes trades on a CFD platform via API.

### 1.2 Scope
The system is a self-hosted, locally running software suite. It does **NOT** install any third-party automation gateway (e.g., OpenClaw SaaS). Instead, it re-implements the equivalent browser automation primitives using open-source libraries (Playwright/CDP) to minimize security exposure.

### 1.3 Background
The signal provider's Telegram channel has copy/forward protection and screenshot restrictions enabled on iOS mobile clients. Screenshots are possible from a desktop PC. Telegram Web (`web.telegram.org`) accessed via a controlled browser on desktop is the primary ingestion channel, as DOM text extraction is more reliable than OCR on screenshots.

### 1.4 Intended Audience
- Developer/Implementer (yourself)
- Future reviewers / auditors of trading logic

### 1.5 Document Conventions
- `REQ-XXX-NNN` — Requirement ID format (Phase-Area-Number)
- `MVP` — Phase 1 Minimum Viable Product
- `TBD` — To Be Decided during design/implementation

***

## 2. Overall System Description

### 2.1 Product Perspective
The system is a standalone pipeline of loosely coupled modules communicating via a local SQLite/PostgreSQL database and internal localhost HTTP only. No external SaaS services are required in Phase 1 or Phase 2.

### 2.2 User Story (Original Requirement)
> "I have been subscribed to a group where one person posts trade ideas and instructions every trading morning on Telegram. Copy/screenshot protection is active on iOS but desktop screenshots are possible. I want to:
> - Automatically retrieve all chat text and monitor for new posts. **[MVP]**
> - Send text to an LLM to analyze and extract structured trade signals. **[P2]**
> - Send resulting signals to a CFD platform via API for trading." **[P3]**

### 2.3 Product Functions Summary

**Phase 1 (MVP):**
- F1. Browser-based Telegram Web automation (login, navigate, scroll)
- F2. Full chat history text extraction and storage
- F3. Real-time monitoring for new messages with auto-extraction
- F4. Raw message store with timestamps

**Phase 2:**
- F5. LLM-based parsing of trade ideas into structured JSON signals
- F6. Signal validation and quality flagging
- F7. Notification when new signal is parsed

**Phase 3:**
- F8. Automated CFD order placement via broker API
- F9. Risk management layer (per-trade and daily loss limits)
- F10. Trade result reconciliation and PnL logging

### 2.4 Operating Environment
| Component | Detail |
|---|---|
| OS | Windows 10/11 or Ubuntu 22.04+ |
| Runtime | Python 3.11+ |
| Browser | Chromium (bundled by Playwright) or system Chrome/Brave |
| Database | SQLite (MVP) → PostgreSQL (Phase 2+) |
| LLM | OpenAI API, Anthropic API, or local Ollama (Phase 2) |
| CFD Platform | IG API, Interactive Brokers API, or equivalent (Phase 3) |

***

## 3. System Architecture

```
+----------------------+     +------------------------------------------+
| Browser Controller   |---->|     Telegram Automation Module           |
| (Playwright / CDP)   |     |  Login, Navigate, Scroll, Extract        |
+----------------------+     +-------------------+----------------------+
                                                 |
                             +-------------------v----------------------+
                             |         Raw Message Store                |
                             |      (messages_raw DB table)             |
                             +-------------------+----------------------+
                                                 |  [Phase 2]
                             +-------------------v----------------------+
                             |    LLM Parsing & Validation              |
                             |   (signals_parsed DB table)              |
                             +-------------------+----------------------+
                                                 |  [Phase 3]
                             +-------------------v----------------------+
                             |   Trading Agent + Risk Manager           |
                             |       CFD Broker API                     |
                             +------------------------------------------+
```
All components communicate via shared local DB or localhost only.  
No component exposes a public network interface.

***

## 4. Phased Delivery Plan

| Phase | Deliverable | Target |
|---|---|---|
| 1 | MVP: Extract + Monitor Telegram channel | First working build |
| 2 | LLM parsing, structured signals, alerts | ~2 weeks after MVP |
| 3 | CFD API integration + risk management | After Phase 2 validated |

***

## 5. Phase 1 (MVP) – Functional Requirements

### 5.1 Browser Controller Module

**REQ-P1-BC-001**
The system SHALL launch a Chromium instance using Playwright with a dedicated, isolated browser profile directory (not the user's default profile).

**REQ-P1-BC-002**
The browser controller SHALL support the following primitive operations:
- `launch(profile_path, headless: bool)`
- `goto(url: str)`
- `wait_for(selector: str | load_state: str, timeout_ms: int)`
- `click(selector: str)`
- `type_text(selector: str, text: str)`
- `scroll(container_selector: str, direction: "up"|"down", pixels: int)`
- `screenshot(file_path: str, full_page: bool)`
- `get_text(selector: str) -> str`
- `get_html(selector: str) -> str`
- `evaluate_js(script: str) -> any`
- `close()`

**REQ-P1-BC-003**
The browser controller SHALL implement automatic retry logic (max 3 retries with exponential backoff) for navigation timeouts and selector not-found errors.

**REQ-P1-BC-004**
The browser controller SHALL be restricted by an allowlist of permitted domains (default: `web.telegram.org`). Navigation to any other domain SHALL be blocked and logged.

**REQ-P1-BC-005**
The browser controller SHALL expose its interface as a Python class/module only (NOT as an external HTTP API in Phase 1) to minimize attack surface.

***

### 5.2 Telegram Automation Module

**REQ-P1-TG-001**
The system SHALL support configuration of:
- `telegram_web_url` — default `"https://web.telegram.org/"`
- `target_channel_name` — display name or username of signal channel
- `session_profile_path` — path to isolated browser profile
- `initial_history_days` — how many days back to extract on first run
- `poll_interval_seconds` — how often to check for new messages (default: 30)

**REQ-P1-TG-002**
On first run (or if no stored session), the system SHALL:
- Open Telegram Web and wait for the user to complete manual login (QR code or phone number). This is a one-time setup step.
- After login, persist the browser session in the profile directory so subsequent runs do NOT require re-authentication.

**REQ-P1-TG-003**
The system SHALL locate the target channel in the chat list by:
- Matching exact display name or username from configuration.
- If not visible, scrolling the chat list to find it.
- Clicking to open the channel.

**REQ-P1-TG-004 — HISTORY EXTRACTION**
On first run, the system SHALL extract full chat history up to the configured `initial_history_days` by:
- Scrolling upward in the chat window in increments.
- After each scroll, extracting all newly visible message elements.
- Stopping when messages older than the cutoff date are reached OR the top of the chat is reached.
- Storing each unique message in `messages_raw` (de-duplication by message element ID or timestamp+text hash).

**REQ-P1-TG-005 — REAL-TIME MONITORING**
After history extraction, the system SHALL enter a continuous monitoring loop that:
- Polls for new messages every `poll_interval_seconds`.
- Detects new messages by comparing against the last known message ID/timestamp in `messages_raw`.
- Extracts and stores any new messages immediately upon detection.
- Handles reconnection automatically if the Telegram Web session is lost or the browser crashes.

**REQ-P1-TG-006 — MESSAGE EXTRACTION**
For each visible message element, the system SHALL extract:
- `message_id` — Telegram internal message identifier from DOM
- `sender_name` — Display name of sender
- `message_text` — Full plain text content (innerText)
- `message_html` — Raw HTML of the message bubble
- `has_media` — Boolean flag (photo, document, sticker present)
- `media_url` — URL if downloadable inline media is present
- `timestamp_utc` — Message timestamp in UTC (parsed from DOM attribute)
- `channel_name` — As configured
- `extracted_at` — System timestamp at time of extraction

**REQ-P1-TG-007 — SCREENSHOT FALLBACK**
If DOM text extraction fails for a message (e.g., rendered as canvas or obfuscated), the system SHALL:
- Take a cropped screenshot of that message element.
- Save the screenshot file to the configured screenshots directory.
- Record the file path in `messages_raw.screenshot_path`.

**REQ-P1-TG-008**
The system SHALL NOT attempt to forward, re-post, or copy messages to any external Telegram account, channel, or bot.

***

### 5.3 Storage Module (MVP)

**REQ-P1-ST-001**
The system SHALL maintain a local SQLite database (Phase 1) at a configured file path.

**REQ-P1-ST-002**
The database SHALL contain the table `messages_raw` (schema in Section 10.1).

**REQ-P1-ST-003**
The system SHALL ensure de-duplication: a message with the same `(channel_name, message_id)` SHALL NOT be inserted twice.

**REQ-P1-ST-004**
The system SHALL log every extraction event (success/failure, row count, timestamp) to a structured log file in JSON Lines format.

***

### 5.4 MVP Acceptance Criteria

| ID | Criteria |
|---|---|
| AC-MVP-01 | On first run, all messages in the target channel for the last N days are present in `messages_raw` |
| AC-MVP-02 | A new test message posted to the channel appears in `messages_raw` within `(poll_interval_seconds + 10)` seconds |
| AC-MVP-03 | Re-running the system does not create duplicate rows |
| AC-MVP-04 | System recovers automatically after a simulated browser crash |
| AC-MVP-05 | All extracted text is accurate — manually verified against actual channel for at least 5 messages |

***

## 6. Phase 2 – LLM Parsing & Signal Structuring

**REQ-P2-LP-001**
The system SHALL add a Parsing Agent that reads unprocessed rows from `messages_raw` (where `parsed = FALSE`) and processes them in order.

**REQ-P2-LP-002**
The Parsing Agent SHALL send each `message_text` to a configured LLM (OpenAI GPT-4o, Anthropic Claude, or local Ollama) with a structured extraction prompt and expect a JSON response conforming to the trade_signal schema (Section 10.2).

**REQ-P2-LP-003**
The system SHALL validate the parsed signal against these rules:
- `instrument` is in a configured whitelist (e.g., HK50, HSI)
- `direction` is `"long"` or `"short"`
- `stop_loss` is below entry for long; above entry for short
- All numeric fields are positive
- `entry_zone_low <= entry_zone_high`
- At least one `take_profit` level exists

Signals failing validation SHALL be stored with `status = "invalid"` and the `invalid_reason` field populated.

**REQ-P2-LP-004**
The system SHALL insert the parsed result into `signals_parsed` (Section 10.2) regardless of validation outcome, with appropriate `status` field value.

**REQ-P2-LP-005**
The system SHALL send a notification (Telegram bot message to a personal chat, or email) whenever a new valid signal is parsed, containing: instrument, direction, entry zone, SL, TP levels, and confidence score.

**REQ-P2-LP-006**
The Parsing Agent SHALL run automatically triggered by any new `messages_raw` row (event-driven or polling every 60 seconds).

***

## 7. Phase 3 – CFD Trading Integration

**REQ-P3-TR-001**
The system SHALL add a Trading Agent that reads new `signals_parsed` rows with `status = "valid"` and executes corresponding orders on the CFD broker API.

**REQ-P3-TR-002**
Before placing any order, the Trading Agent SHALL apply risk checks:
- Max risk per trade (configured %, e.g., 1% of account equity)
- Max number of open positions at any time
- No trading outside configured session hours (e.g., HK market hours 09:15–16:00 HKT)
- Daily loss limit: halt trading if daily PnL < configured threshold

**REQ-P3-TR-003**
The Trading Agent SHALL support at minimum:
- Market order with attached SL and TP
- Limit/stop-entry order at `entry_zone_high` or `entry_zone_low`

**REQ-P3-TR-004**
All order placements, modifications, and fills SHALL be logged in the `trade_log` table (Section 10.3).

**REQ-P3-TR-005**
The Trading Agent SHALL operate in `DRY_RUN` mode by default. Live trading SHALL require explicit configuration flag: `live_trading: true`.

**REQ-P3-TR-006**
The system SHALL reconcile broker fill prices against signal entry zones and log slippage for each trade.

***

## 8. Non-Functional Requirements

| REQ-ID | Category | Requirement |
|---|---|---|
| REQ-NF-001 | Reliability | Monitoring loop >= 99% uptime during active hours; auto-restart within 60s on browser crash |
| REQ-NF-002 | Performance | Message to DB insert <= `poll_interval_seconds + 15` seconds under normal conditions |
| REQ-NF-003 | Maintainability | All Telegram DOM selectors externalized in `selectors.yaml`; no code changes needed for UI updates |
| REQ-NF-004 | Portability | Runs on Windows 10+ and Ubuntu 22.04+ without code changes |
| REQ-NF-005 | Observability | Structured JSON logs for every event; log level configurable (DEBUG/INFO/WARNING/ERROR) |
| REQ-NF-006 | Testability | Each module independently testable with mock browser/LLM; unit test coverage >= 70% for parsing logic |

***

## 9. Security Requirements

**REQ-SEC-001**
The Chromium browser profile directory (containing Telegram session cookie) SHALL be accessible only to the running OS user (`chmod 700` on Linux, Windows ACL equivalent).

**REQ-SEC-002**
Broker API keys and LLM API keys SHALL be stored in environment variables or a `.env` file and NEVER committed to source control.

**REQ-SEC-003**
The browser controller SHALL NOT expose any network port. All control is in-process Python function calls in Phase 1 and Phase 2.

**REQ-SEC-004**
The system SHALL maintain a domain allowlist in the browser controller. Navigation to any domain not in the allowlist SHALL be blocked and logged.
Default allowlist: `[ "web.telegram.org" ]`

**REQ-SEC-005**
Screenshots saved to disk SHALL be stored in a local directory with no network share or cloud sync access.

**REQ-SEC-006**
The system SHALL NOT re-broadcast, forward, or store extracted messages to any external service other than:
- A configured LLM API for parsing (Phase 2) — text only, no user identity
- A configured personal notification channel (personal use only)

**REQ-SEC-007**
In Phase 3, the Trading Agent and the Extraction/Parsing Agent SHALL run as separate processes with separate config files. Broker API keys SHALL NOT be accessible from the extraction/parsing process.

***

## 10. Data Schema

### 10.1 Table: `messages_raw`

```sql
CREATE TABLE messages_raw (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    channel_name      TEXT     NOT NULL,
    message_id        TEXT     NOT NULL,
    sender_name       TEXT,
    message_text      TEXT,
    message_html      TEXT,
    has_media         BOOLEAN  DEFAULT FALSE,
    media_url         TEXT,
    screenshot_path   TEXT,
    timestamp_utc     DATETIME NOT NULL,
    extracted_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    parsed            BOOLEAN  DEFAULT FALSE,
    UNIQUE (channel_name, message_id)
);
```

### 10.2 Table: `signals_parsed` *(Phase 2)*

```sql
CREATE TABLE signals_parsed (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    message_raw_id    INTEGER  REFERENCES messages_raw(id),
    instrument        TEXT,
    direction         TEXT     CHECK(direction IN ('long','short','neutral','unclear')),
    entry_zone_low    REAL,
    entry_zone_high   REAL,
    stop_loss         REAL,
    take_profit_1     REAL,
    take_profit_2     REAL,
    take_profit_3     REAL,
    timeframe         TEXT,
    confidence_score  REAL,    -- 0.0 to 1.0, LLM-estimated
    status            TEXT     CHECK(status IN ('valid','invalid','unclear')),
    invalid_reason    TEXT,
    llm_raw_response  TEXT,    -- full LLM JSON for audit
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    traded            BOOLEAN  DEFAULT FALSE
);
```

**LLM Target JSON Output Format:**
```json
{
  "instrument":  "HK50",
  "direction":   "long",
  "entry_zone":  { "low": 17780, "high": 17820 },
  "stop_loss":   17650,
  "take_profit": [18000, 18200],
  "timeframe":   "intraday",
  "confidence":  0.85,
  "notes":       "Wait for open; scale in at zone low"
}
```

### 10.3 Table: `trade_log` *(Phase 3)*

```sql
CREATE TABLE trade_log (
    id                INTEGER  PRIMARY KEY AUTOINCREMENT,
    signal_id         INTEGER  REFERENCES signals_parsed(id),
    broker_order_id   TEXT,
    instrument        TEXT,
    direction         TEXT,
    order_type        TEXT,    -- 'market','limit','stop'
    requested_entry   REAL,
    fill_price        REAL,
    slippage          REAL,    -- fill_price - requested_entry
    stop_loss         REAL,
    take_profit       REAL,
    position_size     REAL,
    status            TEXT,    -- 'open','closed','cancelled','error'
    open_time         DATETIME,
    close_time        DATETIME,
    close_price       REAL,
    pnl               REAL,
    dry_run           BOOLEAN  DEFAULT TRUE,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

***

## 11. Configuration Schema (`config.yaml`)

```yaml
telegram:
  web_url: "https://web.telegram.org/"
  target_channel_name: "<YOUR_CHANNEL_NAME>"
  session_profile_path: "./browser_profiles/telegram_session"
  initial_history_days: 30
  poll_interval_seconds: 30
  allowed_senders: []           # empty = accept all senders in channel

browser:
  headless: false               # false for initial login setup
  allowed_domains:
    - "web.telegram.org"
  timeout_ms: 15000
  max_retries: 3

selectors_file: "./config/selectors.yaml"

storage:
  db_type: "sqlite"             # or "postgresql"
  db_path: "./data/signals.db"
  screenshots_dir: "./data/screenshots"
  log_file: "./logs/system.jsonl"

parsing:                        # Phase 2
  enabled: false
  llm_provider: "openai"        # openai | anthropic | ollama
  llm_model: "gpt-4o"
  instrument_whitelist: ["HK50","HSI","700.HK","9988.HK"]
  prompt_template_file: "./config/parse_prompt.txt"

notifications:                  # Phase 2
  enabled: false
  method: "telegram_bot"        # telegram_bot | email
  telegram_bot_token_env: "NOTIFY_BOT_TOKEN"
  telegram_chat_id_env: "NOTIFY_CHAT_ID"

trading:                        # Phase 3
  enabled: false
  live_trading: false           # MUST be explicitly true for live orders
  broker: "ig"                  # ig | ibkr
  max_risk_per_trade_pct: 1.0
  max_open_positions: 3
  daily_loss_limit: -500
  session_hours_hkt:
    start: "09:15"
    end:   "16:00"
```

***

## 12. Assumptions & Constraints

**Assumptions:**
- A1. The signal provider posts messages as plain text; no JS-obfuscated content is expected.
- A2. Telegram Web (`web.telegram.org`) does NOT enforce copy protection at the DOM level — only iOS/Android clients enforce it via the UI layer.
- A3. The operator uses extracted data solely for their own private trading.
- A4. The CFD broker selected for Phase 3 provides a documented REST or WebSocket API.
- A5. Python 3.11+ and Playwright (`pip install playwright`) are available in the deployment environment.

**Constraints:**
- C1. This system must NOT be used to redistribute, resell, or share the signal provider's content with any third party.
- C2. All network calls to external APIs go outbound only; no inbound ports are opened.
- C3. Phase 3 live trading must be preceded by a minimum 2-week paper trading (dry run) validation period.

***

## 13. Glossary

| Term | Definition |
|---|---|
| CDP | Chrome DevTools Protocol — low-level browser control interface |
| CFD | Contract for Difference — leveraged derivative product |
| DOM | Document Object Model — browser's in-memory HTML structure |
| Dry Run | Trade simulation mode; no real orders placed |
| LLM | Large Language Model (e.g., GPT-4o, Claude) |
| MVP | Minimum Viable Product — Phase 1 deliverable |
| OCR | Optical Character Recognition — extracting text from images |
| Playwright | Microsoft open-source browser automation library (Python) |
| Signal | A structured trade idea: instrument, direction, SL, TP |
| SRS | Software Requirements Specification (this document) |

***

*End of Document — SRS v1.0 DRAFT*