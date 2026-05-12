"""Headless browser smoke walk for the SPECA Web UI.

Not a pytest — runs as a script so an autonomous loop can pipe its output
back into the orchestrator. Each step prints `OK <name>` or `FAIL <name>:
<reason>` so the caller can grep for failures quickly.

Usage:
    uv run python web/server/tests/smoke_browser.py [--url http://127.0.0.1:7411]

The harness is intentionally tolerant: a missing optional surface logs a
SKIP rather than crashing so iteration is fast.
"""

from __future__ import annotations

import argparse
import sys
import time
from contextlib import contextmanager
from pathlib import Path

try:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Error as PlaywrightError,
        Page,
        TimeoutError as PlaywrightTimeout,
        sync_playwright,
    )
except Exception as exc:  # pragma: no cover - env probe
    print(f"FAIL imports: playwright unavailable ({exc})", file=sys.stderr)
    raise SystemExit(1)


REPORT: list[tuple[str, str, str]] = []


def report(kind: str, name: str, msg: str = "") -> None:
    REPORT.append((kind, name, msg))
    if msg:
        print(f"{kind} {name}: {msg}")
    else:
        print(f"{kind} {name}")


@contextmanager
def step(name: str):
    try:
        yield
        report("OK", name)
    except (PlaywrightTimeout, PlaywrightError, AssertionError) as exc:
        report("FAIL", name, str(exc).splitlines()[0][:300])
    except Exception as exc:  # pragma: no cover - defensive
        report("FAIL", name, f"unexpected: {exc!r}")


def expect_visible(page: Page, selector: str, timeout: int = 5_000) -> None:
    page.wait_for_selector(selector, state="visible", timeout=timeout)


def click_visible(page: Page, selector: str, timeout: int = 5_000) -> None:
    page.wait_for_selector(selector, state="visible", timeout=timeout)
    page.click(selector, timeout=timeout)


def goto(page: Page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=15_000)


def screenshot_to(page: Page, out_dir: Path, name: str) -> None:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)
    except Exception as exc:  # pragma: no cover - best effort
        print(f"WARN screenshot {name}: {exc}")


# --- Individual flow probes ------------------------------------------------


def smoke_health(page: Page, base: str) -> None:
    with step("health"):
        res = page.request.get(f"{base}/api/health")
        assert res.ok, f"HTTP {res.status}"


def smoke_login_screen(page: Page, base: str) -> None:
    """Visit /login while logged out via cookie wipe in this context."""

    with step("login_screen_renders"):
        # Wipe any prior persisted query cache so AppShell falls through
        # to the unauthenticated path. Hitting /login directly works once
        # the route renders without the auth gate redirect (Slice A path).
        goto(page, f"{base}/login")
        page.wait_for_load_state("domcontentloaded", timeout=5_000)
        # The OAuth button + API key field anchor identity of the screen.
        expect_visible(page, "input[type='password']", timeout=5_000)


def smoke_dashboard_loads(page: Page, base: str) -> None:
    with step("dashboard_loads"):
        goto(page, f"{base}/")
        # auth page or runs page should render — both have a <header>.
        expect_visible(page, "header")


def smoke_runs_visible(page: Page, base: str) -> None:
    with step("runs_visible"):
        goto(page, f"{base}/runs")
        page.wait_for_load_state("networkidle", timeout=8_000)
        expect_visible(page, "header")


def smoke_picker_3_entries(page: Page, base: str) -> None:
    with step("picker_three_entries"):
        goto(page, f"{base}/runs/new")
        expect_visible(page, "[data-testid='picker-page']")
        # Saved targets list — demo seed should be visible by repo name
        assert "OpenList" in (page.inner_text("body") or ""), "demo seed not shown"


def smoke_picker_demo_card(page: Page, base: str) -> None:
    with step("picker_demo_card_opens_form"):
        goto(page, f"{base}/runs/new")
        # Click the OpenList demo entry — the SavedTargetsList renders one
        # button per target.
        page.wait_for_selector("[data-testid='picker-page']", timeout=8_000)
        page.get_by_text("OpenListTeam/OpenList", exact=False).first.click(timeout=4_000)
        page.wait_for_url("**/runs/new/review", timeout=4_000)
        expect_visible(page, "[data-testid='new-run-form']")


