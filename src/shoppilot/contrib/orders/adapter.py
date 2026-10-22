"""订单领域的数据源接缝（ADR-0002）。

接入新平台（淘宝开放平台 / Shopify / 自建商城）= 实现本协议并注册
OrdersToolSet(adapter=你的实现)。

实现契约：
1. 必须按 identity.user_id 过滤数据（越权防护），查无或非本人 → 返回 None；
2. 收件人姓名、手机号、地址必须脱敏后再返回；
3. created_at / paid_at 使用 "YYYY-MM-DD HH:MM:SS" 字符串；
4. 网络与平台错误抛 ToolExecutionError，让框架折叠成 {"error": ...}。
"""

from typing import Protocol

from shoppilot.contrib.orders.models import OrderDetail, OrderSummary
from shoppilot.identity.provider import Identity


class OrderAdapter(Protocol):
    async def list_orders(
        self,
        identity: Identity,
        *,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> tuple[list[OrderSummary], int]:
        """返回 (当前页订单摘要, 符合条件的总数)，按创建时间倒序。"""
        ...

    async def get_order(self, identity: Identity, order_id: str) -> OrderDetail | None:
        """返回订单详情；不存在或不属于该用户返回 None。"""
        ...
