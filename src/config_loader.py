import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class TelegramConfig:
    web_url: str
    target_channel_name: str
    session_profile_path: str
    initial_history_days: int
    poll_interval_seconds: int
    allowed_senders: list[str]


@dataclass(frozen=True)
class BrowserConfig:
    headless: bool
    allowed_domains: list[str]
    timeout_ms: int
    max_retries: int


@dataclass(frozen=True)
class StorageConfig:
    db_type: str
    db_path: str
    screenshots_dir: str
    log_file: str


@dataclass(frozen=True)
class BrowserUseConfig:
    openrouter_api_key: str
    openrouter_base_url: str
    model_list: list[str]
    default_model: Optional[str]
    max_steps: int
    use_vision: bool
    cdp_url: Optional[str]
    fallback_chat_index: int


@dataclass(frozen=True)
class AppConfig:
    telegram: TelegramConfig
    browser: BrowserConfig
    browser_use: BrowserUseConfig
    selectors_file: str
    storage: StorageConfig
    raw: dict


def _resolve_path(base: Path, maybe_relative: str) -> str:
    p = Path(maybe_relative)
    if p.is_absolute():
        return str(p)
    return str((base / p).resolve())


def load_app_config(config_path: Path) -> AppConfig:
    """
    Loads `config.yaml` and environment variables from `.env` (if present).
    Notes:
    - This supports a subset of Phase 2/3 config; Sprint 1 only needs Telegram/Browser/Storage.
    """

    load_dotenv()

    config_path = config_path.resolve()
    base_dir = config_path.parent

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    telegram = raw.get("telegram", {}) or {}
    browser = raw.get("browser", {}) or {}
    storage = raw.get("storage", {}) or {}

    selectors_file = raw.get("selectors_file", "./config/selectors.yaml")

    # Basic sanity: URL must have a hostname.
    web_url = str(telegram.get("web_url", "https://web.telegram.org/"))
    hostname = urlparse(web_url).hostname
    if not hostname:
        raise ValueError(f"telegram.web_url is invalid: {web_url}")

    telegram_cfg = TelegramConfig(
        web_url=web_url,
        target_channel_name=str(telegram.get("target_channel_name", "")),
        session_profile_path=_resolve_path(base_dir, str(telegram.get("session_profile_path", "./browser_profiles/telegram_session"))),
        initial_history_days=int(telegram.get("initial_history_days", 30)),
        poll_interval_seconds=int(telegram.get("poll_interval_seconds", 30)),
        allowed_senders=list(telegram.get("allowed_senders", [])) if telegram.get("allowed_senders", None) is not None else [],
    )

    browser_cfg = BrowserConfig(
        headless=bool(browser.get("headless", False)),
        allowed_domains=list(browser.get("allowed_domains", ["web.telegram.org"])),
        timeout_ms=int(browser.get("timeout_ms", 15000)),
        max_retries=int(browser.get("max_retries", 3)),
    )

    storage_cfg = StorageConfig(
        db_type=str(storage.get("db_type", "sqlite")),
        db_path=_resolve_path(base_dir, str(storage.get("db_path", "./data/signals.db"))),
        screenshots_dir=_resolve_path(base_dir, str(storage.get("screenshots_dir", "./data/screenshots"))),
        log_file=_resolve_path(base_dir, str(storage.get("log_file", "./logs/system.jsonl"))),
    )

    model_list_raw = os.getenv("BROWSER_USE_MODELS", "").strip()
    model_list = [m.strip() for m in model_list_raw.split(",") if m.strip()]
    default_model = os.getenv("BROWSER_USE_DEFAULT_MODEL", "").strip() or (model_list[0] if model_list else None)
    max_steps = int(os.getenv("BROWSER_USE_MAX_STEPS", "30"))
    use_vision_raw = os.getenv("BROWSER_USE_USE_VISION", "false").strip().lower()
    use_vision = use_vision_raw in {"1", "true", "yes", "on"}

    browser_use_cfg = BrowserUseConfig(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        model_list=model_list,
        default_model=default_model,
        max_steps=max_steps,
        use_vision=use_vision,
        cdp_url=os.getenv("BROWSER_USE_CDP_URL", "").strip() or None,
        fallback_chat_index=int(os.getenv("BROWSER_USE_FALLBACK_CHAT_INDEX", "2")),
    )

    return AppConfig(
        telegram=telegram_cfg,
        browser=browser_cfg,
        browser_use=browser_use_cfg,
        selectors_file=_resolve_path(base_dir, str(selectors_file)),
        storage=storage_cfg,
        raw=raw,
    )

