"""On-disk store for chat conversations.

Each conversation is a single JSON file under ``~/.speca/web/conversations/``
named ``<conversation_id>.json``. The client owns the UUID — we never mint one
server-side — so the same client can issue a follow-up POST with the same
URL and we'll just append.

All writes are atomic (``tempfile.mkstemp`` + :func:`os.replace`) so a crash
mid-write cannot corrupt history; the worst case is the old version of the
file remaining on disk.

The module is deliberately thin — no caching, no in-memory store. Each request
re-reads the file. For v0 with single-user localhost we don't need more.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from web.server.schemas.chat import ChatMessage, Conversation, ConversationSummary

logger = logging.getLogger(__name__)


# UUID v4-ish guard — we accept any version of UUID and also tolerate test
# fixtures using simple hyphen-separated tokens (e.g. ``test-uuid-1``). The
# pattern blocks path traversal characters without forcing strict UUID form.
_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Per-user storage root. Resolved lazily so tests can monkeypatch the
# function (or pass an explicit path).
def conversations_dir() -> Path:
    """Return the on-disk directory where conversation files live."""

    return Path.home() / ".speca" / "web" / "conversations"


def _validate_conversation_id(conversation_id: str) -> None:
    if not _CONVERSATION_ID_RE.match(conversation_id):
        raise ValueError(
            f"invalid conversation_id: {conversation_id!r} "
            "(must match [A-Za-z0-9_-]{1,128})"
        )


def _conversation_path(conversation_id: str, base: Path | None = None) -> Path:
    _validate_conversation_id(conversation_id)
    root = base if base is not None else conversations_dir()
    return root / f"{conversation_id}.json"


def _atomic_write_json(path: Path, payload: dict) -> None:
    """Atomic write via mkstemp + :func:`os.replace`.

    The temp file is created in the same directory as the target so the
    final rename stays on a single filesystem (atomic on Windows NTFS and
    on POSIX). On exceptions we best-effort unlink the temp file so we
    never leak ``.tmp`` debris.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort
            pass
        raise


def load_conversation(
    conversation_id: str,
    *,
    base: Path | None = None,
) -> Conversation | None:
    """Load a conversation from disk. ``None`` if the file does not exist.

    Corrupt files are logged and treated as missing — for v0 a personal
    tool the kindest behaviour is to let the user start over rather than
    surface 500s.
    """

    path = _conversation_path(conversation_id, base=base)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("chat: read failed for %s (%s)", path, exc)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("chat: %s is not valid JSON (%s)", path, exc)
        return None

    try:
        return Conversation.model_validate(data)
    except ValidationError as exc:
        logger.warning("chat: schema mismatch in %s (%s)", path, exc)
        return None


def save_conversation(
    conversation: Conversation,
    *,
    base: Path | None = None,
) -> None:
    """Persist the conversation file atomically."""

    path = _conversation_path(conversation.conversation_id, base=base)
    _atomic_write_json(path, conversation.model_dump(mode="json"))


def ensure_conversation(
    conversation_id: str,
    *,
    base: Path | None = None,
) -> Conversation:
    """Return an existing conversation or create an empty one on disk.

    The created file is written immediately so a follow-up GET sees a
    consistent state even if the streaming POST fails partway through.
    """

    existing = load_conversation(conversation_id, base=base)
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc)
    conversation = Conversation(
        conversation_id=conversation_id,
        messages=[],
        created_at=now,
        last_message_at=now,
    )
    save_conversation(conversation, base=base)
    return conversation


def append_message(
    conversation: Conversation,
    *,
    role: str,
    content: list[dict] | str,
    base: Path | None = None,
) -> Conversation:
    """Append a message to the conversation and persist atomically.

    Returns the updated conversation so callers can chain ``append_message``
    without re-loading.
    """

    now = datetime.now(timezone.utc)
    message = ChatMessage(role=role, content=content, timestamp=now)  # type: ignore[arg-type]
    conversation.messages.append(message)
    conversation.last_message_at = now
    save_conversation(conversation, base=base)
    return conversation


def list_conversations(
    *,
    base: Path | None = None,
) -> list[ConversationSummary]:
    """List all conversation files newest-first.

    The title is derived from the first user message's text (truncated to
    80 chars). Files that fail to parse are silently skipped so a single
    corrupt file does not nuke the sidebar.
    """

    root = base if base is not None else conversations_dir()
    if not root.exists():
        return []

    summaries: list[ConversationSummary] = []
    for entry in root.iterdir():
        if not entry.is_file() or entry.suffix != ".json":
            continue
        conversation_id = entry.stem
        if not _CONVERSATION_ID_RE.match(conversation_id):
            continue
        convo = load_conversation(conversation_id, base=root)
        if convo is None:
            continue
        summaries.append(
            ConversationSummary(
                conversation_id=convo.conversation_id,
                last_message_at=convo.last_message_at,
                title=_derive_title(convo),
            )
        )

    summaries.sort(key=lambda s: s.last_message_at, reverse=True)
    return summaries


def _derive_title(conversation: Conversation) -> str | None:
    """Pick a short title from the first user message's text part."""

    for msg in conversation.messages:
        if msg.role != "user":
            continue
        if isinstance(msg.content, str):
            text = msg.content
        else:
            text = ""
            for block in msg.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text", ""))
                    break
        text = text.strip().splitlines()[0] if text.strip() else ""
        if text:
            return text[:80]
    return None
