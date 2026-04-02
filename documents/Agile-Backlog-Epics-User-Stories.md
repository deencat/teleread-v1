# Agile Backlog: Epics and User Stories

## How to read this document
- Story IDs are internal to this plan and map back to SRS requirement IDs (e.g., `REQ-P1-TG-004`).
- Each story should be implemented so that it can be tested in isolation (via mocks) where feasible.

## Epic A: Browser Controller (Phase 1 foundation)
### Story A1: Playwright-based browser with primitives
- Mapping: `REQ-P1-BC-001`, `REQ-P1-BC-002`
- As a system, I want a browser controller that can launch an isolated Chromium profile and provide required primitives (goto/click/type/scroll/screenshot/get_text/get_html/evaluate_js/close), so that Telegram Web automation is deterministic and testable.
- Acceptance criteria:
  - Browser launches with dedicated isolated profile directory.
  - All primitive methods exist behind a Python class/module interface (no HTTP API in Phase 1).

### Story A2: Retries with exponential backoff
- Mapping: `REQ-P1-BC-003`
- Acceptance criteria:
  - Navigation timeouts and selector-not-found errors automatically retry up to 3 attempts with exponential backoff.

### Story A3: Domain allowlist enforcement
- Mapping: `REQ-P1-BC-004`, `REQ-SEC-004`
- Acceptance criteria:
  - Only permitted domains are navigable (default includes `web.telegram.org`).
  - Blocked navigation attempts are logged.

### Story A4: Security posture for Phase 1
- Mapping: `REQ-SEC-001`, `REQ-SEC-003`
- Acceptance criteria:
  - Browser profile directory access is restricted to the OS user (Windows ACL equivalent).
  - No network port exposure; control is in-process Python calls.

## Epic B: Telegram Automation Module (Phase 1 MVP)
### Story B1: Configurable Telegram web extraction parameters
- Mapping: `REQ-P1-TG-001`
- Acceptance criteria:
  - System reads configured `telegram_web_url`, `target_channel_name`, `session_profile_path`, `history_days`, and `poll_interval`.

### Story B2: Manual login with session persistence
- Mapping: `REQ-P1-TG-002`
- Acceptance criteria:
  - On first run (or no stored session), operator completes manual login.
  - Session is persisted so re-runs avoid re-authentication.

### Story B3: Locate and open target channel
- Mapping: `REQ-P1-TG-003`
- Acceptance criteria:
  - Target channel is found by exact display name or username.
  - Scrolling is used when the channel is not initially visible.

### Story B4: One-time full history extraction
- Mapping: `REQ-P1-TG-004`
- Acceptance criteria:
  - History extraction scrolls upward in increments until cutoff date is reached or top is reached.
  - Newly visible messages are extracted and inserted without violating de-dup rules (see storage epic).

### Story B5: Real-time monitoring loop with recovery
- Mapping: `REQ-P1-TG-005`, `REQ-NF-001`
- Acceptance criteria:
  - Polls for new messages within `poll_interval_seconds`.
  - Detects session loss / browser crash and performs auto recovery (restart within 60s).

### Story B6: Message extraction fields (DOM-based)
- Mapping: `REQ-P1-TG-006`
- Acceptance criteria:
  - Extracts `message_id`, `sender_name`, `message_text`, `message_html`, `has_media`, `media_url`, `timestamp_utc`, `channel_name`, `extracted_at`.

### Story B7: Screenshot fallback for extraction failures
- Mapping: `REQ-P1-TG-007`
- Acceptance criteria:
  - When DOM text extraction fails, a cropped screenshot is taken and referenced from `messages_raw.screenshot_path`.

### Story B8: No re-posting / forwarding
- Mapping: `REQ-P1-TG-008`, `REQ-SEC-006`
- Acceptance criteria:
  - System never forwards/re-posts any extracted content to external Telegram accounts.

## Epic C: Storage (Phase 1)
### Story C1: SQLite storage and schema
- Mapping: `REQ-P1-ST-001`, `REQ-P1-ST-002`
- Acceptance criteria:
  - SQLite database uses configured path.
  - Table `messages_raw` exists with schema matching SRS.

### Story C2: De-duplication of raw messages
- Mapping: `REQ-P1-ST-003`
- Acceptance criteria:
  - Enforced uniqueness on `(channel_name, message_id)`.
  - Re-running history extraction does not create duplicates.

### Story C3: Structured JSON Lines logging for extraction events
- Mapping: `REQ-P1-ST-004`, `REQ-NF-005`
- Acceptance criteria:
  - Extraction events (success/failure, row counts, timestamps) are logged to a JSONL file.
  - Log level is configurable.

