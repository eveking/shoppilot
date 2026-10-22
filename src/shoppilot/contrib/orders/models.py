"""订单领域的规范模型（canonical models）。

适配器负责把外部平台的数据转换成这些模型；
字段即工具返回给 LLM 的内容，收件人信息在适配器侧完成脱敏。
"""

from pydantic import BaseModel


class OrderItem(BaseModel):
    sku: str
    title: str
    quantity: int
    unit_price: float
    subtotal: float


class OrderSummary(BaseModel):
    order_id: str
    status: str
    total_amount: float
    currency: str = "CNY"
    item_count: int
    created_at: str


class OrderDetail(OrderSummary):
    items: list[OrderItem]
    receiver_name: str
    receiver_phone: str
    shipping_address: str
    paid_at: str | None = None
    remark: str | None = None
