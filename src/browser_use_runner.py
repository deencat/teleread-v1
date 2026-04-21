from __future__ import annotations

from typing import Optional


def _build_browser_use_task(
    *,
    telegram_web_url: str,
    target_channel_name: str,
    fallback_chat_index: int,
) -> str:
    return (
        f"Open {telegram_web_url}. "
        "If login is required, wait for manual login and continue after the chat list is visible. "
        "Use the left search box to find the target channel and click it. "
        f"The exact target title is '{target_channel_name}'. "
        "If exact match is not visible, choose the candidate containing 'Donald sir' and '判市群'. "
        f"If still ambiguous, click chat list item index {fallback_chat_index} (0-based) as fallback. "
        "After opening the channel, scroll up a few times to load older messages. "
        "Then report success with the currently open chat title."
    )


async def run_browser_use_extract_once(
    *,
    telegram_web_url: str,
    target_channel_name: str,
    openrouter_api_key: str,
    openrouter_base_url: str,
    model_name: str,
    max_steps: int,
    use_vision: bool,
    fallback_chat_index: int,
    session_profile_path: str,
    headless: bool,
    cdp_url: Optional[str] = None,
    logger=None,
) -> str:
    """
    Browser-use based alternative flow for Telegram channel opening.
    This path is useful when direct selector-based Playwright automation is brittle.
    """
    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for browser-use mode.")
    if not model_name:
        raise ValueError("No model selected for browser-use mode.")

    try:
        from browser_use import Agent
        try:
            from browser_use import ChatOpenRouter
        except Exception:
            from browser_use.llm.openrouter.chat import ChatOpenRouter
        from browser_use.browser.session import BrowserSession
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "browser-use is not installed. Install dependencies from requirements.txt first."
        ) from exc

    llm = ChatOpenRouter(
        model=model_name,
        api_key=openrouter_api_key,
        base_url=openrouter_base_url,
        temperature=0,
    )

    task = _build_browser_use_task(
        telegram_web_url=telegram_web_url,
        target_channel_name=target_channel_name,
        fallback_chat_index=fallback_chat_index,
    )
    if cdp_url:
        browser_session = BrowserSession(cdp_url=cdp_url)
    else:
        # Reuse the same persistent Telegram profile so login state survives runs.
        browser_session = BrowserSession(
            user_data_dir=session_profile_path,
            headless=headless,
            keep_alive=True,
        )

    agent = Agent(
        task=task,
        llm=llm,
        use_vision=use_vision,
        browser_session=browser_session,
    )

    if logger:
        logger.info(
            "browser_use.start",
            extra={
                "model": model_name,
                "base_url": openrouter_base_url,
                "target_channel_name": target_channel_name,
                "max_steps": max_steps,
                "use_vision": use_vision,
                "session_profile_path": session_profile_path,
                "cdp_url": cdp_url,
                "fallback_chat_index": fallback_chat_index,
            },
        )

    result = await agent.run(max_steps=max_steps)
    result_text = str(result)

    if logger:
        logger.info("browser_use.done", extra={"result": result_text[:800]})
    return result_text

