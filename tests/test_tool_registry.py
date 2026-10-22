"""ToolRegistry：命名空间、冲突检测、schema 生成。"""

import pytest

from shoppilot.core.tools import ToolRegistry, ToolSet, ToolSpec


class DummyToolSet(ToolSet):
    name = "dummy"
    description = "哑插件"

    def __init__(self) -> None:
        self.adapter = object()

    def build_tools(self) -> list[ToolSpec]:
        async def handler(args, ctx):
            return {}

        return [
            ToolSpec(
                name="ping",
                description="回显",
                parameters={"type": "object", "properties": {}},
                handler=handler,
            )
        ]


class SameNameToolSet(DummyToolSet):
    name = "dummy"


def test_register_namespaces_tools():
    registry = ToolRegistry()
    registry.register(DummyToolSet())
    assert "dummy__ping" in registry
    schema = registry.openai_tools()
    assert schema[0]["function"]["name"] == "dummy__ping"
    assert registry.get("dummy__ping").name == "dummy__ping"


def test_toolset_name_conflict_rejected():
    registry = ToolRegistry()
    registry.register(DummyToolSet())
    with pytest.raises(ValueError, match="ToolSet 名称冲突"):
        registry.register(SameNameToolSet())


def test_toolset_without_name_rejected():
    with pytest.raises(TypeError, match="name"):

        class NoName(ToolSet):
            def build_tools(self) -> list[ToolSpec]:
                return []


def test_unknown_tool_lookup_raises():
    registry = ToolRegistry()
    registry.register(DummyToolSet())
    with pytest.raises(KeyError):
        registry.get("dummy__missing")
