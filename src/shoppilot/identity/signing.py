"""签名 Token 的签发与校验（ADR-0004）。

格式：base64url(JSON payload) + "." + base64url(HMAC-SHA256(body, secret))
接入方服务端用共享密钥签发；框架只负责校验。
"""

import base64
import hashlib
import hmac
import json
import time


class TokenError(Exception):
    """Token 校验失败基类。"""


class InvalidToken(TokenError):
    """格式错误或签名不匹配。"""


class ExpiredToken(TokenError):
    """已过期。"""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign_token(payload: dict, secret: str, expires_in: int = 86400) -> str:
    """签发 token；payload 中自动补 iat/exp（秒级 Unix 时间戳）。"""
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + expires_in}
    raw = _b64encode(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode())
    sig = _b64encode(hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{sig}"


def verify_token(token: str, secret: str) -> dict:
    """校验 token，返回 payload；失败抛 TokenError 子类。"""
    raw, _, sig = token.partition(".")
    if not raw or not sig:
        raise InvalidToken("token 格式错误")
    expected = _b64encode(hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise InvalidToken("签名不匹配")
    try:
        payload = json.loads(_b64decode(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidToken("payload 不是合法 JSON") from exc
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise InvalidToken("缺少过期时间")
    if exp < time.time():
        raise ExpiredToken("token 已过期")
    return payload
