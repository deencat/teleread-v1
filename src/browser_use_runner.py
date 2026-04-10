from __future__ import annotations

from typing import Optional


def _build_browser_use_task(*, telegram_web_url: str, target_channel_name: str) -> str:
    return (
        f"Open {telegram_web_url}. "
        "If login is required, wait for manual login and continue after the chat list is visible. "
        f"Open the Telegram channel titled exactly '{target_channel_name}'. "
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
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "browser-use is not installed. Install dependencies from requirements.txt first."
        ) from exc

    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "langchain-openai is not installed. Install dependencies from requirements.txt first."
        ) from exc

    llm = ChatOpenAI(
        model=model_name,
        api_key=openrouter_api_key,
        base_url=openrouter_base_url,
        temperature=0,
    )

    task = _build_browser_use_task(
        telegram_web_url=telegram_web_url,
        target_channel_name=target_channel_name,
    )
    agent = Agent(task=task, llm=llm)

    if logger:
        logger.info(
            "browser_use.start",
            extra={
                "model": model_name,
                "base_url": openrouter_base_url,
                "target_channel_name": target_channel_name,
                "max_steps": max_steps,
            },
        )

    result = await agent.run(max_steps=max_steps)
    result_text = str(result)

    if logger:
        logger.info("browser_use.done", extra={"result": result_text[:800]})
    return result_text

