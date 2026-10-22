"""HMAC 签名 Token 与身份提供方测试。"""

import pytest

from shoppilot.identity.provider import (
    HmacIdentityProvider,
    Identity,
    MockIdentityProvider,
)
from shoppilot.identity.signing import (
    ExpiredToken,
    InvalidToken,
    sign_token,
    verify_token,
)

SECRET = "test-secret"


def test_sign_and_verify_roundtrip():
    token = sign_token({"user_id": "u_1001"}, SECRET)
    payload = verify_token(token, SECRET)
    assert payload["user_id"] == "u_1001"
    assert "exp" in payload and "iat" in payload


def test_tampered_token_rejected():
    token = sign_token({"user_id": "u_1001"}, SECRET)
    body, sig = token.split(".")
    tampered = f"{body[:-2]}XY.{sig}"
    with pytest.raises(InvalidToken):
        verify_token(tampered, SECRET)


def test_wrong_secret_rejected():
    token = sign_token({"user_id": "u_1001"}, SECRET)
    with pytest.raises(InvalidToken):
        verify_token(token, "another-secret")


def test_expired_token_rejected():
    token = sign_token({"user_id": "u_1001"}, SECRET, expires_in=-10)
    with pytest.raises(ExpiredToken):
        verify_token(token, SECRET)


def test_malformed_token_rejected():
    with pytest.raises(InvalidToken):
        verify_token("not-a-token", SECRET)


async def test_hmac_provider_resolves_identity():
    provider = HmacIdentityProvider(SECRET)
    token = sign_token({"user_id": "u_1001", "role": "vip"}, SECRET)
    identity = await provider.verify(token)
    assert identity == Identity(user_id="u_1001", claims={"user_id": "u_1001", "role": "vip"})


async def test_mock_provider_treats_token_as_user_id():
    identity = await MockIdentityProvider().verify(" u_1002 ")
    assert identity.user_id == "u_1002"
    assert identity.claims == {"mock": True}


async def test_hmac_provider_requires_user_id():
    provider = HmacIdentityProvider(SECRET)
    token = sign_token({"nickname": "x"}, SECRET)
    with pytest.raises(InvalidToken):
        await provider.verify(token)
