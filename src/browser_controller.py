import asyncio
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


_LOAD_STATES = {"load", "domcontentloaded", "networkidle"}


class DomainNotAllowedError(ValueError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    base_backoff_seconds: float = 0.5

    def attempts(self) -> int:
        # "max_retries" is interpreted as "number of retries after the first failure".
        return self.max_retries + 1

    def backoff_seconds(self, retry_index: int) -> float:
        # Exponential backoff: base * 2^(retry_index)
        # retry_index=0 is the first retry after the initial failure.
        return self.base_backoff_seconds * (2**retry_index)


class BrowserController:
    """
    Phase 1 browser controller with required primitive operations.

    Notes:
    - Uses an isolated Chromium profile directory.
    - Enforces a navigation domain allowlist for safety.
    - Implements retry logic for navigation timeouts / selector-not-found timeouts.
    - Exposes a Python class/module interface (no external HTTP API).
    """

    def __init__(
        self,
        *,
        allowed_domains: list[str],
        timeout_ms: int,
        max_retries: int,
        logger=None,
    ):
        self.allowed_domains = allowed_domains
        self.timeout_ms = timeout_ms
        self.retry_policy = RetryPolicy(max_retries=max_retries)
        self.logger = logger

        self._playwright = None
        self._browser = None
        self._context = None
        self.page = None

    @staticmethod
    def validate_url(url: str, allowed_domains: list[str]) -> None:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            raise ValueError(f"Invalid URL (missing hostname): {url}")
        if host not in allowed_domains:
            raise DomainNotAllowedError(f"Domain not allowed: {host}")

    async def _run_with_retries(
        self,
        operation_name: str,
        operation_coro_factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        last_exc: Optional[BaseException] = None

        for attempt_index in range(self.retry_policy.attempts()):
            try:
                return await operation_coro_factory()
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                last_exc = exc

                is_retryable = self._is_retryable_exception(exc)
                if not is_retryable or attempt_index >= self.retry_policy.attempts() - 1:
                    raise

                retry_index = attempt_index  # 0 => first retry after initial failure
                delay_s = self.retry_policy.backoff_seconds(retry_index)
                if self.logger:
                    self.logger.warning(
                        "browser.retrying",
                        extra={
                            "operation": operation_name,
                            "attempt": attempt_index + 1,
                            "delay_seconds": delay_s,
                            "error": str(exc),
                        },
                    )
                await asyncio.sleep(delay_s)

        # Should be unreachable.
        if last_exc:
            raise last_exc
        raise RuntimeError("Retry loop ended unexpectedly.")

    @staticmethod
    def _is_retryable_exception(exc: BaseException) -> bool:
        msg = str(exc).lower()
        # Covers navigation timeouts and selector-not-found timeouts (Playwright reports both as timeouts).
        return "timeout" in msg or "selector" in msg or "not found" in msg

    async def launch(self, profile_path: str, headless: bool) -> None:
        profile_dir = os.path.abspath(profile_path)
        os.makedirs(profile_dir, exist_ok=True)

        self._playwright = await async_playwright().start()
        # Important: Playwright's `user_data_dir` must be provided to
        # `launch_persistent_context` (not `Browser.new_context()`).
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
        )
        # A persistent context may already have one page.
        pages = getattr(self._context, "pages", None)
        if pages:
            self.page = pages[0]
        else:
            self.page = await self._context.new_page()

        if self.logger:
            self.logger.info("browser.launched", extra={"headless": headless, "profile_path": profile_dir})

    async def goto(self, url: str) -> None:
        # Enforce allowlist and log blocked attempts.
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            raise ValueError(f"Invalid URL (missing hostname): {url}")
        if host not in self.allowed_domains:
            if self.logger:
                self.logger.warning(
                    "browser.domain_blocked",
                    extra={"url": url, "host": host, "allowed_domains": self.allowed_domains},
                )
            raise DomainNotAllowedError(f"Domain not allowed: {host}")
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            # `wait_until='load'` tends to be stable for initial navigation.
            await self.page.goto(url, timeout=self.timeout_ms, wait_until="load")

        await self._run_with_retries("goto", op)

    async def wait_for(self, selector_or_load_state: str, *, timeout_ms: Optional[int] = None) -> None:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")
        timeout_ms = timeout_ms or self.timeout_ms

        async def op():
            if selector_or_load_state in _LOAD_STATES:
                await self.page.wait_for_load_state(selector_or_load_state, timeout=timeout_ms)
            else:
                # Telegram Web frequently attaches DOM nodes slightly before they are
                # considered "visible" by Playwright. Prefer "attached" for reliability.
                await self.page.wait_for_selector(selector_or_load_state, timeout=timeout_ms, state="attached")

        await self._run_with_retries("wait_for", op)

    async def click(self, selector: str) -> None:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            await self.page.click(selector, timeout=self.timeout_ms)

        await self._run_with_retries("click", op)

    async def type_text(self, selector: str, text: str) -> None:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            await self.page.fill(selector, text, timeout=self.timeout_ms)

        await self._run_with_retries("type_text", op)

    # Spec alias: Phase 1 primitive is named `type`.
    async def type(self, selector: str, text: str) -> None:
        await self.type_text(selector, text)

    async def scroll(self, container_selector: str, direction: str, pixels: int) -> None:
        if direction not in {"up", "down"}:
            raise ValueError("direction must be 'up' or 'down'")
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            # Important: don't throw if the selector isn't present.
            # Throwing triggers the controller retry loop and can stall extraction.
            await self.page.evaluate(
                """
                (args) => {
                  const [sel, dir, px] = args;
                  const deepQuerySelector = (root, selector) => {
                    if (!root) return null;
                    if (root.querySelector) {
                      const direct = root.querySelector(selector);
                      if (direct) return direct;
                    }
                    // Search Shadow DOM boundaries.
                    if (root.querySelectorAll) {
                      for (const node of Array.from(root.querySelectorAll('*'))) {
                        if (node && node.shadowRoot) {
                          const found = deepQuerySelector(node.shadowRoot, selector);
                          if (found) return found;
                        }
                      }
                    }
                    return null;
                  };

                  let el = deepQuerySelector(document, sel);
                  if (!el) {
                    // Heuristic fallback: find a message element and its
                    // scrollable ancestor.
                    const msgEl = deepQuerySelector(document, '[id^="message-"]');
                    let p = msgEl;
                    while (p && p !== document.body && p instanceof Element) {
                      if (p.scrollHeight && p.clientHeight && p.scrollHeight > p.clientHeight) {
                        el = p;
                        break;
                      }
                      p = p.parentElement;
                    }
                  }
                  if (!el) return false;
                  const delta = (dir === 'up' ? -px : px);
                  el.scrollTop = el.scrollTop + delta;
                  return true;
                }
                """,
                [container_selector, direction, pixels],
            )

        await self._run_with_retries("scroll", op)

    async def screenshot(self, file_path: str, *, full_page: bool) -> None:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        out_path = os.path.abspath(file_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        await self.page.screenshot(path=out_path, full_page=full_page)

    async def get_text(self, selector: str) -> str:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            return await self.page.inner_text(selector, timeout=self.timeout_ms)

        return await self._run_with_retries("get_text", op)

    async def get_html(self, selector: str) -> str:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            return await self.page.inner_html(selector, timeout=self.timeout_ms)

        return await self._run_with_retries("get_html", op)

    async def evaluate_js(self, script: str, *args: Any) -> Any:
        if not self.page:
            raise RuntimeError("Browser not launched. Call `launch()` first.")

        async def op():
            # Playwright's `page.evaluate` supports passing at most one argument.
            # When multiple args are provided, pack them into a list and let the
            # JS snippet destructure from that single array argument.
            if len(args) == 0:
                return await self.page.evaluate(script)
            if len(args) == 1:
                return await self.page.evaluate(script, args[0])
            return await self.page.evaluate(script, list(args))

        return await self._run_with_retries("evaluate_js", op)

    async def close(self) -> None:
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass

        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self.page = None
        self._context = None
        self._browser = None
        self._playwright = None

