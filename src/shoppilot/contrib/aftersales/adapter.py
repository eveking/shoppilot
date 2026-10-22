"""售后领域的数据源接缝（ADR-0002）。契约同 OrderAdapter。"""

from typing import Protocol

from shoppilot.contrib.aftersales.models import AftersaleDetail, AftersaleSummary
from shoppilot.identity.provider import Identity


class AftersaleAdapter(Protocol):
    async def list_aftersales(
        self,
        identity: Identity,
        *,
        order_id: str | None = None,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> tuple[list[AftersaleSummary], int]:
        """返回 (当前页售后单摘要, 符合条件的总数)，按创建时间倒序。"""
        ...

    async def get_aftersale(self, identity: Identity, aftersale_id: str) -> AftersaleDetail | None:
        """返回售后单详情；不存在或不属于该用户返回 None。"""
        ...
