"""会话与消息的数据访问。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shoppilot.storage.models import ChatMessage, ChatSession, utcnow


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

    async def list_sessions(self, user_id: str, *, limit: int = 50) -> list[ChatSession]:
        """某用户的会话列表，按最近活跃倒序（NULL 视为最旧，ADR-0011）。"""
        async with self._factory() as db:
            result = await db.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(
                    ChatSession.last_message_at.is_(None),
                    ChatSession.last_message_at.desc(),
                    ChatSession.created_at.desc(),
                )
                .limit(limit)
            )
            return list(result.scalars().all())

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
            session_row = await db.get(ChatSession, session_id)
            if session_row is None:
                raise ValueError(f"会话不存在: {session_id}")
            now = utcnow()
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
            # 显式赋值，保证与 last_message_at 严格一致（可排序、可游标）
            row.created_at = now
            row.updated_at = now
            db.add(row)
            session_row.last_message_at = now
            await db.commit()
            await db.refresh(row)
            return row

    async def list_messages_page(
        self,
        session_id: str,
        *,
        limit: int = 50,
        before_id: str | None = None,
        include_tool: bool = False,
    ) -> tuple[list[ChatMessage], bool]:
        """游标分页取消息（ADR-0011）。

        取 before_id 指向消息之前的一页，按时间正序返回；
        has_more 指示是否还有更早的消息。before_id 不属于本会话时抛 ValueError。
        """
        async with self._factory() as db:
            query = select(ChatMessage).where(ChatMessage.session_id == session_id)
            if not include_tool:
                # 用户视角：排除 tool 行，以及携带 tool_calls 但无正文的
                # assistant 脚手架行（仅服务 Agent 循环用，用户不可见）
                query = query.where(
                    (ChatMessage.role != "tool")
                    & ~(
                        (ChatMessage.tool_calls.is_not(None))
                        & (ChatMessage.content.is_(None))
                    )
                )
            if before_id is not None:
                cursor = await db.get(ChatMessage, before_id)
                if cursor is None or cursor.session_id != session_id:
                    raise ValueError("无效的消息游标")
                query = query.where(ChatMessage.created_at < cursor.created_at)
            result = await db.execute(
                query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(
                    limit + 1
                )
            )
            rows = list(result.scalars().all())
            has_more = len(rows) > limit
            rows = rows[:limit]
            rows.reverse()
            return rows, has_more

    async def list_messages(self, session_id: str) -> list[ChatMessage]:
        async with self._factory() as db:
            result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at)
            )
            return list(result.scalars().all())
