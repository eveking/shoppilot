"""ORM 模型。

遵循统一公共字段约定：id, created_by, updated_by, created_at, updated_at。
时间统一使用 UTC。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class PublicFieldsMixin:
    """统一公共字段（中间表除外）。"""

    created_by: Mapped[str] = mapped_column(String(64), default="")
    updated_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ChatSession(Base, PublicFieldsMixin):
    """一次多轮对话会话，绑定已验证的用户身份。"""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    # 最近一次追加消息的时间（会话列表排序依据，ADR-0011）；新建会话为 NULL
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChatSession id={self.id} user_id={self.user_id}>"


class ChatMessage(Base, PublicFieldsMixin):
    """会话内的一条消息（用户/助手/工具结果）。"""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_created", "session_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    # user / assistant / tool
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # assistant 中间消息携带的工具调用（JSON 数组）
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)
    # role=tool 时的回填字段
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
