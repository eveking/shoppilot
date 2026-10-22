"""售后领域 ToolSet：aftersales__list_aftersales / aftersales__get_aftersale。"""

from shoppilot.contrib.aftersales.adapter import AftersaleAdapter
from shoppilot.core.context import ToolContext
from shoppilot.core.tools import ToolExecutionError, ToolSet, ToolSpec

STATUS_VALUES = ["待审核", "处理中", "已完成", "已拒绝"]
TYPE_VALUES = ["仅退款", "退货退款", "换货", "维修"]


class AftersalesToolSet(ToolSet):
    name = "aftersales"
    description = (
        "售后领域：可查询用户本人的售后单列表（aftersales__list_aftersales）与售后单详情"
        "（aftersales__get_aftersale）。类型：仅退款/退货退款/换货/维修；"
        "状态：待审核/处理中/已完成/已拒绝。"
    )
    adapter_protocol = AftersaleAdapter

    def __init__(self, adapter: AftersaleAdapter) -> None:
        self.adapter = adapter

    def build_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_aftersales",
                description="查询用户本人的售后单列表，可按订单号或状态筛选，按创建时间倒序。",
                parameters={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "按订单号筛选，不传则查全部"},
                        "status": {
                            "type": "string",
                            "enum": STATUS_VALUES,
                            "description": "按售后状态筛选",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "description": "返回条数，默认 5",
                        },
                    },
                },
                handler=self._list_aftersales,
            ),
            ToolSpec(
                name="get_aftersale",
                description="按售后单号查询售后详情（含申请原因与处理时间线）。",
                parameters={
                    "type": "object",
                    "properties": {
                        "aftersale_id": {
                            "type": "string",
                            "description": "售后单号，如 AF20260411001",
                        }
                    },
                    "required": ["aftersale_id"],
                },
                handler=self._get_aftersale,
            ),
        ]

    async def _list_aftersales(self, args: dict, ctx: ToolContext) -> dict:
        order_id = args.get("order_id") or None
        status = args.get("status") or None
        try:
            limit = int(args.get("limit", 5))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("limit 必须是整数") from exc
        limit = max(1, min(limit, 20))
        if status is not None and status not in STATUS_VALUES:
            raise ToolExecutionError(f"未知售后状态: {status}")
        try:
            items, total = await self.adapter.list_aftersales(
                ctx.identity, order_id=order_id, status=status, limit=limit
            )
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"售后服务暂不可用: {exc}") from exc
        return {"total": total, "aftersales": [a.model_dump() for a in items]}

    async def _get_aftersale(self, args: dict, ctx: ToolContext) -> dict:
        aftersale_id = str(args.get("aftersale_id") or "").strip()
        if not aftersale_id:
            raise ToolExecutionError("aftersale_id 不能为空")
        try:
            detail = await self.adapter.get_aftersale(ctx.identity, aftersale_id)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"售后服务暂不可用: {exc}") from exc
        if detail is None:
            return {"error": f"未找到售后单 {aftersale_id}，请核对单号"}
        return detail.model_dump()
