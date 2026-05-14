"""Pydantic schemas for the auth router.

These models intentionally never expose the raw API key or OAuth tokens to the
frontend — :class:`AuthStatus` only carries booleans / display-friendly
identity strings. The credentials material itself stays on disk under
``~/.claude/credentials.json`` and is only ever read by the backend.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class AuthStatus(BaseModel):
    """Login state surfaced to the SPA.

    ``method`` is ``None`` when the user is not logged in. ``identity`` is a
    human-readable label (e.g. an OAuth email) that the UI can show next to a
    "logged in as" banner — it is **never** the raw key. For API key auth we
    leave it ``None`` rather than echoing back any portion of the key.
    """

    model_config = ConfigDict(extra="forbid")

    logged_in: bool
    method: Literal["oauth", "api_key"] | None = None
    identity: str | None = None


class ApiKeyRequest(BaseModel):
    """Body of ``POST /api/auth/api-key``.

    The validator is intentionally lenient: it only emits a warning when the
    prefix is not ``sk-ant-``. That keeps fake test keys usable in dev/CI
    while still helping the user notice an obvious paste mistake.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)

    @field_validator("key")
    @classmethod
    def _warn_on_unexpected_prefix(cls, value: str) -> str:
        if not value.startswith("sk-ant-"):
            logger.warning(
                "auth.api_key prefix does not look like an Anthropic key "
                "(expected 'sk-ant-' prefix). Accepting anyway."
            )
        return value
