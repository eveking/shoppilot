"""sessions 增加 last_message_at（ADR-0011 会话列表排序依据）

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("last_message_at", sa.DateTime(), nullable=True))
    # 回填存量数据：取会话内最新一条消息的 created_at
    op.execute(
        "UPDATE sessions SET last_message_at = ("
        " SELECT MAX(created_at) FROM messages WHERE messages.session_id = sessions.id)"
    )


def downgrade() -> None:
    op.drop_column("sessions", "last_message_at")
