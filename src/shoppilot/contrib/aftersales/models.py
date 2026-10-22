"""售后领域的规范模型。"""

from pydantic import BaseModel


class TimelineEvent(BaseModel):
    time: str
    event: str


class AftersaleSummary(BaseModel):
    aftersale_id: str
    order_id: str
    type: str  # 仅退款 / 退货退款 / 换货 / 维修
    status: str  # 待审核 / 处理中 / 已完成 / 已拒绝
    amount: float
    currency: str = "CNY"
    created_at: str


class AftersaleDetail(AftersaleSummary):
    reason: str
    timeline: list[TimelineEvent]
