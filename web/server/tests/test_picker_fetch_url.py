"""Slice B3: ``POST /api/picker/fetch_url`` end-to-end behaviour.

These tests exercise the **happy path** + every documented failure mode of
:mod:`web.server.services.bounty_scope` *without* hitting the Anthropic API.
We swap the module-level ``client_factory`` for a tiny fake that returns a
pre-canned ``Message`` (or raises), then drive the router via
:class:`fastapi.testclient.TestClient`.

What we are guarding against:

1. The router still validates request bodies (422 on missing URL).
2. A valid Anthropic answer round-trips into the documented schema.
3. A malformed Anthropic answer downgrades to a populated ``notes`` field
   (not a 500) — this is the v0 "best-effort" contract.
4. A missing API key surfaces as a 503 with ``retryable=True``.
5. SDK-level exceptions also surface as a 503 (not a bare 500).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from web.server.services import bounty_scope


# --- Fake SDK plumbing ------------------------------------------------------


class _FakeContentBlock:
    """Stand-in for ``anthropic.types.TextBlock`` etc.

    The real SDK returns objects with ``.type`` / ``.text`` attributes; our
    fake mimics that so :func:`bounty_scope._collect_text_from_message` does
    not need a dict-path branch in production.
    """

    def __init__(self, *, type: str, text: str | None = None) -> None:
        self.type = type
        self.text = text


class _FakeMessage:
    def __init__(self, content: list[_FakeContentBlock]) -> None:
        self.content = content
        self.stop_reason = "end_turn"


class _FakeMessages:
    def __init__(self, response: Any) -> None:
        # ``response`` may be a _FakeMessage or an exception instance.
        self._response = response
        self.last_kwargs: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.last_kwargs = kwargs
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


class _FakeClient:
    def __init__(self, response: Any) -> None:
        self.messages = _FakeMessages(response)


@pytest.fixture
def fake_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point :mod:`bounty_scope` at a tmpdir credentials file with an API key.

    We also clear ``ANTHROPIC_API_KEY`` from the environment so that the
    file-path branch of ``_resolve_api_key`` is the one being exercised by
    every test that uses this fixture (the env-var branch is exercised
    explicitly in :func:`test_env_var_api_key_takes_precedence`).
    """

    creds = tmp_path / "credentials.json"
    creds.write_text(
        json.dumps({"apiKey": "sk-ant-test-fixture"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bounty_scope, "_CREDENTIALS_PATH", creds)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return creds


@pytest.fixture
def restore_client_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real client factory after each test that overrides it."""

    original = bounty_scope.client_factory
    monkeypatch.setattr(bounty_scope, "client_factory", original)


# --- Tests ------------------------------------------------------------------


def test_fetch_url_happy_path(
    client: TestClient,
    fake_credentials: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A well-formed Anthropic answer is returned as a 200 + clean schema."""

    body = json.dumps(
        {
            "program_url": "https://immunefi.com/bounty/example",
            "program_name": "Example Protocol",
            "in_scope_assets": [
                "https://github.com/example/protocol",
                "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            ],
            "in_scope_contracts": [
                {
                    "address": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    "network": "ethereum",
                    "name": "Vault",
                }
            ],
            "out_of_scope": ["testnet deployments"],
            "severity_ratings": "Immunefi v2.2",
            "reward_range": "$1k - $100k",
            "notes": "PoC required",
            "spec_urls": "https://docs.example.com/v1,https://docs.example.com/v2",
            "keywords": "vault,erc4626",
        }
    )
    response_text = (
        "Here is the scope I extracted:\n\n"
        "```json\n"
        f"{body}\n"
        "```\n"
    )

    monkeypatch.setattr(
        bounty_scope,
        "client_factory",
        lambda _key: _FakeClient(_FakeMessage([_FakeContentBlock(type="text", text=response_text)])),
    )

    resp = client.post(
        "/api/picker/fetch_url",
        json={"bug_bounty_url": "https://immunefi.com/bounty/example"},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["program_url"] == "https://immunefi.com/bounty/example"
    assert payload["program_name"] == "Example Protocol"
    assert "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" in payload["in_scope_assets"]
    assert payload["in_scope_contracts"] == [
        {
            "address": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "network": "ethereum",
            "name": "Vault",
        }
    ]
    assert payload["spec_urls"] == "https://docs.example.com/v1,https://docs.example.com/v2"
    assert payload["keywords"] == "vault,erc4626"
    assert payload["severity_ratings"] == "Immunefi v2.2"
    assert payload["reward_range"] == "$1k - $100k"
    assert payload["notes"] == "PoC required"


def test_fetch_url_invalid_json_falls_back_to_notes(
    client: TestClient,
    fake_credentials: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the model emits prose instead of JSON, we still 200 with notes filled."""

    response_text = (
        "I tried to read the page but the JSON I would have produced is "
        "incomplete. Sorry — please retry later."
    )

    monkeypatch.setattr(
        bounty_scope,
        "client_factory",
        lambda _key: _FakeClient(_FakeMessage([_FakeContentBlock(type="text", text=response_text)])),
    )

    resp = client.post(
        "/api/picker/fetch_url",
        json={"bug_bounty_url": "https://immunefi.com/bounty/example"},
    )
    assert resp.status_code == 200, resp.text

    payload = resp.json()
    assert payload["program_url"] == "https://immunefi.com/bounty/example"
    assert payload["notes"] == response_text
    # Defaults must still be present so the SPA's form bindings don't blow up.
    assert payload["in_scope_assets"] == []
    assert payload["in_scope_contracts"] == []
    assert payload["spec_urls"] == ""
    assert payload["keywords"] == ""


def test_fetch_url_anthropic_sdk_failure_is_503(
    client: TestClient,
    fake_credentials: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raised SDK exception bubbles up as a 503 ``anthropic_unreachable``."""

    monkeypatch.setattr(
        bounty_scope,
        "client_factory",
        lambda _key: _FakeClient(RuntimeError("connection reset by peer")),
    )

    resp = client.post(
        "/api/picker/fetch_url",
        json={"bug_bounty_url": "https://immunefi.com/bounty/example"},
    )
    assert resp.status_code == 503, resp.text

    detail = resp.json()["detail"]
    assert detail["error"] == "anthropic_unreachable"
    assert detail["retryable"] is True
    assert "connection reset" in detail["message"]


def test_fetch_url_missing_api_key_is_503(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env var and no credentials.json → 503 with OAuth-mode hint."""

    # Point at an empty tmpdir so the credentials file is absent.
    missing = tmp_path / "credentials.json"
    monkeypatch.setattr(bounty_scope, "_CREDENTIALS_PATH", missing)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # client_factory should NEVER be called when the key resolves to nothing,
    # so wire it to a hard failure to catch regressions.
    def _explode(_key: str) -> Any:  # pragma: no cover - guard
        raise AssertionError("client_factory was called despite no API key")

    monkeypatch.setattr(bounty_scope, "client_factory", _explode)

    resp = client.post(
        "/api/picker/fetch_url",
        json={"bug_bounty_url": "https://immunefi.com/bounty/example"},
    )
    assert resp.status_code == 503, resp.text

    detail = resp.json()["detail"]
    assert detail["error"] == "anthropic_unreachable"
    assert detail["retryable"] is True
    assert "OAuth-only" in detail["message"] or "API key" in detail["message"]


def test_fetch_url_validation_rejects_non_http_url(client: TestClient) -> None:
    """Pydantic ``HttpUrl`` rejects non-HTTP schemes before we burn an SDK call."""

    resp = client.post(
        "/api/picker/fetch_url",
        json={"bug_bounty_url": "ftp://example.com/scope"},
    )
    assert resp.status_code == 422


def test_fetch_url_validation_requires_bug_bounty_url(client: TestClient) -> None:
    """Missing required field → 422, not 500."""

    resp = client.post("/api/picker/fetch_url", json={})
    assert resp.status_code == 422


def test_env_var_api_key_takes_precedence(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``ANTHROPIC_API_KEY`` env var wins over ``~/.claude/credentials.json``."""

    creds = tmp_path / "credentials.json"
    creds.write_text(json.dumps({"apiKey": "sk-ant-from-file"}), encoding="utf-8")
    monkeypatch.setattr(bounty_scope, "_CREDENTIALS_PATH", creds)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")

    seen_keys: list[str] = []

    def _factory(key: str) -> _FakeClient:
        seen_keys.append(key)
        return _FakeClient(
            _FakeMessage(
                [
                    _FakeContentBlock(
                        type="text",
                        text='```json\n{"program_url": "https://x", "spec_urls": "", "keywords": ""}\n```',
                    )
                ]
            )
        )

    monkeypatch.setattr(bounty_scope, "client_factory", _factory)

    resp = client.post(
        "/api/picker/fetch_url",
        json={"bug_bounty_url": "https://immunefi.com/bounty/example"},
    )
    assert resp.status_code == 200, resp.text
    assert seen_keys == ["sk-ant-from-env"]


def test_contract_addresses_are_forwarded_into_prompt(
    client: TestClient,
    fake_credentials: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``contract_addresses`` from the request body lands in the prompt text."""

    captured: dict[str, Any] = {}

    def _factory(_key: str) -> _FakeClient:
        message = _FakeMessage(
            [
                _FakeContentBlock(
                    type="text",
                    text='```json\n{"program_url": "https://x", "spec_urls": "", "keywords": ""}\n```',
                )
            ]
        )
        fake = _FakeClient(message)
        # Hand back the messages object so we can inspect the prompt after
        # the request fires.
        captured["messages"] = fake.messages
        return fake

    monkeypatch.setattr(bounty_scope, "client_factory", _factory)

    resp = client.post(
        "/api/picker/fetch_url",
        json={
            "bug_bounty_url": "https://immunefi.com/bounty/example",
            "contract_addresses": "0xDEAD,0xBEEF",
        },
    )
    assert resp.status_code == 200, resp.text

    kwargs = captured["messages"].last_kwargs
    assert kwargs is not None
    user_msg = kwargs["messages"][0]
    assert user_msg["role"] == "user"
    assert "0xDEAD,0xBEEF" in user_msg["content"]

    # web_fetch + web_search tools must be registered.
    tool_types = {t["type"] for t in kwargs["tools"]}
    assert any(t.startswith("web_fetch_") for t in tool_types)
    assert any(t.startswith("web_search_") for t in tool_types)
