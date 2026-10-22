"""Mock 商城种子数据：模拟商城的用户 / 订单 / 售后单。

收件人姓名、手机号、地址均为虚构且已脱敏——这本身就是给适配器实现者的示范。
demo 用户：u_1001 张三 / u_1002 李四 / u_1003 王五（对话时 user_id 即用户编号）。
"""

# 按订单号组织；user_id 用于越权过滤
DEMO_ORDERS: dict[str, dict] = {
    "SO20260315001": {
        "user_id": "u_1001",
        "status": "待发货",
        "total_amount": 299.00,
        "created_at": "2026-03-15 10:23:00",
        "paid_at": "2026-03-15 10:25:11",
        "remark": "希望尽快发货",
        "receiver_name": "张*",
        "receiver_phone": "138****5678",
        "shipping_address": "上海市浦东新区**路**号 3 幢 502",
        "items": [
            {
                "sku": "SKU-BT-001",
                "title": "无线蓝牙耳机 降噪版",
                "quantity": 1,
                "unit_price": 299.00,
                "subtotal": 299.00,
            },
        ],
    },
    "SO20260310002": {
        "user_id": "u_1001",
        "status": "已完成",
        "total_amount": 89.80,
        "created_at": "2026-03-10 20:01:44",
        "paid_at": "2026-03-10 20:02:03",
        "remark": None,
        "receiver_name": "张*",
        "receiver_phone": "138****5678",
        "shipping_address": "上海市浦东新区**路**号 3 幢 502",
        "items": [
            {
                "sku": "SKU-CUP-010",
                "title": "316 不锈钢保温杯 500ml",
                "quantity": 1,
                "unit_price": 59.90,
                "subtotal": 59.90,
            },
            {
                "sku": "SKU-TEA-003",
                "title": "桂花乌龙茶包 10 袋",
                "quantity": 1,
                "unit_price": 29.90,
                "subtotal": 29.90,
            },
        ],
    },
    "SO20260402004": {
        "user_id": "u_1001",
        "status": "已发货",
        "total_amount": 459.00,
        "created_at": "2026-04-02 09:12:30",
        "paid_at": "2026-04-02 09:13:05",
        "remark": None,
        "receiver_name": "张*",
        "receiver_phone": "138****5678",
        "shipping_address": "上海市浦东新区**路**号 3 幢 502",
        "items": [
            {
                "sku": "SKU-KB-087",
                "title": "87 键机械键盘 茶轴",
                "quantity": 1,
                "unit_price": 459.00,
                "subtotal": 459.00,
            },
        ],
    },
    "SO20260418005": {
        "user_id": "u_1001",
        "status": "待付款",
        "total_amount": 129.00,
        "created_at": "2026-04-18 22:45:10",
        "paid_at": None,
        "remark": None,
        "receiver_name": "张*",
        "receiver_phone": "138****5678",
        "shipping_address": "上海市浦东新区**路**号 3 幢 502",
        "items": [
            {
                "sku": "SKU-MSE-112",
                "title": "静音无线鼠标",
                "quantity": 1,
                "unit_price": 129.00,
                "subtotal": 129.00,
            },
        ],
    },
    "SO20260301003": {
        "user_id": "u_1001",
        "status": "已取消",
        "total_amount": 199.00,
        "created_at": "2026-03-01 08:30:00",
        "paid_at": None,
        "remark": "超时未支付自动取消",
        "receiver_name": "张*",
        "receiver_phone": "138****5678",
        "shipping_address": "上海市浦东新区**路**号 3 幢 502",
        "items": [
            {
                "sku": "SKU-BAG-021",
                "title": "通勤单肩包",
                "quantity": 1,
                "unit_price": 199.00,
                "subtotal": 199.00,
            },
        ],
    },
    "SO20260320006": {
        "user_id": "u_1002",
        "status": "已完成",
        "total_amount": 1399.00,
        "created_at": "2026-03-20 14:05:00",
        "paid_at": "2026-03-20 14:06:12",
        "remark": None,
        "receiver_name": "李*",
        "receiver_phone": "186****3301",
        "shipping_address": "杭州市西湖区**街**号 7 栋 1201",
        "items": [
            {
                "sku": "SKU-MON-027",
                "title": "27 英寸 2K 显示器",
                "quantity": 1,
                "unit_price": 1399.00,
                "subtotal": 1399.00,
            },
        ],
    },
    "SO20260401007": {
        "user_id": "u_1002",
        "status": "已发货",
        "total_amount": 259.00,
        "created_at": "2026-04-01 11:40:22",
        "paid_at": "2026-04-01 11:41:00",
        "remark": None,
        "receiver_name": "李*",
        "receiver_phone": "186****3301",
        "shipping_address": "杭州市西湖区**街**号 7 栋 1201",
        "items": [
            {
                "sku": "SKU-MSE-115",
                "title": "电竞无线鼠标 PRO",
                "quantity": 1,
                "unit_price": 259.00,
                "subtotal": 259.00,
            },
        ],
    },
    "SO20260415008": {
        "user_id": "u_1003",
        "status": "已完成",
        "total_amount": 899.00,
        "created_at": "2026-04-15 19:20:00",
        "paid_at": "2026-04-15 19:21:41",
        "remark": "送货前请电话联系",
        "receiver_name": "王*",
        "receiver_phone": "137****9024",
        "shipping_address": "成都市高新区**大道**号 2 栋 803",
        "items": [
            {
                "sku": "SKU-DSK-050",
                "title": "实木升降书桌 1.2m",
                "quantity": 1,
                "unit_price": 899.00,
                "subtotal": 899.00,
            },
        ],
    },
}