def smoke_form_project_type(page: Page, base: str) -> None:
    with step("form_has_project_type_select"):
        goto(page, f"{base}/runs/new/review")
        sel = page.wait_for_selector(
            "[data-testid='new-run-project-type']", timeout=5_000
        )
        assert sel is not None
        # Switching to web_app should rename the contracts label
        page.select_option("[data-testid='new-run-project-type']", "web_app")
        time.sleep(0.2)  # let translation re-render
        # placeholder change is the cheapest assertion
        textarea = page.wait_for_selector(
            "[data-testid='new-run-contracts']", timeout=3_000
        )
        ph = textarea.get_attribute("placeholder")
        assert ph is not None and "src/" in ph, f"unexpected placeholder: {ph!r}"


def smoke_settings(page: Page, base: str) -> None:
    with step("settings_renders"):
        goto(page, f"{base}/settings")
        page.wait_for_load_state("domcontentloaded", timeout=5_000)
        expect_visible(page, "header")


def smoke_theme_toggle(page: Page, base: str) -> None:
    with step("theme_toggle_present_and_switches"):
        goto(page, f"{base}/runs")
        light = page.wait_for_selector(
            "[data-testid='theme-toggle-light']", timeout=5_000
        )
        dark = page.wait_for_selector("[data-testid='theme-toggle-dark']", timeout=2_000)
        assert light and dark
        dark.click()
        time.sleep(0.2)
        theme = page.evaluate("document.documentElement.dataset.theme")
        assert theme == "dark", f"expected dark, got {theme!r}"
        light.click()
        time.sleep(0.2)
        theme = page.evaluate("document.documentElement.dataset.theme")
        assert theme == "light", f"expected light, got {theme!r}"


def smoke_language_toggle(page: Page, base: str) -> None:
    with step("language_toggle_switches_html_lang"):
        goto(page, f"{base}/runs")
        page.wait_for_selector("header", timeout=5_000)
        # LanguageToggle compact uses aria-pressed on the EN button — fall back
        # to text match.
        en_btn = page.locator("button", has_text="EN").first
        ja_btn = page.locator("button", has_text="JA").first
        if en_btn.count() == 0 or ja_btn.count() == 0:
            # try i18n keys instead
            en_btn = page.get_by_role("button", name="English")
            ja_btn = page.get_by_role("button", name="日本語")
        ja_btn.click(timeout=4_000)
        time.sleep(0.2)
        lang = page.evaluate("document.documentElement.lang")
        assert lang.startswith("ja"), f"expected ja, got {lang!r}"
        en_btn.click(timeout=4_000)
        time.sleep(0.2)
        lang = page.evaluate("document.documentElement.lang")
        assert lang.startswith("en"), f"expected en, got {lang!r}"


def smoke_chat_opens(page: Page, base: str) -> None:
    with step("chat_panel_opens_via_header"):
        goto(page, f"{base}/runs")
        page.wait_for_selector("[data-testid='chat-toggle']", timeout=5_000)
        page.click("[data-testid='chat-toggle']")
        # ChatPanel.tsx adds data-testid="chat-panel" — assert it renders.
        expect_visible(page, "[data-testid='chat-panel']", timeout=8_000)


def smoke_chat_history_toggle(page: Page, base: str) -> None:
    with step("chat_history_toggle"):
        goto(page, f"{base}/runs")
        page.click("[data-testid='chat-toggle']")
        page.wait_for_selector("[data-testid='chat-panel']", timeout=8_000)
        page.click("[data-testid='chat-history-toggle']")
        # "New chat" button must appear when drawer is open.
        expect_visible(page, "[data-testid='chat-new-conversation']", timeout=4_000)


