"""MockShopAdapter：示例数据源适配器（ADR-0002）。

同时实现 OrderAdapter 与 AftersaleAdapter 两个领域协议，
演示接入方需要遵守的全部契约：按 identity 过滤、脱敏、分页、倒序。
"""

from shoppilot.adapters.mock_shop.seed import DEMO_AFTERSALES, DEMO_ORDERS
from shoppilot.contrib.aftersales.models import AftersaleDetail, AftersaleSummary, TimelineEvent
from shoppilot.contrib.orders.models import OrderDetail, OrderItem, OrderSummary
from shoppilot.identity.provider import Identity


class MockShopAdapter:
    """内存实现：数据来自 seed.py，进程内共享、只读。"""

    # ---- OrderAdapter ----

    async def list_orders(
        self,
        identity: Identity,
        *,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> tuple[list[OrderSummary], int]:
        mine = [
            (order_id, o) for order_id, o in DEMO_ORDERS.items() if o["user_id"] == identity.user_id
        ]
        if status is not None:
            mine = [(oid, o) for oid, o in mine if o["status"] == status]
        mine.sort(key=lambda pair: pair[1]["created_at"], reverse=True)
        page = mine[offset : offset + limit]
        summaries = [
            OrderSummary(
                order_id=order_id,
                status=o["status"],
                total_amount=o["total_amount"],
                item_count=sum(i["quantity"] for i in o["items"]),
                created_at=o["created_at"],
            )
            for order_id, o in page
        ]
        return summaries, len(mine)

    async def get_order(self, identity: Identity, order_id: str) -> OrderDetail | None:
        order = DEMO_ORDERS.get(order_id)
        # 越权防护契约：非本人的订单一律视为不存在
        if order is None or order["user_id"] != identity.user_id:
            return None
        return OrderDetail(
            order_id=order_id,
            status=order["status"],
            total_amount=order["total_amount"],
            item_count=sum(i["quantity"] for i in order["items"]),
            created_at=order["created_at"],
            items=[OrderItem(**i) for i in order["items"]],
            receiver_name=order["receiver_name"],
            receiver_phone=order["receiver_phone"],
            shipping_address=order["shipping_address"],
            paid_at=order["paid_at"],
            remark=order["remark"],
        )

    # ---- AftersaleAdapter ----

    async def list_aftersales(
        self,
        identity: Identity,
        *,
        order_id: str | None = None,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> tuple[list[AftersaleSummary], int]:
        mine = [
            (aftersale_id, a)
            for aftersale_id, a in DEMO_AFTERSALES.items()
            if a["user_id"] == identity.user_id
        ]
        if order_id is not None:
            mine = [(aid, a) for aid, a in mine if a["order_id"] == order_id]
        if status is not None:
            mine = [(aid, a) for aid, a in mine if a["status"] == status]
        mine.sort(key=lambda pair: pair[1]["created_at"], reverse=True)
        page = mine[offset : offset + limit]
        summaries = [
            AftersaleSummary(
                aftersale_id=aftersale_id,
                order_id=a["order_id"],
                type=a["type"],
                status=a["status"],
                amount=a["amount"],
                created_at=a["created_at"],
            )
            for aftersale_id, a in page
        ]
        return summaries, len(mine)

    async def get_aftersale(self, identity: Identity, aftersale_id: str) -> AftersaleDetail | None:
        aftersale = DEMO_AFTERSALES.get(aftersale_id)
        if aftersale is None or aftersale["user_id"] != identity.user_id:
            return None
        return AftersaleDetail(
            aftersale_id=aftersale_id,
            order_id=aftersale["order_id"],
            type=aftersale["type"],
            status=aftersale["status"],
            amount=aftersale["amount"],
            created_at=aftersale["created_at"],
            reason=aftersale["reason"],
            timeline=[TimelineEvent(**e) for e in aftersale["timeline"]],
        )
