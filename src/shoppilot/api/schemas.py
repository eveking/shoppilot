"""API 请求/响应模型。"""

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    """创建会话：demo 模式传 user_id；生产模式传签名 token。"""

    token: str | None = None
    user_id: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str
    demo_mode: bool


class ChatRequest(BaseModel):
    session_id: str
    message: str
