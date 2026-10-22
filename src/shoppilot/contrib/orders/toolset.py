"""订单领域 ToolSet：orders__query_orders / orders__get_order。"""

from shoppilot.contrib.orders.adapter import OrderAdapter
from shoppilot.core.context import ToolContext
from shoppilot.core.tools import ToolExecutionError, ToolSet, ToolSpec

STATUS_VALUES = ["待付款", "待发货", "已发货", "已完成", "已取消"]


class OrdersToolSet(ToolSet):
    name = "orders"
    description = (
        "订单领域：可查询用户本人的订单列表（orders__query_orders）与订单详情"
        "（orders__get_order）。订单状态取值：待付款/待发货/已发货/已完成/已取消。"
        "用户问「我的订单」「包裹到哪了」等时先用列表工具定位订单。"
    )
    adapter_protocol = OrderAdapter

    def __init__(self, adapter: OrderAdapter) -> None:
        self.adapter = adapter

    def build_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="query_orders",
                description="查询用户本人的订单列表，按创建时间倒序，可按状态筛选。",
                parameters={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": STATUS_VALUES,
                            "description": "按订单状态筛选，不传则查全部",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "description": "返回条数，默认 5",
                        },
                    },
                },
                handler=self._query_orders,
            ),
            ToolSpec(
                name="get_order",
                description="按订单号查询订单详情（含商品明细与收货信息）。",
                parameters={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string", "description": "订单号，如 SO20260315001"}
                    },
                    "required": ["order_id"],
                },
                handler=self._get_order,
            ),
        ]

    async def _query_orders(self, args: dict, ctx: ToolContext) -> dict:
        status = args.get("status") or None
        try:
            limit = int(args.get("limit", 5))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("limit 必须是整数") from exc
        limit = max(1, min(limit, 20))
        if status is not None and status not in STATUS_VALUES:
            raise ToolExecutionError(f"未知订单状态: {status}")
        try:
            orders, total = await self.adapter.list_orders(ctx.identity, status=status, limit=limit)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"订单服务暂不可用: {exc}") from exc
        return {"total": total, "orders": [o.model_dump() for o in orders]}

    async def _get_order(self, args: dict, ctx: ToolContext) -> dict:
        order_id = str(args.get("order_id") or "").strip()
        if not order_id:
            raise ToolExecutionError("order_id 不能为空")
        try:
            order = await self.adapter.get_order(ctx.identity, order_id)
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"订单服务暂不可用: {exc}") from exc
        if order is None:
            return {"error": f"未找到订单 {order_id}，请核对订单号"}
        return order.model_dump()
