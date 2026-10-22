"""测试公共设施：测试用 Settings 与 FakeLLM 替身。"""

import pytest

from shoppilot.llm.client import LLMChunk, LLMToolCallDelta
from shoppilot.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path.as_posix()}/test.db",
        demo_mode=True,
        auto_migrate=True,
        llm_api_key="test-key",
        cors_origins=[],
    )


class FakeLLM:
    """按脚本回放 LLMChunk 的替身，记录每次收到的 messages/tools。"""

    def __init__(self, scripts: list[list[LLMChunk]]) -> None:
        self._scripts = list(scripts)
        self.calls: list[dict] = []

    async def stream_chat(self, messages, tools=None):
        self.calls.append({"messages": messages, "tools": tools or []})
        script = self._scripts.pop(0)
        for chunk in script:
            yield chunk


def text_script(text: str, finish: str = "stop") -> list[LLMChunk]:
    return [LLMChunk(content=text), LLMChunk(finish_reason=finish)]


def tool_script(call_id: str, name: str, arguments: str) -> list[LLMChunk]:
    return [
        LLMChunk(
            tool_call=LLMToolCallDelta(index=0, id=call_id, name=name, arguments_delta=arguments)
        ),
        LLMChunk(finish_reason="tool_calls"),
    ]