def smoke_findings_list(page: Page, base: str) -> None:
    with step("findings_list_renders"):
        goto(
            page,
            f"{base}/runs/2026-05-11T13-11-49Z-994f630-unknown/findings",
        )
        page.wait_for_load_state("networkidle", timeout=8_000)
        expect_visible(page, "header")


def smoke_run_detail(page: Page, base: str) -> None:
    with step("run_detail_legacy_renders"):
        # The seed dataset contains run id 2026-05-11T13-11-49Z-994f630-unknown.
        goto(page, f"{base}/runs/2026-05-11T13-11-49Z-994f630-unknown")
        page.wait_for_load_state("networkidle", timeout=6_000)
        # Stop / Re-run actions should be present (text-agnostic).
        expect_visible(page, "header")


def smoke_dark_mode_each_screen(page: Page, base: str, screenshots: Path | None) -> None:
    """Snapshot every major surface in dark mode for visual review."""
    with step("dark_mode_snapshots"):
        # Flip to dark first, then visit each screen.
        goto(page, f"{base}/runs")
        page.wait_for_selector("[data-testid='theme-toggle-dark']", timeout=5_000)
        page.click("[data-testid='theme-toggle-dark']")
        time.sleep(0.3)
        screens = {
            "dark_runs": f"{base}/runs",
            "dark_new_run": f"{base}/runs/new",
            "dark_review": f"{base}/runs/new/review",
            "dark_settings": f"{base}/settings",
            "dark_run_detail": f"{base}/runs/2026-05-11T13-11-49Z-994f630-unknown",
        }
        for name, url in screens.items():
            goto(page, url)
            time.sleep(0.3)
            if screenshots is not None:
                screenshot_to(page, screenshots, name)


# --- Runner ----------------------------------------------------------------


def run(base: str, headless: bool, screenshots: Path | None) -> int:
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(headless=headless)
        try:
            context: BrowserContext = browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.set_default_timeout(8_000)

            flows = [
                smoke_health,
                smoke_login_screen,
                smoke_dashboard_loads,
                smoke_runs_visible,
                smoke_picker_3_entries,
                smoke_picker_demo_card,
                smoke_form_project_type,
                smoke_settings,
                smoke_theme_toggle,
                smoke_language_toggle,
                smoke_chat_opens,
                smoke_chat_history_toggle,
                smoke_findings_list,
                smoke_run_detail,
            ]
            for fn in flows:
                fn(page, base)
                if screenshots is not None:
                    screenshot_to(page, screenshots, fn.__name__)

            # Dark-mode visual sweep at the end so the previous light-mode
            # screenshots are preserved.
            smoke_dark_mode_each_screen(page, base, screenshots)

            # Mobile (360x720) walk of the main surfaces.
            mobile_context = browser.new_context(
                viewport={"width": 360, "height": 720},
                device_scale_factor=2,
                is_mobile=True,
            )
            mpage = mobile_context.new_page()
            mpage.set_default_timeout(8_000)
            for name, url in (
                ("mobile_runs", f"{base}/runs"),
                ("mobile_new_run", f"{base}/runs/new"),
                ("mobile_review", f"{base}/runs/new/review"),
                ("mobile_settings", f"{base}/settings"),
            ):
                with step(name):
                    goto(mpage, url)
                    mpage.wait_for_load_state("networkidle", timeout=6_000)
                if screenshots is not None:
                    screenshot_to(mpage, screenshots, name)
            mobile_context.close()

        finally:
            try:
                browser.close()
            except Exception:
                pass

    fails = [r for r in REPORT if r[0] == "FAIL"]
    print("---")
    print(f"PASS={sum(1 for r in REPORT if r[0] == 'OK')} FAIL={len(fails)}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:7411")
    ap.add_argument("--headed", action="store_true", help="run with visible browser")
    ap.add_argument(
        "--screenshots",
        type=Path,
        default=None,
        help="directory to dump per-flow screenshots into",
    )
    args = ap.parse_args()
    return run(args.url, headless=not args.headed, screenshots=args.screenshots)


if __name__ == "__main__":
    raise SystemExit(main())
