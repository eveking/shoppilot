"""工具接缝的核心抽象（ADR-0003）。

一个领域 = 一个 ToolSet 插件：工具声明 + 领域适配器协议 + 系统提示片段。
框架核心只认识 ToolSet 抽象，不认识任何具体领域。
"""

import abc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from shoppilot.core.context import ToolContext


class ToolExecutionError(RuntimeError):
    """工具实现主动抛出的业务错误（如参数非法、数据不可达）。"""


@dataclass(frozen=True)
class ToolSpec:
    """单个工具的完整声明。

    name 为领域内短名（如 query_orders），注册表负责加命名空间前缀。
    """

    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable[[dict, ToolContext], Awaitable[dict]]


class ToolSet(abc.ABC):
    """领域插件基类：注册进 ToolRegistry 即生效。"""

    #: 命名空间（如 orders），工具全名为 f"{name}__{短名}"
    name: str
    #: 注入系统提示的领域知识片段
    description: str = ""

    adapter: object
    #: 该领域要求的适配器协议（文档性声明，供接入方实现）
    adapter_protocol: type = object

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "name", None):
            raise TypeError(f"{cls.__name__} 必须定义类属性 name（领域命名空间）")

    @abc.abstractmethod
    def build_tools(self) -> list[ToolSpec]:
        """声明本领域的全部工具。"""


class ToolRegistry:
    """工具注册表：收集 ToolSet → 命名空间化 → 生成模型侧 schema。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._toolsets: list[ToolSet] = []

    def register(self, toolset: ToolSet) -> None:
        if any(ts.name == toolset.name for ts in self._toolsets):
            raise ValueError(f"ToolSet 名称冲突: {toolset.name}")
        self._toolsets.append(toolset)
        for spec in toolset.build_tools():
            full_name = f"{toolset.name}__{spec.name}"
            if full_name in self._tools:
                raise ValueError(f"工具名冲突: {full_name}")
            self._tools[full_name] = replace(spec, name=full_name)

    @property
    def toolsets(self) -> list[ToolSet]:
        return list(self._toolsets)

    def openai_tools(self) -> list[dict]:
        """转换为 OpenAI function calling schema。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def get(self, namespaced_name: str) -> ToolSpec:
        """按全名取工具；未知工具抛 KeyError。"""
        return self._tools[namespaced_name]

    def __contains__(self, namespaced_name: str) -> bool:
        return namespaced_name in self._tools
