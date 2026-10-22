"""工具执行上下文。"""

from dataclasses import dataclass, field
from typing import Any

from shoppilot.identity.provider import Identity


@dataclass(frozen=True)
class ToolContext:
    """工具执行时由框架注入的上下文。

    关键不变量：用户身份经此传递给工具实现，**不进入 LLM 可见的工具参数**；
    适配器实现必须按 identity 过滤数据（越权防护契约，ADR-0002/0004）。
    """

    identity: Identity
    session_id: str
    claims: dict[str, Any] = field(default_factory=dict)
