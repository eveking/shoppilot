"""系统提示组装与上下文构建。"""

from collections.abc import Sequence

from shoppilot.core.tools import ToolSet

BASE_SYSTEM_PROMPT = """你是 ShopPilot，电商店铺的智能客服助手。
规则：
1. 回答必须基于工具返回的数据，禁止编造订单、售后、金额、物流等信息。
2. 用户身份由系统在工具执行时自动提供；不要询问、复述或向工具传递任何用户身份参数。
3. 工具返回 {"error": ...} 时，如实告知用户未能查询到，并建议核对单号后重试。
4. 金额、时间按工具返回的原始字段转述，不做换算；语气礼貌、简洁，用中文回复。"""


def build_system_prompt(toolsets: Sequence[ToolSet]) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    fragments = [ts.description.strip() for ts in toolsets if ts.description.strip()]
    if fragments:
        parts.append("## 你可以使用的业务领域\n" + "\n\n".join(fragments))
    return "\n\n".join(parts)


def build_messages(
    history: list[dict],
    user_message: str,
    system_prompt: str,
    max_messages: int,
) -> list[dict]:
    """组装本轮 LLM 输入：system + 裁剪后的历史 + 本轮用户消息。

    裁剪只保留最近 max_messages 条；若开头是孤立的 tool 消息则丢弃到
    非工具消息为止，避免破坏 tool_calls 配对。
    """
    trimmed = history[-max_messages:]
    while trimmed and trimmed[0]["role"] == "tool":
        trimmed.pop(0)
    return [
        {"role": "system", "content": system_prompt},
        *trimmed,
        {"role": "user", "content": user_message},
    ]