# 按售后单号组织；关联订单必须属于同一用户
DEMO_AFTERSALES: dict[str, dict] = {
    "AF20260411001": {
        "user_id": "u_1001",
        "order_id": "SO20260310002",
        "type": "仅退款",
        "status": "已完成",
        "amount": 29.90,
        "created_at": "2026-04-11 16:02:00",
        "reason": "茶包口感不符合预期，申请仅退款茶包部分",
        "timeline": [
            {"time": "2026-04-11 16:02:00", "event": "用户提交售后申请"},
            {"time": "2026-04-11 18:30:00", "event": "商家审核通过"},
            {"time": "2026-04-12 10:00:00", "event": "退款 29.90 元已原路退回"},
        ],
    },
    "AF20260416002": {
        "user_id": "u_1001",
        "order_id": "SO20260402004",
        "type": "换货",
        "status": "处理中",
        "amount": 0.00,
        "created_at": "2026-04-16 09:15:00",
        "reason": "键盘 A 键手感异常，申请同型号换新",
        "timeline": [
            {"time": "2026-04-16 09:15:00", "event": "用户提交换货申请"},
            {"time": "2026-04-16 15:40:00", "event": "商家审核通过，已发出换新商品"},
            {"time": "2026-04-18 11:20:00", "event": "换新商品运输中"},
        ],
    },
    "AF20260401003": {
        "user_id": "u_1002",
        "order_id": "SO20260320006",
        "type": "退货退款",
        "status": "已拒绝",
        "amount": 1399.00,
        "created_at": "2026-04-01 10:00:00",
        "reason": "超出 7 天无理由退货期申请退货",
        "timeline": [
            {"time": "2026-04-01 10:00:00", "event": "用户提交退货退款申请"},
            {"time": "2026-04-01 14:30:00", "event": "商家审核拒绝：超过 7 天无理由退货期限"},
        ],
    },
    "AF20260419004": {
        "user_id": "u_1003",
        "order_id": "SO20260415008",
        "type": "维修",
        "status": "待审核",
        "amount": 0.00,
        "created_at": "2026-04-19 20:10:00",
        "reason": "桌面升降按钮偶发失灵，申请保修维修",
        "timeline": [
            {"time": "2026-04-19 20:10:00", "event": "用户提交维修申请"},
        ],
    },
}
