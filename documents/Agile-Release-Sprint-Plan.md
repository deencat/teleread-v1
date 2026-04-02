# Agile Release Plan (Mapped to SRS)

## Assumed sprint structure
- Sprint length: 2 weeks
- Capacity: time-box scope; keep work as vertically integrated slices (feature end-to-end through DB state transitions)
- Cross-cutting focus every sprint:
  - Structured logging (critical-path events)
  - Secrets/security constraints
  - Unit tests with mocks for parsing and storage logic

## Milestones / Gates
### MVP Complete (end of Phase 1)
All MVP acceptance criteria must be satisfied:
1. `AC-MVP-01`: On first run, all messages in the target channel for the last N days are present in `messages_raw`
2. `AC-MVP-02`: A new test message appears in `messages_raw` within `(poll_interval_seconds + 10)` seconds
3. `AC-MVP-03`: Re-running does not create duplicate rows
4. `AC-MVP-04`: System recovers automatically after a simulated browser crash
5. `AC-MVP-05`: Extracted text is accurate for at least 5 manually verified messages

### Phase 2 Complete
- New messages are parsed into `signals_parsed` with validation status.
- Notifications fire when new valid signals are parsed.

### Phase 3 Complete (paper trading validated)
- Trading agent runs in `DRY_RUN` by default.
- Risk checks block unsafe orders.
- `trade_log` contains complete audit trails and slippage reconciliation is computed.

## Sprint Plan
| Sprint | Primary Objective | Key Deliverables | SRS REQ coverage (non-exhaustive) |
|---|---|---|---|
| 1 | Foundation + Browser Controller | Project local run; config/env separation; structured logger + DB init scaffold; Playwright browser controller primitives; isolated profile; retry/backoff; domain allowlist enforcement; class/module-only interface | `REQ-NF-003`, `REQ-NF-005`, `REQ-NF-006`, `REQ-SEC-002`, `REQ-P1-BC-001`, `REQ-P1-BC-002`, `REQ-P1-BC-003`, `REQ-P1-BC-004`, `REQ-P1-BC-005` |
| 2 | Telegram setup + Channel discovery + History wiring | Manual login + session persistence; locate/open target channel; config for Telegram extraction parameters; begin history extraction flow wired to insert into `messages_raw` (schema/de-dup finalized by next sprint if needed) | `REQ-P1-TG-001`, `REQ-P1-TG-002`, `REQ-P1-TG-003`, `REQ-P1-TG-004`, `REQ-P1-ST-001`, `REQ-P1-ST-002` |
| 3 | MVP Phase 1 complete: history + monitoring | Full history extraction with de-dup; screenshot fallback hook; extraction event JSONL logging; real-time monitoring loop with crash/session recovery; DOM extraction fields; MVP gate readiness for AC-MVP-01..04 | `REQ-P1-TG-004`, `REQ-P1-TG-005`, `REQ-P1-TG-006`, `REQ-P1-TG-007`, `REQ-P1-ST-003`, `REQ-P1-ST-004`, `REQ-NF-001` |
| 4 | MVP gate verification + Phase 2 parsing core | Validate AC-MVP-01..05 (especially text accuracy); ensure performance + reliability under normal conditions; implement Parsing Agent loop; LLM JSON extraction + instrument whitelist + SL/TP sanity checks; store all outcomes in `signals_parsed` with status + audit | `AC-MVP-01..05`, `REQ-NF-002`, `REQ-NF-001`, `REQ-P2-LP-001`, `REQ-P2-LP-002`, `REQ-P2-LP-003`, `REQ-P2-LP-004`, `REQ-NF-006` |
| 5 | Phase 2 notifications + start Phase 3 (dry-run) | Notification on new valid signals; auto-trigger parsing on new rows; set up Trading Agent in DRY_RUN default; broker adapter + order logging groundwork | `REQ-P2-LP-005`, `REQ-P2-LP-006`, `REQ-P3-TR-001`, `REQ-P3-TR-003`, `REQ-P3-TR-004`, `REQ-P3-TR-005` |
| 6 | Phase 3 risk checks + reconciliation + audit | Risk management gating (per trade %, max positions, session hours, daily loss limit); broker fill reconciliation; compute slippage and record in `trade_log`; complete paper-trading validation and separation of agent processes/config | `REQ-P3-TR-002`, `REQ-P3-TR-006`, `REQ-NF-001..005`, `REQ-SEC-007` |

## Sprint-by-sprint acceptance checklist (lightweight)
- Sprint ends with the system runnable end-to-end for the phase(s) targeted that sprint.
- Any new storage schema changes include corresponding migrations/tests.
- Any new parsing logic includes validation tests (whitelist + SL/TP sanity).
- Any new trading logic includes DRY_RUN enforcement tests.

