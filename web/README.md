# SPECA Web UI

Local web client for the SPECA audit pipeline. Two processes during
development (Python backend + Vite dev server), one process in production
(backend serves the built bundle from `web/frontend/dist`).

## Dev mode (two terminals)

```bash
# Terminal 1 — backend on http://127.0.0.1:7411
uv sync
uv run speca-web --port 7411 --no-open-browser

# Terminal 2 — Vite dev server with HMR on http://127.0.0.1:5173
# (proxies /api/* to the backend)
cd web/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in a browser.

## Production-like single-process mode

```bash
cd web/frontend
npm install
npm run build              # produces web/frontend/dist
cd ../..
uv run speca-web --port 7411 --serve-frontend
```

Open `http://127.0.0.1:7411`. The backend serves the SPA from
`web/frontend/dist` and exposes the API at `/api/*`. With
`--serve-frontend` (the default unless you pass `--no-open-browser`) the
backend opens the URL in your default browser on startup.

## First login

Open `/login` and paste an Anthropic API key (`sk-ant-...`). The key is
persisted to `~/.claude/credentials.json` alongside any Claude Code CLI
credentials — your existing CLI login is preserved.

If `~/.claude/credentials.json` already carries an `apiKey` or
`claudeAiOauth` block (you have logged in via the Claude Code CLI), the
SPA detects it on boot and skips the login screen.

## Pages (v0)

| Route | What it shows |
|---|---|
| `/login` | Anthropic API key entry. OAuth (claude.ai) is stubbed for v1. |
| `/runs` | List of `.speca/runs/<id>/manifest.json` summaries (newest first). |
| `/runs/<id>` | Per-phase status + duration, "Open in VSCode" entry points. |
| `/runs/<id>/findings` | Phase 03 / 04 findings table, severity / verdict / phase filters. |
| `/runs/<id>/findings/<property_id>` | One finding's evidence / proof trace / gates. |
| `/settings` | Auth + `code`/`gh` integration status + maintenance links into VSCode. |

The chat panel (top-right "Chat" button in the app shell) is read-only:
only `read_run_status`, `list_findings`, `read_finding` are dispatched.
A forged `launch_pipeline` (or any non-allow-listed tool name) is blocked
server-side with a structured `tool_not_allowed` event.

## Test

```bash
# Backend
uv run pytest web/server/tests -v

# Frontend type-check + build
cd web/frontend && npm run build
```

Both must pass before any web slice lands. The backend suite covers
`/api/health`, the lenient findings loader, the empty-runs response, and
the integrations status / paths contract; the chat surface has its own
read-only guard regression in `test_chat_readonly_guard.py`.

## Layout

```
web/
  server/         FastAPI backend (Python)
    main.py       app factory + router anchors
    cli.py        speca-web entrypoint
    config.py     path resolution (SPECA_REPO_ROOT, SPECA_RUNS_DIR, ...)
    routers/      per-feature HTTP routers (auth, runs, findings,
                  integrations, chat, picker)
    services/     business logic (run_index, finding_loader, ...)
    schemas/      Pydantic request / response models
    tests/        pytest suite for the backend
  frontend/       Vite + React 19 + TypeScript SPA
    src/
      components/ reusable UI primitives (AppShell, Header, OpenInVSCode, ...)
      features/   feature-scoped state and pages
        auth/        login screen + status query
        runs/        run list + detail (phase rows)
        findings/    findings list + detail
        integrations/ <OpenInVSCode> integrations + paths query
        chat/        right-side chat panel (lazy-mounted)
        picker/      saved targets (Slice F)
        settings/    Settings page (Slice G)
      lib/        framework-agnostic helpers (api.ts, ...)
      styles/     global CSS + Nyx token mirror
```
