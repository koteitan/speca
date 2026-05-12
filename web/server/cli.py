"""``speca-web`` console entrypoint.

Run the FastAPI backend with uvicorn, optionally serving the built frontend
bundle from ``web/frontend/dist`` so the whole UI is reachable on a single
port. The CLI is intentionally argparse-only (no third-party CLI lib) to keep
the dependency footprint small.
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Sequence

import uvicorn
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from .config import SPECA_REPO_ROOT
from .main import app as fastapi_app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7411

FRONTEND_DIST = SPECA_REPO_ROOT / "web" / "frontend" / "dist"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="speca-web",
        description="Run the SPECA local web UI backend.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=(
            "Interface to bind. Defaults to 127.0.0.1 — do not change this "
            "unless you understand the implications of exposing the backend "
            "beyond localhost."
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port to listen on (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--serve-frontend",
        action="store_true",
        help=(
            "Mount web/frontend/dist as static files on /. "
            "Run `cd web/frontend && npm run build` first."
        ),
    )
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Skip launching the default browser at startup.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (dev only).",
    )
    return parser


def _mount_frontend(dist: Path) -> None:
    """Attach the built SPA to the FastAPI app.

    Mounting at ``/`` with ``html=True`` makes uvicorn serve ``index.html`` for
    bare directory requests, but we still need a SPA fallback so client-side
    routes (e.g. ``/runs/abc``) return ``index.html`` instead of 404.
    """

    index_html = dist / "index.html"
    fastapi_app.mount(
        "/assets",
        StaticFiles(directory=str(dist / "assets"), check_dir=False),
        name="assets",
    )

    @fastapi_app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:  # noqa: ARG001
        # ``/api/*`` is registered first, so FastAPI's router precedence
        # already routes API calls correctly. Everything else hands back the
        # SPA shell so React Router can take over.
        return FileResponse(index_html)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.serve_frontend:
        index_html = FRONTEND_DIST / "index.html"
        if not index_html.is_file():
            print(
                "speca-web: --serve-frontend was given but "
                f"{index_html} is missing. "
                "Run `cd web/frontend && npm run build` first.",
                file=sys.stderr,
            )
            return 2
        _mount_frontend(FRONTEND_DIST)

    if not args.no_open_browser:
        url = f"http://{args.host}:{args.port}"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "web.server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
