"""HTTP 路由：/health、/sessions、/chat（SSE）、历史读回（ADR-0011）。"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from shoppilot.api.schemas import ChatRequest, CreateSessionRequest
from shoppilot.core.agent import AgentEvent, run_chat
from shoppilot.core.context_builder import build_messages, build_system_prompt
from shoppilot.identity.provider import Identity
from shoppilot.identity.signing import ExpiredToken, TokenError

logger = logging.getLogger(__name__)

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_PAGE_LIMIT_MAX = 200
_PAGE_LIMIT_DEFAULT = 50


def _row_to_message(row) -> dict:
    msg = {"role": row.role}
    if row.content is not None:
        msg["content"] = row.content
    if row.tool_calls:
        msg["tool_calls"] = json.loads(row.tool_calls)
    if row.tool_call_id:
        msg["tool_call_id"] = row.tool_call_id
    return msg


async def _require_identity(request: Request, body_token: str | None = None) -> Identity | None:
    """会话接口的统一鉴权（ADR-0011）。

    demo 模式豁免，返回 None；生产模式要求 token（Authorization: Bearer 优先，
    body token 兜底），校验失败抛 401。
    """
    state = request.app.state
    if state.settings.demo_mode:
        return None
    raw = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        raw = auth[len("Bearer ") :].strip()
    raw = raw or (body_token or "").strip() or None
    if raw is None:
        raise HTTPException(status_code=401, detail="缺少凭证（Authorization: Bearer <token>）")
    try:
        return await state.identity_provider.verify(raw)
    except ExpiredToken:
        raise HTTPException(status_code=401, detail="token 已过期，请重新签发") from None
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=f"身份校验失败: {exc}") from None


def _ensure_owner(identity: Identity | None, session) -> None:
    """所有权校验：非归属者一律 404，不泄露会话存在性。"""
    if identity is not None and identity.user_id != session.user_id:
        raise HTTPException(status_code=404, detail="会话不存在或已失效")


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, _PAGE_LIMIT_MAX))


async def _get_owned_session(session_id: str, request: Request, body_token: str | None = None):
    state = request.app.state
    session = await state.repo.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已失效")
    identity = await _require_identity(request, body_token)
    _ensure_owner(identity, session)
    return session, identity


@router.get("/health")
async def health(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "version": request.app.version,
        "demo_mode": settings.demo_mode,
        "llm_model": settings.llm_model,
    }


@router.post("/sessions", status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> dict:
    state = request.app.state
    if (body.token is None) == (body.user_id is None):
        raise HTTPException(
            status_code=400,
            detail="token 与 user_id 必须二选一（demo 模式传 user_id，生产模式传 token）",
        )
    if body.user_id is not None:
        if not state.settings.demo_mode:
            raise HTTPException(status_code=400, detail="demo 模式已关闭，请携带签名 token")
        raw_token = body.user_id
    else:
        raw_token = body.token  # type: ignore[assignment]
    try:
        identity = await state.identity_provider.verify(raw_token)
    except ExpiredToken:
        raise HTTPException(status_code=401, detail="token 已过期，请重新签发") from None
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=f"身份校验失败: {exc}") from None
    session = await state.repo.create_session(user_id=identity.user_id)
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "demo_mode": state.settings.demo_mode,
    }


@router.get("/sessions")
async def list_sessions(request: Request, limit: int = _PAGE_LIMIT_DEFAULT) -> dict:
    """当前用户的会话列表，按最近活跃倒序（ADR-0011）。

    生产模式身份取 token；demo 模式豁免鉴权，用 user_id 查询参数指定。
    """
    state = request.app.state
    identity = await _require_identity(request)
    if identity is not None:
        user_id = identity.user_id
    else:
        user_id = (request.query_params.get("user_id") or "").strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="demo 模式必须传 user_id 查询参数")
    rows = await state.repo.list_sessions(user_id, limit=_clamp_limit(limit))
    return {
        "sessions": [
            {
                "session_id": row.id,
                "created_at": row.created_at,
                "last_message_at": row.last_message_at,
            }
            for row in rows
        ]
    }


@router.get("/sessions/{session_id}/messages")
async def list_session_messages(
    session_id: str,
    request: Request,
    limit: int = _PAGE_LIMIT_DEFAULT,
    before: str | None = None,
) -> dict:
    """历史读回（用户视角）：只含 user/assistant 消息，游标分页（ADR-0011）。"""
    session, _ = await _get_owned_session(session_id, request)
    try:
        rows, has_more = await request.app.state.repo.list_messages_page(
            session.id, limit=_clamp_limit(limit), before_id=before, include_tool=False
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {
        "session_id": session.id,
        "has_more": has_more,
        "messages": [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@router.get("/sessions/{session_id}/events")
async def list_session_events(
    session_id: str,
    request: Request,
    limit: int = _PAGE_LIMIT_DEFAULT,
    before: str | None = None,
) -> dict:
    """审计读回：全量消息含 tool 调用与结果，游标分页（ADR-0011）。"""
    session, _ = await _get_owned_session(session_id, request)
    try:
        rows, has_more = await request.app.state.repo.list_messages_page(
            session.id, limit=_clamp_limit(limit), before_id=before, include_tool=True
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {
        "session_id": session.id,
        "has_more": has_more,
        "events": [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "tool_calls": json.loads(row.tool_calls) if row.tool_calls else None,
                "tool_call_id": row.tool_call_id,
                "tool_name": row.tool_name,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    state = request.app.state
    session, identity = await _get_owned_session(body.session_id, request, body.token)

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    settings = state.settings
    history_rows = await state.repo.list_messages(session.id)
    await state.repo.append_message(session.id, actor=session.user_id, role="user", content=message)

    messages = build_messages(
        history=[_row_to_message(r) for r in history_rows],
        user_message=message,
        system_prompt=build_system_prompt(state.registry.toolsets),
        max_messages=settings.context_max_messages,
    )
    if identity is None:  # demo 模式：身份取会话归属者
        identity = Identity(user_id=session.user_id)

    async def persist(**kwargs) -> None:
        await state.repo.append_message(session.id, actor=session.user_id, **kwargs)

    async def event_stream():
        try:
            async for event in run_chat(
                llm=state.llm,
                registry=state.registry,
                messages=messages,
                identity=identity,
                session_id=session.id,
                max_rounds=settings.agent_max_tool_rounds,
                tool_result_max_chars=settings.tool_result_max_chars,
                persist=persist,
            ):
                yield f"data: {event.model_dump_json(exclude_none=True)}\n\n"
        except Exception:
            logger.exception("会话 %s 对话流异常", session.id)
            error_event = AgentEvent(type="error", error="服务内部异常，请稍后重试")
            yield f"data: {error_event.model_dump_json(exclude_none=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
