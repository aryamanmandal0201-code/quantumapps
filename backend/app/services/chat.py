"""Stored chat history, always scoped to one user."""
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import ChatMessage

HISTORY_FOR_MODEL = 10  # recent messages sent to the LLM as context
HISTORY_FOR_UI = 50


def list_messages(db: Session, user_id: int, limit: int = HISTORY_FOR_UI) -> list[ChatMessage]:
    """The user's latest messages, oldest first."""
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.user_id == user_id).order_by(ChatMessage.id.desc()).limit(limit)
    ).all()
    return list(reversed(rows))


def recent_history_for_model(db: Session, user_id: int) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in list_messages(db, user_id, HISTORY_FOR_MODEL)]


def save_exchange(db: Session, user_id: int, message: str, reply: str, tool_calls: list[dict[str, Any]]) -> None:
    db.add(ChatMessage(user_id=user_id, role="user", content=message))
    db.add(ChatMessage(user_id=user_id, role="assistant", content=reply, tool_calls=tool_calls))
    db.commit()


def clear_history(db: Session, user_id: int) -> None:
    db.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
    db.commit()
