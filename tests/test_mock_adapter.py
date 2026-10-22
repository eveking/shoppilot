"""MockShopAdapter：越权过滤、分页、脱敏示范。"""

from shoppilot.adapters.mock_shop import MockShopAdapter
from shoppilot.identity.provider import Identity


async def test_list_orders_filtered_by_identity():
    adapter = MockShopAdapter()
    orders, total = await adapter.list_orders(Identity(user_id="u_1001"), limit=20)
    assert total == 5
    assert all(o.order_id.startswith("SO") for o in orders)
    # 按创建时间倒序
    created = [o.created_at for o in orders]
    assert created == sorted(created, reverse=True)


async def test_list_orders_status_filter():
    adapter = MockShopAdapter()
    orders, total = await adapter.list_orders(Identity(user_id="u_1001"), status="已完成", limit=20)
    assert total == 1
    assert orders[0].order_id == "SO20260310002"


async def test_get_order_denies_cross_user_access():
    adapter = MockShopAdapter()
    # SO20260320006 属于 u_1002，u_1001 查询必须不可见
    assert await adapter.get_order(Identity(user_id="u_1001"), "SO20260320006") is None
    detail = await adapter.get_order(Identity(user_id="u_1002"), "SO20260320006")
    assert detail is not None
    assert detail.items[0].title == "27 英寸 2K 显示器"


async def test_receiver_info_is_masked():
    adapter = MockShopAdapter()
    detail = await adapter.get_order(Identity(user_id="u_1001"), "SO20260315001")
    assert detail is not None
    assert "****" in detail.receiver_phone
    assert "张" in detail.receiver_name and len(detail.receiver_name) <= 2


async def test_list_aftersales_and_isolation():
    adapter = MockShopAdapter()
    items, total = await adapter.list_aftersales(Identity(user_id="u_1001"), limit=20)
    assert total == 2
    other, _ = await adapter.list_aftersales(Identity(user_id="u_1002"), order_id="SO20260320006")
    assert len(other) == 1 and other[0].status == "已拒绝"


async def test_get_aftersale_includes_timeline():
    adapter = MockShopAdapter()
    detail = await adapter.get_aftersale(Identity(user_id="u_1001"), "AF20260411001")
    assert detail is not None
    assert detail.timeline[0].event == "用户提交售后申请"
    assert await adapter.get_aftersale(Identity(user_id="u_1003"), "AF20260411001") is None
