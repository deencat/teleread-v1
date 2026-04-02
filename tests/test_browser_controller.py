import asyncio
import datetime as dt

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.browser_controller import BrowserController, DomainNotAllowedError


def test_validate_url_allows_allowed_domain():
    BrowserController.validate_url("https://web.telegram.org/k/", ["web.telegram.org"])


def test_validate_url_blocks_disallowed_domain():
    with pytest.raises(DomainNotAllowedError):
        BrowserController.validate_url("https://example.com/", ["web.telegram.org"])


@pytest.mark.asyncio
async def test_run_with_retries_exponential_backoff(monkeypatch):
    # max_retries=2 => attempts=3 (initial + 2 retries)
    controller = BrowserController(
        allowed_domains=["web.telegram.org"],
        timeout_ms=5000,
        max_retries=2,
        logger=None,
    )

    sleep_calls = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    attempt = {"n": 0}

    async def op():
        attempt["n"] += 1
        if attempt["n"] < 3:
            raise PlaywrightTimeoutError("Timeout while waiting for selector")
        return "ok"

    result = await controller._run_with_retries("test_op", op)
    assert result == "ok"
    assert attempt["n"] == 3

    # base_backoff_seconds default is 0.5 => delays 0.5, 1.0 for retry_index 0,1
    assert sleep_calls == [0.5, 1.0]

