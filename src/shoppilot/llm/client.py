"""LLM 接缝（ADR-0005）：OpenAI 兼容协议客户端。

base_url / api_key / model 全部配置化，默认 deepseek-chat；
不做逐厂商适配，协议行为以 OpenAI 兼容语义为准。
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass(frozen=True)
class LLMToolCallDelta:
    """流式工具调用增量。"""

    index: int
    id: str | None = None
    name: str | None = None
    arguments_delta: str = ""


@dataclass(frozen=True)
class LLMChunk:
    """流式输出的一个增量片段。"""

    content: str | None = None
    tool_call: LLMToolCallDelta | None = None
    finish_reason: str | None = None
    usage: dict | None = None


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "empty")

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """流式对话；tools 为 OpenAI function calling schema 列表。"""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.usage is not None:
                yield LLMChunk(usage=chunk.usage.model_dump())
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            if delta is not None and delta.content:
                yield LLMChunk(content=delta.content)
            if delta is not None and delta.tool_calls:
                for tc in delta.tool_calls:
                    name = tc.function.name if tc.function else None
                    args = tc.function.arguments if tc.function else ""
                    yield LLMChunk(
                        tool_call=LLMToolCallDelta(
                            index=tc.index,
                            id=tc.id,
                            name=name,
                            arguments_delta=args or "",
                        )
                    )
            if choice.finish_reason:
                yield LLMChunk(finish_reason=choice.finish_reason)
