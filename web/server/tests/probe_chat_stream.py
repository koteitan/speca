"""Targeted Playwright probe for chat SSE streaming.

Verifies the chat panel reaches an *actual assistant reply* (the previous
auth bug — wrong credentials.json path — let the request fail silently with
"Could not resolve authentication method"). Not part of the 32-flow smoke
walk because it requires:

* claude.ai OAuth credentials at ~/.claude/.credentials.json (dot-prefix)
* available concurrent quota on the user's subscription

Prints OK/FAIL lines so the harness output is greppable.

Usage:
    uv run python web/server/tests/probe_chat_stream.py [--url http://127.0.0.1:7411]
"""

from __future__ import annotations

import argparse
import io
import sys
import time

# Console on Windows defaults to cp932; force UTF-8 so em-dashes and
# other non-ASCII bytes in surfaced error messages don't crash the probe.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeout,
        sync_playwright,
    )
except Exception as exc:  # pragma: no cover - env probe
    print(f"FAIL imports: playwright unavailable ({exc})", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7411")
    parser.add_argument("--prompt", default="Reply with the single word PONG. No punctuation, no quotes, no explanation.")
    parser.add_argument("--needle", default="PONG")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    fails: list[str] = []

    def ok(name: str, msg: str = "") -> None:
        print(f"OK {name}{f': {msg}' if msg else ''}")

    def fail(name: str, msg: str) -> None:
        print(f"FAIL {name}: {msg}")
        fails.append(name)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Force en-US so Send button text matches "Send" — but we use the
        # locale-independent `button[type='submit']` selector anyway.
        context = browser.new_context(locale="en-US")
        page = context.new_page()

        try:
            page.goto(f"{args.url}/runs", wait_until="domcontentloaded", timeout=15_000)
            # Force English in localStorage so the panel labels are stable.
            page.evaluate(
                "() => { try { localStorage.setItem('i18nextLng', 'en'); } catch(e) {} }"
            )
            page.reload(wait_until="domcontentloaded", timeout=15_000)
            ok("dashboard_loads")
        except Exception as exc:
            fail("dashboard_loads", str(exc).splitlines()[0])
            return 1

        try:
            page.click("[data-testid='chat-toggle']", timeout=5_000)
            page.wait_for_selector("[data-testid='chat-panel']", timeout=8_000)
            ok("chat_panel_opens")
        except Exception as exc:
            fail("chat_panel_opens", str(exc).splitlines()[0])
            return 1

        # Count existing assistant bubbles so we can detect the new one.
        try:
            existing_before = page.locator("[data-testid='bubble-assistant']").count()
        except Exception:
            existing_before = 0

        try:
            ta = page.locator("[data-testid='chat-panel'] textarea").first
            ta.fill(args.prompt)
            page.locator("[data-testid='chat-panel'] button[type='submit']").first.click(timeout=5_000)
            ok("send_clicked")
        except Exception as exc:
            fail("send_clicked", str(exc).splitlines()[0])
            return 1

        # User message bubble must render right away.
        try:
            page.wait_for_function(
                "n => document.querySelectorAll(\"[data-testid='bubble-user']\").length > n",
                arg=0,
                timeout=5_000,
            )
            ok("user_bubble_renders")
        except Exception as exc:
            fail("user_bubble_renders", str(exc).splitlines()[0][:200])

        # Assistant SSE stream — poll for either non-empty assistant text or
        # a visible error message. Both branches checked every tick so an
        # empty streaming draft doesn't starve the error path.
        deadline = time.monotonic() + args.timeout
        assistant_text = ""
        last_error_text = ""
        saw_assistant = False
        while time.monotonic() < deadline:
            try:
                count = page.locator("[data-testid='bubble-assistant']").count()
            except Exception:
                count = existing_before
            if count > existing_before:
                try:
                    assistant_text = page.locator(
                        "[data-testid='bubble-assistant']"
                    ).nth(count - 1).inner_text(timeout=1_000)
                except PlaywrightTimeout:
                    assistant_text = ""
                if assistant_text.strip():
                    saw_assistant = True
                    break

            try:
                last_error_text = page.evaluate(
                    "() => {"
                    "  const panel = document.querySelector(\"[data-testid='chat-panel']\");"
                    "  if (!panel) return '';"
                    "  const candidates = panel.querySelectorAll('[role=\"alert\"], [class*=\"error\" i]');"
                    "  for (const c of candidates) {"
                    "    const t = (c.textContent || '').trim();"
                    "    if (t) return t;"
                    "  }"
                    "  return '';"
                    "}"
                )
            except Exception:
                last_error_text = ""
            if last_error_text:
                break
            time.sleep(0.5)

        if not saw_assistant and not last_error_text:
            # Dump panel HTML to diagnose if neither branch fired.
            try:
                dump = page.evaluate(
                    "() => document.querySelector(\"[data-testid='chat-panel']\")?.outerHTML?.slice(0, 1500) ?? ''"
                )
                print(f"DEBUG panel_html: {dump}")
            except Exception:
                pass

        if saw_assistant:
            if args.needle.lower() in assistant_text.lower():
                ok("assistant_streams_content", f"got {args.needle!r} in reply ({len(assistant_text)} chars)")
            else:
                ok(
                    "assistant_streams_content",
                    f"reply present but no {args.needle!r}: {assistant_text[:120]!r}",
                )
        elif last_error_text:
            fail("assistant_streams_content", f"backend error surfaced: {last_error_text[:200]!r}")
        else:
            fail(
                "assistant_streams_content",
                f"no assistant bubble within {args.timeout}s and no error rendered",
            )

        # History drawer should still work after a send.
        try:
            page.click("[data-testid='chat-history-toggle']", timeout=3_000)
            page.wait_for_selector("[data-testid='chat-new-conversation']", timeout=3_000)
            ok("history_drawer_opens_after_send")
        except Exception as exc:
            fail("history_drawer_opens_after_send", str(exc).splitlines()[0])

        # New-chat clears the panel back to an empty conversation.
        try:
            page.click("[data-testid='chat-new-conversation']", timeout=3_000)
            page.wait_for_function(
                "() => document.querySelectorAll(\"[data-testid='bubble-user']\").length === 0",
                timeout=4_000,
            )
            ok("new_conversation_clears_panel")
        except Exception as exc:
            fail("new_conversation_clears_panel", str(exc).splitlines()[0][:200])

        # Esc closes chat panel (global shortcut).
        try:
            page.keyboard.press("Escape")
            page.wait_for_selector("[data-testid='chat-panel']", state="detached", timeout=3_000)
            ok("esc_closes_panel")
        except Exception as exc:
            fail("esc_closes_panel", str(exc).splitlines()[0])

        # `c` shortcut re-opens it.
        try:
            page.keyboard.press("c")
            page.wait_for_selector("[data-testid='chat-panel']", timeout=3_000)
            ok("c_shortcut_reopens_panel")
        except Exception as exc:
            fail("c_shortcut_reopens_panel", str(exc).splitlines()[0])

        # `?` opens help modal even with chat focus.
        try:
            page.keyboard.press("?")
            page.wait_for_selector("[role='dialog']", timeout=3_000)
            ok("question_opens_help_modal")
            page.keyboard.press("Escape")
        except Exception as exc:
            fail("question_opens_help_modal", str(exc).splitlines()[0])

        browser.close()

    print(f"--- PASS={'assistant_streams_content not in failures' if 'assistant_streams_content' not in fails else 'see failures'}")
    print(f"--- FAIL={len(fails)} ({', '.join(fails) if fails else 'none'})")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
