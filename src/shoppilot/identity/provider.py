"""身份接缝（ADR-0004）：校验凭证、解析出 Identity。"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from shoppilot.identity.signing import ExpiredToken, InvalidToken, verify_token


@dataclass(frozen=True)
class Identity:
    """一次会话的已验证用户身份。

    Identity 随工具执行上下文传递、永不出现在 LLM 可见参数中；
    越权防护契约在适配器内按 identity.user_id 过滤执行。
    """

    user_id: str
    claims: dict[str, Any] = field(default_factory=dict)


class IdentityProvider(Protocol):
    """身份接缝：接入方可实现自有账号体系的校验逻辑。"""

    async def verify(self, token: str) -> Identity: ...


class HmacIdentityProvider:
    """生产形态：校验服务端签发的 HMAC 签名 token。"""

    def __init__(self, secret: str) -> None:
        self._secret = secret

    async def verify(self, token: str) -> Identity:
        try:
            payload = verify_token(token, self._secret)
        except ExpiredToken:
            raise
        user_id = payload.get("user_id")
        if not user_id:
            raise InvalidToken("payload 缺少 user_id")
        claims = {k: v for k, v in payload.items() if k not in ("exp", "iat")}
        return Identity(user_id=str(user_id), claims=claims)


class MockIdentityProvider:
    """demo 形态：token 即 user_id，免签发，仅演示用。"""

    async def verify(self, token: str) -> Identity:
        user_id = token.strip()
        if not user_id:
            raise InvalidToken("user_id 不能为空")
        return Identity(user_id=user_id, claims={"mock": True})
