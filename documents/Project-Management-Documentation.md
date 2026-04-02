# Project Management Documentation

## Project
Telegram Signal Extractor & Automated CFD Trading System

## Goals
Deliver a self-hosted pipeline that:
1. Extracts Telegram Web chat history and new messages from a configured channel (Phase 1 / MVP)
2. Parses extracted messages into structured trade signals via an LLM with validation and notifications (Phase 2)
3. Executes validated signals via a CFD broker API with risk controls, fill reconciliation, and full audit logging (Phase 3)

## Delivery Phases (from SRS)
1. **Phase 1 (MVP)**: Browser automation + Telegram extraction + local storage + monitoring loop
2. **Phase 2**: LLM parsing, validation, persistence of parse status, and new-signal notifications
3. **Phase 3**: Trading agent, risk management checks, dry-run default, and broker reconciliation logging

## Agile Process (recommended baseline)
- Cadence: 1-week sprints
- Planning: Sprint Planning (capacity + scope), then daily updates, then Sprint Review + Retrospective
- Work tracking labels:
  - `Done` - fully implemented and acceptance criteria satisfied
  - `ToDo` - actively targeted for the current or next sprint
  - `Backlog` - not planned for the current sprint (yet), prioritized for future sprints

## Completed Tasks
- None yet (project kickoff / planning stage).

## Pending Tasks (prioritized)
- Create and maintain the backlog and sprint plan mapped to SRS requirement IDs
- Define shared quality gates (Definition of Done) applied to all stories
- Establish initial local development/testing workflow (unit tests + mocks) aligned with Phase 1/2/3 boundaries
- Implement Phase 1 MVP in a vertical-slice manner (browser controller -> Telegram extraction -> DB -> monitoring -> de-dup)

## Backlog Tasks (prioritized by SRS phase)
1. **Phase 1 Browser Controller** (Playwright primitives, retry logic, domain allowlist, class-only interface)
2. **Phase 1 Telegram Automation** (manual login persistence, channel discovery, history extraction, monitoring loop, message extraction, screenshot fallback)
3. **Phase 1 Storage** (SQLite schema, de-duplication, structured JSONL event logging)
4. **Phase 2 LLM Parsing & Validation** (event-driven parsing, JSON schema output, validation rules, status handling)
5. **Phase 2 Notifications** (new valid signal alert via configured method)
6. **Phase 3 Trading Agent** (broker integration, order types, DRY_RUN default, reconciliation and logging)
7. **Cross-cutting Reliability/Observability/Security** (auto-restart, structured logs, selectors.yaml, env-based secrets, least exposure to network)

## Quality Gates (Definition of Done - summary)
- Implemented feature passes unit tests (mocked browser/LLM where applicable)
- Structured logging is present for the feature’s critical path
- Security constraints are respected (no secrets in repo; no exposed inbound ports; allowlist enforced where required)
- Feature is wired end-to-end through the DB state transitions (e.g., `messages_raw.parsed`, `signals_parsed.status`)

