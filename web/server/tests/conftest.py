"""Shared pytest fixtures for the SPECA web backend test suite.

The fixtures here are intentionally small — every test that needs an HTTP
client gets a fresh :class:`fastapi.testclient.TestClient` so that one test
mutating state (env vars, cached snapshots) cannot bleed into the next.

Notes:

* :func:`client` builds the app via :func:`web.server.main.create_app` so
  the wiring under test matches production (all routers included).
* The credentials probe in ``get_status`` reads ``~/.claude/.credentials.json``
  (with leading dot, where the claude CLI persists its OAuth blob) and falls
  back to the legacy dot-less path — that read tolerates a missing file, so
  tests do *not* have to mock it unless they specifically assert on the
  ``logged_in`` value.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from web.server.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Yield a fresh :class:`TestClient` for one test.

    ``TestClient`` is itself a context manager (FastAPI uses it to trigger
    startup / shutdown events) so we yield from a ``with`` block. The app
    instance is rebuilt per test so a router-level state mutation in one
    test cannot bleed into another.
    """

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
