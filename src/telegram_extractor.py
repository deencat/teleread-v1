import asyncio
import datetime as dt
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from src.storage import insert_message_raw


class TelegramExtractor:
    """
    Phase 1 Telegram Web automation module.

    Sprint 1 scaffolding currently does not implement full extraction; this class
    exists so later sprints can wire Telegram-specific DOM extraction without
    changing the project structure.
    """

    def __init__(self, *, selectors_file: str):
        self.selectors_file = selectors_file
        self.sel = self._load_selectors(Path(selectors_file))

    @staticmethod
    def _load_selectors(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _relative_selector(full: str, container: str) -> str:
        # Turn selectors like `.chatlist-chat .peer-title` into `.peer-title` when querying inside `.chatlist-chat`.
        prefix = container.rstrip() + " "
        if full.startswith(prefix):
            return full[len(prefix) :]
        return full

    @staticmethod
    def _normalize_channel_name(name: str) -> str:
        n = (name or "").strip()
        if n.startswith("@"):
            n = n[1:]
        # Telegram Web often prepends an emoji/icon before the chat title.
        # Strip leading non-word symbols so matching doesn't depend on that emoji.
        n = re.sub(r"^[^\w]+", "", n, flags=re.UNICODE)
        # Remove zero-width / format characters.
        n = re.sub(r"[\u200B-\u200D\uFEFF]", "", n)
        # Explicitly normalize NBSP (sometimes appears as whitespace from DOM text).
        n = n.replace("\u00A0", " ")
        # Also strip all whitespace to avoid mismatch due to formatting.
        n = re.sub(r"\s+", "", n, flags=re.UNICODE)
        return n.lower()

    async def ensure_logged_in(
        self,
        controller,
        *,
        telegram_web_url: str,
        manual_login_timeout_ms: int = 600_000,
    ) -> None:
        """
        Navigates to Telegram Web and waits for the chat list.
        If this is the first run, the operator completes manual login in the opened browser.
        """

        chat_list = self.sel.get("chat_list", {}) or {}
        # Wait for an actual chat row to exist; `.chatlist` alone can appear
        # before Telegram finishes fully loading the inbox after login.
        chat_item_sel = chat_list.get("chat_item", ".chatlist-chat")

        await controller.goto(telegram_web_url)
        await controller.wait_for(chat_item_sel, timeout_ms=manual_login_timeout_ms)

    async def open_channel(
        self,
        controller,
        *,
        target_channel_name: str,
    ) -> None:
        # Used for recovery when Telegram doesn't render the message DOM yet.
        self._last_clicked_chat_idx: Optional[int] = None
        chat_list = self.sel.get("chat_list", {}) or {}
        chat_item_sel = chat_list.get("chat_item", ".chatlist-chat")
        self._last_clicked_chat_item_sel = chat_item_sel
        chat_title_sel_full = chat_list.get("chat_title", ".chatlist-chat .peer-title")
        chat_title_sel = self._relative_selector(chat_title_sel_full, chat_item_sel)
        scroll_wrapper_sel = chat_list.get("scroll_wrapper", ".sidebar-left .scrollable-y")

        target_norm = self._normalize_channel_name(target_channel_name)
        if not target_norm:
            raise ValueError("target_channel_name is empty; update config.yaml before extraction.")

        controller_logger = getattr(controller, "logger", None)

        EVAL_FIND_AND_CLICK = r"""
        (args) => {
          const [chatItemSel, chatTitleSel, targetNorm] = args;
          const items = Array.from(document.querySelectorAll(chatItemSel));
          for (let i = 0; i < items.length; i++) {
            const el = items[i];
            const t = el.querySelector(chatTitleSel);
            // Normalize the DOM title similarly to Python:
            // - strip leading @
            // - strip leading emoji/icons/symbols (keep letters/numbers incl CJK)
            let title = (t && t.innerText ? t.innerText.trim() : '').replace(/^@/, '');
            title = title.replace(/^[^\p{L}\p{N}]+/u, '').toLowerCase();
            title = title.replace(/[\u200B-\u200D\uFEFF]/g, '');
            title = title.replace(/\s+/g, '');
            const targetNormNoWs = String(targetNorm).replace(/\s+/g, '');
            if (title === targetNormNoWs || title.includes(targetNormNoWs) || targetNormNoWs.includes(title)) {
              el.click();
              return i;
            }
          }
          return -1;
        }
        """

        EVAL_IS_AT_TOP = r"""
        (scrollSel) => {
          const el = document.querySelector(scrollSel);
          // If the scroll container isn't found, don't assume we're at the top.
          // Return false so we keep scrolling and allow selector fallbacks.
          if (!el) return false;
          return el.scrollTop <= 0;
        }
        """

        # Try multiple scrolls until we locate the chat row.
        for _ in range(80):
            clicked_idx = await controller.evaluate_js(EVAL_FIND_AND_CLICK, chat_item_sel, chat_title_sel, target_norm)
            if isinstance(clicked_idx, (int, float)) and clicked_idx >= 0:
                if controller_logger:
                    controller_logger.warning(
                        "telegram.channel_click_success",
                        extra={"extra": {"clicked_idx": int(clicked_idx), "chat_item_sel": chat_item_sel}},
                    )
                self._last_clicked_chat_idx = int(clicked_idx)
                return

            await asyncio.sleep(0.5)
            at_top = await controller.evaluate_js(EVAL_IS_AT_TOP, scroll_wrapper_sel)
            if at_top:
                break

            # Scroll the chat list upward to load earlier items.
            await controller.scroll(scroll_wrapper_sel, "up", 900)

        # One last attempt after the final scroll.
        clicked_idx = await controller.evaluate_js(EVAL_FIND_AND_CLICK, chat_item_sel, chat_title_sel, target_norm)
        if isinstance(clicked_idx, (int, float)) and clicked_idx >= 0:
            if controller_logger:
                controller_logger.warning(
                    "telegram.channel_click_success_final_attempt",
                    extra={"extra": {"clicked_idx": int(clicked_idx), "chat_item_sel": chat_item_sel}},
                )
            self._last_clicked_chat_idx = int(clicked_idx)
            return

        # Debug: log candidate titles so the user can set an exact match if needed.
        collect = r"""
        (args) => {
          const [chatItemSel, chatTitleSel, limit] = args;
          const items = Array.from(document.querySelectorAll(chatItemSel)).slice(0, limit);
          const norm = (s) => {
            if (!s) return '';
            s = String(s).trim().replace(/^@/, '');
            s = s.replace(/^[^\p{L}\p{N}]+/u, '');
            s = s.replace(/[\u200B-\u200D\uFEFF]/g, '');
            s = s.replace(/\s+/g, '').toLowerCase();
            return s;
          };
          return items.map((el, idx) => {
            const t = el.querySelector(chatTitleSel);
            const raw = (t && t.innerText) ? t.innerText.trim() : '';
            return { idx, raw, norm: norm(raw) };
          });
        }
        """
        try:
            candidates = await controller.evaluate_js(collect, chat_item_sel, chat_title_sel, 15)
            if controller_logger:
                controller_logger.warning(
                    "telegram.channel_not_found_debug",
                    extra={
                        "target_channel_name": target_channel_name,
                        "target_norm": target_norm,
                        "candidates": candidates,
                    },
                )

            if controller_logger and isinstance(candidates, list) and candidates:
                # Print escaped forms to catch subtle Unicode/codepoint mismatches.
                target_norm_esc = target_norm.encode("unicode_escape").decode("ascii")
                checks = []
                for c in candidates[:6]:
                    raw = c.get("raw", "")
                    py_norm = self._normalize_channel_name(raw)
                    checks.append(
                        {
                            "idx": c.get("idx"),
                            "py_norm_escape": py_norm.encode("unicode_escape").decode("ascii"),
                            "equals_target_norm": py_norm == target_norm,
                        }
                    )
                controller_logger.warning(
                    "telegram.channel_match_debug",
                    extra={"target_norm_escape": target_norm_esc, "checks": checks},
                )

            # Robust token-based selection to avoid subtle Unicode comparison issues.
            # Choose the first candidate whose raw title contains an English token
            # from the configured `target_channel_name` (e.g., "donald").
            ascii_tokens = re.findall(r"[A-Za-z]+", target_channel_name)
            ascii_token = ascii_tokens[0].lower() if ascii_tokens else ""
            cjk_tokens = re.findall(r"[\u4e00-\u9fff]+", target_channel_name)
            # Prefer the last CJK token (e.g. "判市群") instead of the first
            # (e.g. "短炒世界升級系統") which may exist in multiple chats.
            cjk_token = cjk_tokens[-1] if cjk_tokens else ""
            cjk_fallback = cjk_token[-2:] if len(cjk_token) >= 2 else ""

            def score_candidate(raw: str) -> int:
                raw_lower = raw.lower()
                score = 0
                if cjk_token and cjk_token in raw:
                    score += 100
                elif cjk_fallback and cjk_fallback in raw:
                    score += 60

                if ascii_token and ascii_token in raw_lower:
                    score += 50
                elif ascii_token and len(ascii_token) >= 4 and ascii_token[:4] in raw_lower:
                    score += 20
                return score

            best = None  # (score, idx)
            for c in candidates or []:
                raw = str(c.get("raw", ""))
                idx = c.get("idx")
                s = score_candidate(raw)
                if idx is None:
                    continue
                if best is None or s > best[0]:
                    best = (s, idx)

            match_idx_py = None
            if best is not None:
                # Require some minimum signal. If we only find a weak substring
                # match (e.g. just "群"), we avoid wrong-clicking.
                if best[0] >= 80:
                    match_idx_py = best[1]

            if match_idx_py is not None and match_idx_py >= 0:
                EVAL_CLICK_BY_INDEX = r"""
                (args) => {
                  const [chatItemSel, idx] = args;
                  const items = Array.from(document.querySelectorAll(chatItemSel)).slice(0, 15);
                  if (!items[idx]) return false;
                  items[idx].click();
                  return true;
                }
                """
                clicked = await controller.evaluate_js(EVAL_CLICK_BY_INDEX, chat_item_sel, int(match_idx_py))
                if controller_logger:
                    controller_logger.warning(
                        "telegram.channel_token_click_result",
                        extra={"clicked": clicked, "match_idx_py": match_idx_py},
                    )
                if clicked:
                    self._last_clicked_chat_idx = int(match_idx_py)
                    return

            # Find matching chat index in JS (using the same normalization function
            # as the candidate collector), then click it.
            # This avoids Python/JS Unicode mismatch issues.
            EVAL_FIND_MATCH_IDX = r"""
            (args) => {
              const [chatItemSel, chatTitleSel, targetNorm] = args;
              const items = Array.from(document.querySelectorAll(chatItemSel)).slice(0, 15);
              const norm = (s) => {
                if (!s) return '';
                s = String(s).trim().replace(/^@/, '');
                s = s.replace(/^[^\p{L}\p{N}]+/u, '');
                s = s.replace(/[\u200B-\u200D\uFEFF]/g, '');
                s = s.replace(/\s+/g, '').toLowerCase();
                return s;
              };
              const tn = String(targetNorm).replace(/\s+/g, '');
              for (let i = 0; i < items.length; i++) {
                const t = items[i].querySelector(chatTitleSel);
                const raw = (t && t.innerText) ? t.innerText.trim() : '';
                const rn = norm(raw);
                if (rn === tn || rn.includes(tn) || tn.includes(rn)) return i;
              }
              return -1;
            }
            """
            match_idx = await controller.evaluate_js(EVAL_FIND_MATCH_IDX, chat_item_sel, chat_title_sel, target_norm)
            if controller_logger:
                controller_logger.warning(
                    "telegram.channel_js_match_idx",
                    extra={"match_idx": match_idx, "target_norm": target_norm},
                )
            if match_idx is not None and isinstance(match_idx, (int, float)) and match_idx >= 0:
                EVAL_CLICK_BY_INDEX = r"""
                (args) => {
                  const [chatItemSel, idx] = args;
                  const items = Array.from(document.querySelectorAll(chatItemSel)).slice(0, 15);
                  if (!items[idx]) return false;
                  items[idx].click();
                  return true;
                }
                """
                clicked = await controller.evaluate_js(EVAL_CLICK_BY_INDEX, chat_item_sel, int(match_idx))
                if controller_logger:
                    controller_logger.warning(
                        "telegram.channel_index_click_result",
                        extra={"clicked": clicked, "match_idx": match_idx},
                    )
                if clicked:
                    self._last_clicked_chat_idx = int(match_idx)
                    return
        except Exception:
            # Don't mask the original "not found" failure.
            pass

        raise RuntimeError(f"Target channel not found: {target_channel_name}")

    async def extract_history_once(
        self,
        controller,
        db,
        *,
        channel_name: str,
        initial_history_days: int,
        screenshot_dir: Optional[str] = None,
        logger=None,
        max_scroll_rounds: int = 60,
        scroll_pixels: int = 900,
    ) -> int:
        """
        Phase 1: one-time extraction of chat history by scrolling upward and inserting unique messages into `messages_raw`.
        Returns number of inserted rows.
        """

        chat_window = self.sel.get("chat_window", {}) or {}
        content_bubble_sel = chat_window.get("content_bubble", ".bubble:not(.service)")
        message_bubble_sel = chat_window.get("message_bubble", ".bubble")
        message_id_attr = (self.sel.get("attributes", {}) or {}).get("message_id_attr", "data-mid")
        peer_id_attr = (self.sel.get("attributes", {}) or {}).get("peer_id_attr", "data-peer-id")
        timestamp_title_attr = (self.sel.get("attributes", {}) or {}).get("timestamp_title", "title")

        messages_container_sel = chat_window.get("messages_container", ".bubbles-inner")
        scroll_container_sel = chat_window.get("scroll_container", ".bubbles .scrollable-y")

        message_text_full = chat_window.get("message_text", ".bubble .message")
        sender_name_full = chat_window.get("sender_name", ".bubble .peer-title")
        timestamp_full = chat_window.get("timestamp", ".bubble .time .time-inner")
        photo_element_full = chat_window.get("photo_element", ".bubble .attachment img")
        document_element_full = chat_window.get("document_element", ".bubble .document")

        # Relative selectors for querying inside a message bubble element.
        message_text_sel = self._relative_selector(message_text_full, ".bubble")
        sender_name_sel = self._relative_selector(sender_name_full, ".bubble")
        timestamp_sel = self._relative_selector(timestamp_full, ".bubble")
        photo_element_sel = self._relative_selector(photo_element_full, ".bubble")
        document_element_sel = self._relative_selector(document_element_full, ".bubble")

        # Cutoff: "initial_history_days back from now".
        now_utc = dt.datetime.now(dt.timezone.utc)
        cutoff = now_utc - dt.timedelta(days=int(initial_history_days))

        EVAL_EXTRACT_VISIBLE = r"""
        (args) => {
          const [contentBubbleSel, messageIdAttr, peerIdAttr, timestampSel, timestampTitleAttr, messageTextSel, senderNameSel, photoSel, docSel] = args;
          const deepQuerySelectorAll = (root, selector) => {
            const results = [];
            if (!root) return results;
            if (root.querySelectorAll) results.push(...Array.from(root.querySelectorAll(selector)));
            if (root.querySelectorAll) {
              for (const el of Array.from(root.querySelectorAll('*'))) {
                if (el && el.shadowRoot) {
                  results.push(...deepQuerySelectorAll(el.shadowRoot, selector));
                }
              }
            }
            return results;
          };

          const bubbles = deepQuerySelectorAll(document, contentBubbleSel);
          const out = [];
          for (const el of bubbles) {
            let messageId = el.getAttribute(messageIdAttr);
            if (!messageId && el.id && String(el.id).startsWith('message-')) {
              const candidate = String(el.id).slice('message-'.length);
              // Best-effort fallback: Telegram may change ID formats; accept
              // non-numeric tail markers as well so extraction doesn't stall.
              if (candidate) messageId = candidate;
            }
            if (!messageId) continue;

            const senderEl = el.querySelector(senderNameSel);
            const senderName = senderEl && senderEl.innerText ? senderEl.innerText.trim() : null;

            const textEl = el.querySelector(messageTextSel);
            const messageText = textEl && textEl.innerText ? textEl.innerText : '';

            const tsEl = el.querySelector(timestampSel);
            const tsTitle = tsEl ? tsEl.getAttribute(timestampTitleAttr) : null;
            let tsIso = null;
            if (tsTitle) {
              const d = new Date(tsTitle);
              if (!isNaN(d.getTime())) tsIso = d.toISOString();
            }

            let hasMedia = false;
            let mediaUrl = null;
            const photoEl = el.querySelector(photoSel);
            if (photoEl && photoEl.src) {
              hasMedia = true;
              mediaUrl = photoEl.src;
            }

            const docEl = el.querySelector(docSel);
            if (!hasMedia && docEl) {
              hasMedia = true;
              // Best-effort: try to extract a usable link.
              const a = docEl.querySelector('a');
              if (a && a.href) mediaUrl = a.href;
            }

            out.push({
              message_id: messageId,
              sender_name: senderName,
              message_text: messageText,
              message_html: el.innerHTML,
              has_media: hasMedia,
              media_url: mediaUrl,
              timestamp_utc_iso: tsIso,
              peer_id: el.getAttribute(peerIdAttr) || null,
            });
          }
          return out;
        }
        """

        EVAL_IS_AT_TOP = r"""
        (scrollSel) => {
          const el = document.querySelector(scrollSel);
          if (!el) return true;
          return el.scrollTop <= 0;
        }
        """

        EVAL_DEBUG_BUBBLE_COUNTS = r"""
        (args) => {
          const [sel, messageIdAttr] = args;
          const deepQuerySelectorAll = (root, selector) => {
            const results = [];
            if (!root) return results;
            if (root.querySelectorAll) results.push(...Array.from(root.querySelectorAll(selector)));
            if (root.querySelectorAll) {
              for (const el of Array.from(root.querySelectorAll('*'))) {
                if (el && el.shadowRoot) {
                  results.push(...deepQuerySelectorAll(el.shadowRoot, selector));
                }
              }
            }
            return results;
          };

          const els = deepQuerySelectorAll(document, sel);
          const withMid = els.filter((el) => el.getAttribute(messageIdAttr));
          const anyMidEls = deepQuerySelectorAll(document, "[" + messageIdAttr + "]");
          const anyMsgIdFromIdEls = deepQuerySelectorAll(document, '[id^="message-"]');
          const numericMsgIdEls = anyMsgIdFromIdEls.filter((el) => {
            if (!el || !el.id) return false;
            const candidate = String(el.id).replace(/^message-/, '');
            return /^\d+$/.test(candidate);
          });
          const iframes = Array.from(document.querySelectorAll("iframe"));
          const sample_ids = els.slice(0, 5).map((el) => (el && el.id ? el.id : null));
          const sample_numeric_ids = numericMsgIdEls.slice(0, 5).map((el) => (el && el.id ? el.id : null));
          return {
            bubble_count: els.length,
            with_mid_count: withMid.length,
            mid_attr_count: anyMidEls.length,
            message_id_from_id_count: numericMsgIdEls.length,
            iframe_count: iframes.length,
            iframe_src_sample: iframes.length ? iframes[0].src : null,
            sample_mid: withMid.length ? withMid[0].getAttribute(messageIdAttr) : null,
            sample_any_mid: anyMidEls.length ? anyMidEls[0].getAttribute(messageIdAttr) : null,
            sample_ids: sample_ids,
            sample_numeric_ids: sample_numeric_ids,
            sample_message_id_from_id: numericMsgIdEls.length
              ? String(numericMsgIdEls[0].id).replace(/^message-/, '')
              : null,
          };
        }
        """

        # After switching chats, Telegram may take a while to render the message list.
        # Avoid blocking hard on a single bubble selector; instead, start extraction
        # immediately and let the scroll rounds load more DOM.
        content_bubble_sel_to_use = content_bubble_sel

        # Scroll container selector can vary; do not block on it.
        # We'll attempt scrolling and fall back on failures.
        active_scroll_sel = scroll_container_sel
        bubble_debug: Optional[dict[str, Any]] = None

        if logger:
            logger.info(
                "telegram.history.ready",
                extra={
                    "channel_name": channel_name,
                    "active_scroll_sel": active_scroll_sel,
                    "content_bubble_sel": content_bubble_sel_to_use,
                },
            )

            # Helps diagnose why extraction yields `visible_count = 0`.
            # If `bubble_count` is >0 but `with_mid_count` is 0, our selector/attrs
            # don't match Telegram's current DOM.
            try:
                # Poll briefly after the click to allow Telegram to attach DOM nodes.
                # (We avoid long blocking waits.)
                debug_sel = message_bubble_sel
                bubble_debug = None
                # Wait for any message DOM to attach (data-mid is our ingestion key).
                for _ in range(15):
                    bubble_debug = await controller.evaluate_js(
                        EVAL_DEBUG_BUBBLE_COUNTS,
                        debug_sel,
                        message_id_attr,
                    )
                    if bubble_debug and (
                        bubble_debug.get("mid_attr_count", 0) > 0
                        or bubble_debug.get("message_id_from_id_count", 0) > 0
                    ):
                        break
                    await asyncio.sleep(1)

                logger.info("telegram.history.bubble_debug", extra={"extra": bubble_debug})
            except Exception:
                pass

        # Fail fast only when we don't even see message DOM nodes.
        # Telegram often renders "tail markers" first; those match our selectors
        # but are not numeric messages yet. In that case, we should keep scrolling.
        if (
            bubble_debug
            and bubble_debug.get("bubble_count", 0) == 0
            and bubble_debug.get("mid_attr_count", 0) == 0
            and bubble_debug.get("message_id_from_id_count", 0) == 0
        ):
            if logger:
                logger.warning(
                    "telegram.history.no_message_dom",
                    extra={
                        "channel_name": channel_name,
                        "mid_attr_count": bubble_debug.get("mid_attr_count"),
                        "iframe_count": bubble_debug.get("iframe_count"),
                    },
                )
            # Recovery: re-click the same chat row once and re-check.
            last_idx = getattr(self, "_last_clicked_chat_idx", None)
            last_sel = getattr(self, "_last_clicked_chat_item_sel", None)
            if last_idx is not None and last_sel:
                EVAL_CLICK_BY_IDX_NO_SLICE = r"""
                (args) => {
                  const [chatItemSel, idx] = args;
                  const items = Array.from(document.querySelectorAll(chatItemSel));
                  if (!items[idx]) return false;
                  items[idx].click();
                  return true;
                }
                """
                try:
                    if logger:
                        logger.warning(
                            "telegram.history.no_message_dom_reclick",
                            extra={"extra": {"clicked_idx": int(last_idx)}},
                        )
                    clicked = await controller.evaluate_js(
                        EVAL_CLICK_BY_IDX_NO_SLICE,
                        last_sel,
                        int(last_idx),
                    )
                    if clicked:
                        bubble_debug = None
                        for _ in range(15):
                            bubble_debug = await controller.evaluate_js(
                                EVAL_DEBUG_BUBBLE_COUNTS,
                                message_bubble_sel,
                                message_id_attr,
                            )
                            if bubble_debug and bubble_debug.get("mid_attr_count", 0) > 0:
                                break
                            await asyncio.sleep(1)
                        if bubble_debug and bubble_debug.get("mid_attr_count", 0) > 0:
                            if logger:
                                logger.info(
                                    "telegram.history.no_message_dom_recovered",
                                    extra={"extra": {"mid_attr_count": bubble_debug.get("mid_attr_count")}},
                                )
                        else:
                            return 0
                except Exception:
                    return 0
            else:
                return 0

        inserted_total = 0
        fallback_ts = dt.datetime.now(dt.timezone.utc)

        current_scroll_sel = active_scroll_sel
        last_visible_count: Optional[int] = None
        unchanged_rounds = 0
        empty_rounds = 0

        for _round in range(max_scroll_rounds):
            visible = await controller.evaluate_js(
                EVAL_EXTRACT_VISIBLE,
                content_bubble_sel_to_use,
                message_id_attr,
                peer_id_attr,
                timestamp_sel,
                timestamp_title_attr,
                message_text_sel,
                sender_name_sel,
                photo_element_sel,
                document_element_sel,
            )

            # Insert visible messages (de-dup is enforced by UNIQUE(channel_name, message_id)).
            oldest_seen: Optional[dt.datetime] = None

            visible_count = len(visible) if visible else 0
            if visible_count == 0:
                empty_rounds += 1
            else:
                empty_rounds = 0

            if empty_rounds >= 2 and content_bubble_sel_to_use != message_bubble_sel:
                content_bubble_sel_to_use = message_bubble_sel
                empty_rounds = 0
                if logger:
                    logger.warning(
                        "telegram.history.content_selector_forced_bubble",
                        extra={
                            "channel_name": channel_name,
                            "content_bubble_sel": content_bubble_sel_to_use,
                            "round": _round,
                        },
                    )
            if last_visible_count is not None:
                if visible_count == last_visible_count:
                    unchanged_rounds += 1
                else:
                    unchanged_rounds = 0

            if unchanged_rounds >= 2 and current_scroll_sel != messages_container_sel:
                current_scroll_sel = messages_container_sel
                unchanged_rounds = 0
                if logger:
                    logger.warning(
                        "telegram.history.scroll_selector_fallback",
                        extra={
                            "round": _round,
                            "visible_count": visible_count,
                            "new_scroll_sel": current_scroll_sel,
                        },
                    )

            last_visible_count = visible_count

            if logger and _round % 5 == 0:
                sample = visible[0] if visible else None
                logger.info(
                    "telegram.history.round_sample",
                    extra={
                        "round": _round,
                        "visible_count": len(visible),
                        "sample_message_id": sample.get("message_id") if sample else None,
                        "sample_has_timestamp": bool(sample.get("timestamp_utc_iso")) if sample else None,
                    },
                )
            for msg in visible:
                ts_iso = msg.get("timestamp_utc_iso")
                if ts_iso:
                    ts = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
                    if oldest_seen is None or ts < oldest_seen:
                        oldest_seen = ts
                else:
                    # If Telegram DOM doesn't expose a parseable timestamp, store the
                    # message with a fallback timestamp so ingestion still works.
                    ts = fallback_ts

                inserted_total += await insert_message_raw(
                    db,
                    channel_name=channel_name,
                    message_id=msg["message_id"],
                    sender_name=msg.get("sender_name"),
                    message_text=msg.get("message_text"),
                    message_html=msg.get("message_html"),
                    has_media=bool(msg.get("has_media")),
                    media_url=msg.get("media_url"),
                    screenshot_path=None,
                    timestamp_utc=ts,
                )

            if oldest_seen is not None and oldest_seen <= cutoff:
                if logger:
                    logger.info("telegram.history.cutoff_reached", extra={"oldest_seen": oldest_seen.isoformat()})
                break

            at_top = False
            if current_scroll_sel:
                at_top = await controller.evaluate_js(EVAL_IS_AT_TOP, current_scroll_sel)

            # If we didn't find any visible message bubbles yet, don't assume we're
            # done just because scrollTop is at 0; Telegram may render lazily and
            # our selector might be too narrow. Keep scrolling to trigger DOM updates.
            if at_top and visible_count > 0:
                break

            if current_scroll_sel:
                try:
                    await controller.scroll(current_scroll_sel, "up", scroll_pixels)
                except Exception:
                    # Selector isn't usable for scrolling in this DOM state.
                    failed_sel = current_scroll_sel
                    current_scroll_sel = None
                    if logger:
                        logger.warning(
                            "telegram.history.disable_scrolling",
                            extra={
                                "round": _round,
                                "failed_scroll_sel": failed_sel,
                            },
                        )
            await asyncio.sleep(1.2)

        if logger:
            logger.info("telegram.history.extract_done", extra={"inserted_total": inserted_total})
        return inserted_total


