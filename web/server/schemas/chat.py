"""Pydantic schemas for the Chat API.

The wire shape mirrors Anthropic's ``messages`` content blocks closely so a
single ``ChatMessage`` can hold either:

* a plain string (legacy / user input shortcut), or
* a ``list[dict]`` of content blocks: text, tool_use, tool_result, etc.

Conversation files on disk (``~/.speca/web/conversations/<id>.json``) use the
same shape — no separate persistence schema — so reads and writes are trivial
``model_dump`` / ``model_validate`` calls.

We deliberately keep ``content`` permissive (``list[dict] | str``) because the
SDK occasionally introduces new block types (e.g. citations) that we want to
round-trip without a schema bump.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Role = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    """One message in a conversation.

    ``content`` is intentionally typed loosely: the SDK may yield blocks
    we don't recognise yet and storing them verbatim keeps history
    forward-compatible. The frontend / chat_runtime is responsible for
    parsing the structured shape.
    """

    model_config = ConfigDict(extra="allow")

    role: Role
    content: list[dict] | str
    timestamp: datetime


class Conversation(BaseModel):
    """Persistent conversation file body.

    ``conversation_id`` is supplied by the client (UUID v4) and used as the
    on-disk filename. ``last_message_at`` is refreshed on every append so the
    list endpoint can sort by recency without scanning ``messages``.
    """

    model_config = ConfigDict(extra="allow")

    conversation_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime
    last_message_at: datetime


class ConversationSummary(BaseModel):
    """One row in ``GET /api/chat/conversations``."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    last_message_at: datetime
    title: str | None = None


class PostMessageRequest(BaseModel):
    """Request body for ``POST /api/chat/conversations/<id>/messages``."""

    model_config = ConfigDict(extra="forbid")

    text: str


# --- Slice C1 + C2: side-effect tool approval gate --------------------------


ApprovalAction = Literal["approve", "edit", "cancel"]


class ToolApprovalRequest(BaseModel):
    """Body for ``POST /api/chat/tool_approve``.

    ``conversation_id`` + ``tool_call_id`` together identify the pending
    approval registered by the chat runtime. ``edited_input`` is only
    meaningful when ``action="edit"`` — the runtime falls back to the
    model's original snapshot otherwise.
    """

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    tool_call_id: str
    action: ApprovalAction
    edited_input: dict | None = None


class ToolApprovalResponse(BaseModel):
    """Body returned by ``POST /api/chat/tool_approve``."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
