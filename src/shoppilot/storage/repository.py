"""会话与消息的数据访问。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shoppilot.storage.models import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def create_session(self, user_id: str) -> ChatSession:
        async with self._factory() as db:
            row = ChatSession(user_id=user_id, created_by=user_id, updated_by=user_id)
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row

    async def get_session(self, session_id: str) -> ChatSession | None:
        async with self._factory() as db:
            return await db.get(ChatSession, session_id)

    async def append_message(
        self,
        session_id: str,
        *,
        actor: str,
        role: str,
        content: str | None = None,
        tool_calls: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> ChatMessage:
        async with self._factory() as db:
            row = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                created_by=actor,
                updated_by=actor,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row

    async def list_messages(self, session_id: str) -> list[ChatMessage]:
        async with self._factory() as db:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            )
            return list(result.scalars().all())
