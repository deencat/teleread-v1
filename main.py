import argparse
import asyncio
from pathlib import Path

from src.browser_controller import BrowserController
from src.browser_use_runner import run_browser_use_extract_once
from src.config_loader import load_app_config
from src.logger import init_logger
from src.telegram_extractor import TelegramExtractor
from src.storage import init_db


async def run_smoke() -> None:
    """
    Minimal runnable check for Sprint 1:
    - load config + env
    - init JSON logger + SQLite schema
    - launch Chromium in an isolated profile
    - navigate to the allowlisted Telegram Web URL
    """

    cfg = load_app_config(Path("config.yaml"))
    logger = init_logger(cfg.storage.log_file)
    logger.info("smoke.start", extra={"mode": "smoke"})

    db = await init_db(cfg.storage.db_path, logger=logger)
    try:
        controller = BrowserController(
            allowed_domains=cfg.browser.allowed_domains,
            timeout_ms=cfg.browser.timeout_ms,
            max_retries=cfg.browser.max_retries,
            logger=logger,
        )
        await controller.launch(
            profile_path=cfg.telegram.session_profile_path,
            headless=cfg.browser.headless,
        )
        try:
            await controller.goto(cfg.telegram.web_url)
            # If not logged in yet, Telegram will still render a page; we just ensure navigation works.
            await controller.wait_for("domcontentloaded", timeout_ms=cfg.browser.timeout_ms)
            logger.info("smoke.navigation_complete")
        finally:
            await controller.close()
    finally:
        await db.close()


async def run_extract_history_once() -> None:
    """
    Sprint 2: manual login + channel discovery + initial history extraction into `messages_raw`.
    """

    cfg = load_app_config(Path("config.yaml"))
    logger = init_logger(cfg.storage.log_file)
    logger.info("extract_history_once.start", extra={"mode": "extract_history_once"})

    db = await init_db(cfg.storage.db_path, logger=logger)
    controller = BrowserController(
        allowed_domains=cfg.browser.allowed_domains,
        timeout_ms=cfg.browser.timeout_ms,
        max_retries=cfg.browser.max_retries,
        logger=logger,
    )
    try:
        await controller.launch(
            profile_path=cfg.telegram.session_profile_path,
            headless=cfg.browser.headless,
        )

        extractor = TelegramExtractor(selectors_file=cfg.selectors_file)
        await extractor.ensure_logged_in(
            controller,
            telegram_web_url=cfg.telegram.web_url,
        )
        await extractor.open_channel(
            controller,
            target_channel_name=cfg.telegram.target_channel_name,
        )

        inserted = await extractor.extract_history_once(
            controller,
            db,
            channel_name=cfg.telegram.target_channel_name,
            initial_history_days=cfg.telegram.initial_history_days,
            screenshot_dir=cfg.storage.screenshots_dir,
            logger=logger,
        )
        logger.info("extract_history_once.done", extra={"inserted": inserted})
    finally:
        await controller.close()
        await db.close()


async def run_extract_history_once_browser_use(*, model_override: str | None = None) -> None:
    """
    Alternative extraction entrypoint using browser-use + OpenRouter models.
    """
    cfg = load_app_config(Path("config.yaml"))
    logger = init_logger(cfg.storage.log_file)
    logger.info("extract_history_once_browser_use.start", extra={"mode": "extract_history_once_browser_use"})

    selected_model = (model_override or cfg.browser_use.default_model or "").strip()
    if not selected_model:
        raise ValueError(
            "No browser-use model selected. Set BROWSER_USE_DEFAULT_MODEL or pass --browseruse-model."
        )

    result_text = await run_browser_use_extract_once(
        telegram_web_url=cfg.telegram.web_url,
        target_channel_name=cfg.telegram.target_channel_name,
        openrouter_api_key=cfg.browser_use.openrouter_api_key,
        openrouter_base_url=cfg.browser_use.openrouter_base_url,
        model_name=selected_model,
        max_steps=cfg.browser_use.max_steps,
        use_vision=cfg.browser_use.use_vision,
        fallback_chat_index=cfg.browser_use.fallback_chat_index,
        session_profile_path=cfg.telegram.session_profile_path,
        headless=cfg.browser.headless,
        cdp_url=cfg.browser_use.cdp_url,
        logger=logger,
    )
    logger.info(
        "extract_history_once_browser_use.done",
        extra={
            "selected_model": selected_model,
            "available_models": cfg.browser_use.model_list,
            "result_preview": result_text[:800],
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["smoke", "extract_history_once", "extract_history_once_browser_use"],
        default="smoke",
    )
    parser.add_argument(
        "--browseruse-model",
        default=None,
        help="Override browser-use model (otherwise uses BROWSER_USE_DEFAULT_MODEL from .env).",
    )
    args = parser.parse_args()

    if args.mode == "smoke":
        asyncio.run(run_smoke())
    elif args.mode == "extract_history_once":
        asyncio.run(run_extract_history_once())
    elif args.mode == "extract_history_once_browser_use":
        asyncio.run(run_extract_history_once_browser_use(model_override=args.browseruse_model))


if __name__ == "__main__":
    main()