## Epic D: LLM Parsing & Validation (Phase 2)
### Story D1: Parsing agent processes unparsed rows
- Mapping: `REQ-P2-LP-001`, `REQ-P2-LP-006`
- Acceptance criteria:
  - Parsing agent reads `messages_raw` where `parsed = FALSE`.
  - Agent triggers automatically on new `messages_raw` rows (event-driven or bounded polling).

### Story D2: LLM extraction to `trade_signal` schema
- Mapping: `REQ-P2-LP-002`
- Acceptance criteria:
  - LLM prompt produces JSON that conforms to trade signal requirements (instrument, direction, entry zone, SL/TP, timeframe, confidence, notes).

### Story D3: Instrument whitelist + sanity checks
- Mapping: `REQ-P2-LP-003`
- Acceptance criteria:
  - Instrument whitelist enforced.
  - Direction constrained to allowed values.
  - SL/TP sanity checks performed (e.g., SL below entry for long).

### Story D4: Store all parse outcomes in `signals_parsed`
- Mapping: `REQ-P2-LP-004`
- Acceptance criteria:
  - Insert into `signals_parsed` for all outcomes (valid/invalid/unclear) with `status` and `invalid_reason` where applicable.
  - Raw LLM response is persisted for audit.

### Story D5: Notify on new valid signal
- Mapping: `REQ-P2-LP-005`
- Acceptance criteria:
  - Notification sent only for new valid signals.
  - Notification includes instrument, direction, entry zone, SL/TP, and confidence score.

## Epic E: Trading Agent & Risk Management (Phase 3)
### Story E1: Execute broker orders for valid signals
- Mapping: `REQ-P3-TR-001`
- Acceptance criteria:
  - Trading agent selects `signals_parsed` rows with `status = "valid"` and `traded = FALSE` (or equivalent).
  - Correct broker API integration layer exists.

### Story E2: Risk checks before placing orders
- Mapping: `REQ-P3-TR-002`
- Acceptance criteria:
  - Max risk per trade enforced.
  - Max open positions enforced.
  - Session hours constraint enforced.
  - Daily loss limit halts trading when threshold is breached.

### Story E3: Support market and limit/stop-entry order types
- Mapping: `REQ-P3-TR-003`
- Acceptance criteria:
  - Market order with attached SL/TP supported.
  - Limit or stop-entry order placement supported using entry zone boundaries.

### Story E4: Order/fill audit logging to `trade_log`
- Mapping: `REQ-P3-TR-004`, `REQ-NF-005`
- Acceptance criteria:
  - Every order attempt, modification, and fill result is recorded in `trade_log`.

### Story E5: DRY_RUN default + explicit live flag
- Mapping: `REQ-P3-TR-005`, `REQ-SEC-007`
- Acceptance criteria:
  - DRY_RUN is default behavior.
  - Live trading requires explicit configuration flag (`live_trading: true`).
  - Broker keys are not accessible from extraction/parsing process.

### Story E6: Slippage reconciliation per trade
- Mapping: `REQ-P3-TR-006`
- Acceptance criteria:
  - Fill prices reconciled against requested entry zones.
  - Slippage is computed and stored for each trade.

## Epic F: Cross-cutting Non-Functional + Security
### Story F1: Maintainable selectors configuration
- Mapping: `REQ-NF-003`
- Acceptance criteria:
  - Telegram DOM selectors moved to `selectors.yaml`; changes do not require code edits.

### Story F2: Portability
- Mapping: `REQ-NF-004`, `REQ-SEC-001`
- Acceptance criteria:
  - Runs on Windows and Ubuntu without code changes (differences handled via config/env).

### Story F3: Testability and coverage target
- Mapping: `REQ-NF-006`, `REQ-NF-005`
- Acceptance criteria:
  - Parsing logic has unit tests with coverage >= 70%.
  - Browser/LLM are mockable for testing.

### Story F4: Observability and performance
- Mapping: `REQ-NF-001`, `REQ-NF-002`, `REQ-NF-005`
- Acceptance criteria:
  - Insert-to-DB latency within `poll_interval_seconds + 15` under normal conditions.
  - Auto-restart within 60s on crashes.
  - Structured JSON logs for events.

### Story F5: Secrets management
- Mapping: `REQ-SEC-002`, `REQ-SEC-003`
- Acceptance criteria:
  - API keys are read from env vars or `.env`.
  - No secrets in source control.

