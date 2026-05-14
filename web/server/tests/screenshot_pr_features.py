"""Capture screenshots of the new batch-1 / batch-2 / batch-3 features for PR #62.

Not a regression test. Pipes one PNG per feature into ``docs/web-ui-
screenshots/`` so the PR body can reference them via raw github URLs.

Usage:
    uv run python web/server/tests/screenshot_pr_features.py [--url http://127.0.0.1:7411]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover
    print(f"FAIL imports: playwright unavailable ({exc})", file=sys.stderr)
    raise SystemExit(1)


OUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "web-ui-screenshots"


def shot(page, name: str, settle_selectors: list[str] | None = None) -> None:
    """Capture a full-page PNG.

    ``settle_selectors`` lets the caller wait for one of several markers
    that the page has loaded its real content before the shutter clicks —
    we hit this for the finding detail page which shows a "Loading…"
    state for a beat after navigation.
    """

    out = OUT_DIR / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if settle_selectors:
        for sel in settle_selectors:
            try:
                page.wait_for_selector(sel, timeout=4_000, state="visible")
                break
            except Exception:
                continue
    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except Exception:
        pass
    page.screenshot(path=str(out), full_page=True)
    print(f"OK  {name} -> {out.relative_to(out.parents[2])}")


def set_theme(page, mode: str) -> None:
    page.evaluate(
        "(m) => { try { localStorage.setItem('speca.theme', JSON.stringify({state:{mode:m},version:1})); } catch(e){} }",
        mode,
    )
    page.reload(wait_until="domcontentloaded", timeout=15_000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7411")
    args = parser.parse_args()
    base = args.url.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900}, locale="en-US")
        page = ctx.new_page()
        page.evaluate("() => { try { localStorage.setItem('i18nextLng', 'en'); } catch(e){} }")

        # 1) Dashboard — default (system) theme baseline
        page.goto(f"{base}/runs", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=8_000)
        shot(page, "01_dashboard_default")

        # 2) Solarized theme — same page in Solarized Dark
        set_theme(page, "solarized")
        page.goto(f"{base}/runs", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=8_000)
        shot(page, "02_solarized_dashboard")

        # Revert to light for the rest of the shots so colours are
        # legible in PRs viewed on default GitHub light theme.
        set_theme(page, "light")

        # 3) Findings list with filter DSL — open a seed run
        page.goto(f"{base}/runs", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=8_000)
        seed = page.evaluate(
            "() => document.querySelector('[data-testid^=\"run-row-\"] a')?.getAttribute('href') ?? null"
        )
        if seed:
            page.goto(f"{base}{seed}/findings", wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_load_state("networkidle", timeout=8_000)
            shot(page, "03_findings_list")

            # 4) Code highlighting — open a finding detail. The page
            # shows "Loading finding…" until the API returns, so we wait
            # for the actual code-path row before snapping.
            row = page.locator("[data-property-id] a").first
            if row.count() > 0:
                row.click()
                shot(
                    page,
                    "04_finding_detail_code_highlight",
                    settle_selectors=[
                        "[data-testid='finding-code-path']",
                        "pre[data-language]",
                    ],
                )

        # 5) Run detail with budget gauge + phase rows (keybinding hint)
        page.goto(f"{base}/runs", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=8_000)
        row = page.locator("[data-testid^='run-row-'] a").first
        if row.count() > 0:
            row.click()
            shot(
                page,
                "05_run_detail_budget_phases",
                settle_selectors=[
                    "[data-testid='run-detail-page']",
                    "[data-testid^='phase-row-']",
                ],
            )

            # 6) Budget cap-bump modal — click the gauge to open it
            btn = page.locator("[data-testid='budget-gauge-button']")
            if btn.count() > 0:
                btn.first.click()
                page.wait_for_selector("[data-testid='budget-cap-modal']", timeout=5_000)
                # Modal fades in over ~150ms — sleep past the animation so
                # the screenshot does not capture opacity:0 → invisible.
                page.wait_for_timeout(400)
                shot(page, "06_budget_cap_bump_modal")
                page.keyboard.press("Escape")

        # 7) Chat panel (without sending — just shows the empty composer)
        page.click("[data-testid='chat-toggle']")
        page.wait_for_selector("[data-testid='chat-panel']", timeout=8_000)
        shot(page, "07_chat_panel_empty")
        page.keyboard.press("Escape")

        # 8) Help modal (`?` shortcut)
        page.keyboard.press("?")
        page.wait_for_selector("[role='dialog']", timeout=5_000)
        page.wait_for_timeout(400)
        shot(page, "08_keyboard_shortcuts_help")
        page.keyboard.press("Escape")

        # 9) Settings page — theme toggle now has 4 buttons incl. Solarized
        page.goto(f"{base}/settings", wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_load_state("networkidle", timeout=8_000)
        shot(page, "09_settings_theme_4buttons")

        # 10) Login screen with the new paste-code OAuth surface.
        # Forces a fresh context so the user is logged out.
        ctx2 = browser.new_context(
            viewport={"width": 1400, "height": 900}, locale="en-US"
        )
        page2 = ctx2.new_page()
        page2.evaluate("() => { try { localStorage.setItem('i18nextLng', 'en'); } catch(e){} }")
        page2.goto(f"{base}/login", wait_until="domcontentloaded", timeout=15_000)
        page2.wait_for_load_state("networkidle", timeout=8_000)
        shot(page2, "10_login_paste_code")
        ctx2.close()

        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
