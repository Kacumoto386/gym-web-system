"""会员小程序 · 购卡 + 购课 + 支付接口（预开发阶段）

支付流程设计:
  选择商品 → 创建订单 → 发起支付 → 支付回调 → 激活权益

订单状态:
  pending     待支付
  paid        已支付（等待激活）
  completed   已完成（权益已激活）
  cancelled   已取消

预开发阶段:
  - pay() 接口直接模拟支付成功（无需真实支付）
  - 后续接入微信支付时，只需替换 prepay() 中的逻辑
  - 回调地址 /purchase/callback 预留给微信支付通知
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

from backend.database import get_db
from backend.models.models import MembershipCard, Member, Product, Package, Sale
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_member_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/purchase", tags=["会员-购买"])


# ─── Pydantic Schemas ───

class CreateOrderRequest(BaseModel):
    """创建订单请求"""
    product_type: Literal["card", "package"]  # card=会籍卡, package=课程包
    product_id: str                           # Product.id 或 Package.package_id
    quantity: int = 1
    remark: Optional[str] = ""


# ─── 商品查询 ───

@router.get("/card-products")
async def list_card_products(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """可购会籍卡种列表（会员端可见的卡产品）。"""
    products = db.query(Product).filter(
        Product.category.in_(["次卡", "期限卡", "储值卡", "现金卡"])
    ).all()
    return success(data=[
        {
            "id": str(p.id),
            "name": p.name,
            "category": p.category,
            "price": float(p.price) if p.price else 0,
            "total_classes": p.total_classes or 0,
            "bonus_classes": p.bonus_classes or 0,
            "validity_days": p.validity_days or 365,
            "description": p.remark or "",
        }
        for p in products
    ])


@router.get("/packages")
async def list_packages(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """可购课程包列表（会员端可见）。"""
    packages = db.query(Package).all()
    return success(data=[
        {
            "package_id": p.package_id,
            "name": p.name,
            "price": float(p.price) if p.price else 0,
            "total_classes": p.total_classes or 0,
            "validity_days": p.validity_days or 0,
            "description": p.remark or "",
        }
        for p in packages
    ])


# ─── 订单管理 ───

@router.post("/create-order")
async def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """创建订单（购卡/购课）。

    支付前先创建订单，锁住商品价格和库存信息。支付成功后根据
    product_type 自动激活对应权益（创建会籍卡/售课记录）。
    """
    member_id = member.get("sub")
    member_info = db.query(Member).filter(Member.member_id == member_id).first()
    if not member_info:
        raise MiniAppException(2002, "会员不存在")

    # 查询商品信息并计算金额
    product_name = ""
    amount = 0.0
    product_meta = {}  # 保存激活权益所需的额外信息

    if body.product_type == "card":
        product = db.query(Product).filter(Product.id == body.product_id).first()
        if not product:
            raise MiniAppException(2002, "卡产品不存在")
        product_name = product.name
        amount = float(product.price or 0) * body.quantity
        product_meta = {
            "card_type": product.category,
            "total_classes": product.total_classes or 0,
            "bonus_classes": product.bonus_classes or 0,
            "validity_days": product.validity_days or 365,
        }

    elif body.product_type == "package":
        pkg = db.query(Package).filter(Package.package_id == body.product_id).first()
        if not pkg:
            raise MiniAppException(2002, "课程包不存在")
        product_name = pkg.name
        amount = float(pkg.price or 0) * body.quantity
        product_meta = {
            "total_classes": pkg.total_classes or 0,
            "validity_days": pkg.validity_days or 0,
        }

    order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{_order_counter:04d}"
    _order_counter += 1
    now = datetime.now().isoformat()

    # 将订单数据存入 JSON 字段（预开发阶段用简单方式）
    # 正式开发时建议新建 purchase_orders 表
    order_record = {
        "order_id": order_id,
        "member_id": member_id,
        "member_name": member_info.name,
        "product_type": body.product_type,
        "product_id": body.product_id,
        "product_name": product_name,
        "quantity": body.quantity,
        "amount": amount,
        "status": "pending",
        "product_meta": product_meta,
        "remark": body.remark,
        "created_at": now,
        "paid_at": None,
    }

    # 预开发阶段：将订单存入内存字典
    # TODO: 正式开发时迁移到 purchase_orders 表
    _orders[order_id] = order_record

    return success(data={
        "order_id": order_id,
        "product_name": product_name,
        "amount": amount,
        "status": "pending",
        "created_at": now,
    })


@router.get("/orders")
async def list_orders(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """订单历史。"""
    member_id = member.get("sub")
    orders = [
        o for o in _orders.values()
        if o["member_id"] == member_id and (status is None or o["status"] == status)
    ]
    orders.sort(key=lambda o: o["created_at"], reverse=True)

    return success(data=[
        {
            "order_id": o["order_id"],
            "product_type": o["product_type"],
            "product_name": o["product_name"],
            "amount": o["amount"],
            "status": o["status"],
            "created_at": o["created_at"],
            "paid_at": o.get("paid_at"),
        }
        for o in orders
    ])


# ─── 支付接口 ───

@router.post("/prepay")
async def prepay(
    order_id: str,
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """发起支付 — 获取微信支付参数。

    预开发阶段：返回模拟 prepay_id，不发起真实支付。
    正式上线时替换为微信支付 JSAPI 下单逻辑：

        # 调用微信支付统一下单 API
        prepay_data = wechat_pay_unified_order(
            openid=openid,
            out_trade_no=order_id,
            total_fee=int(amount * 100),  # 单位：分
            body=product_name,
            notify_url="https://your-domain.com/api/miniapp/member/purchase/callback",
        )
    """
    member_id = member.get("sub")
    order = _orders.get(order_id)
    if not order or order["member_id"] != member_id:
        raise MiniAppException(2002, "订单不存在")
    if order["status"] != "pending":
        raise MiniAppException(3001, "订单状态不允许支付")

    # ── 模拟微信支付参数（预开发阶段）──
    mock_prepay_data = {
        "prepay_id": f"wx{mock_prepay_counter():016d}",
        "package": "prepay_id=mock_prepay_id",
        "nonceStr": "mock_nonce_" + order_id[-8:],
        "timeStamp": str(int(datetime.now().timestamp())),
        "signType": "MD5",
        "paySign": "mock_signature_for_predev",
        # 预开发标记：设为 true 时前端可以直接调 pay() 模拟支付
        "mock_pay": True,
    }

    return success(data=mock_prepay_data)


@router.post("/pay")
async def pay(
    order_id: str,
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """确认支付（预开发阶段：直接模拟支付成功）。

    正式流程：
      1. 小程序端调 wx.requestPayment(prepay_data)
      2. 用户输入密码完成支付
      3. 微信异步回调 /purchase/callback
      4. 回调中修改订单状态 + 激活权益
      5. 小程序端轮询或通过 WebSocket 获知支付结果

    预开发阶段简化：直接调用此接口模拟支付成功。
    """
    member_id = member.get("sub")
    order = _orders.get(order_id)
    if not order or order["member_id"] != member_id:
        raise MiniAppException(2002, "订单不存在")
    if order["status"] != "pending":
        raise MiniAppException(3001, "订单状态不允许支付")

    # 模拟支付成功
    order["status"] = "paid"
    order["paid_at"] = datetime.now().isoformat()

    # 激活权益
    _activate_order(db, member_id, order)

    return success(data={
        "order_id": order_id,
        "status": "completed",
        "message": "支付成功，权益已激活",
    })


@router.post("/callback")
async def payment_callback():
    """微信支付异步回调通知（预留）。

    微信支付成功后，微信服务器会 POST 通知此地址。
    需要验证签名 -> 修改订单状态 -> 激活权益 -> 返回 success 应答。

    预开发阶段暂不实现，后续接入微信支付时补充。
    """
    return {"code": 0, "message": "notify_received"}


# ─── 内部逻辑 ───

# 内存订单存储（预开发阶段用，正式版迁移到数据库）
_orders: dict = {}
_order_counter = 0


def mock_prepay_counter() -> int:
    global _order_counter
    _order_counter += 1
    return _order_counter


def _activate_order(db: Session, member_id: str, order: dict):
    """支付成功后激活权益：创建会籍卡或售课记录。"""
    meta = order.get("product_meta", {})

    if order["product_type"] == "card":
        # 创建会籍卡（复用 MembershipCard 模型）
        card_id = generate_id("MC", db, MembershipCard.card_id)
        card = MembershipCard(
            card_id=card_id,
            member_id=member_id,
            member_name=order["member_name"],
            product_name=order["product_name"],
            card_type=meta.get("card_type", "次卡"),
            total_classes=meta.get("total_classes", 0),
            bonus_classes=meta.get("bonus_classes", 0),
            remaining_classes=(meta.get("total_classes", 0) + meta.get("bonus_classes", 0)),
            amount=order["amount"],
            paid_amount=order["amount"],
            validity_days=meta.get("validity_days", 365),
            status="active",
        )
        db.add(card)

        # 次卡累加剩余课时
        if meta.get("card_type") == "次卡":
            add = (meta.get("total_classes", 0) + meta.get("bonus_classes", 0))
            member = db.query(Member).filter(Member.member_id == member_id).first()
            if member and add:
                member.remaining_lessons = (member.remaining_lessons or 0) + add

    elif order["product_type"] == "package":
        # 创建售课记录（复用 Sale 模型）
        from backend.models.models import Sale
        sale_id = generate_id("SA", db, Sale.sale_id)
        sale = Sale(
            sale_id=sale_id,
            member_id=member_id,
            member_name=order["member_name"],
            product_name=order["product_name"],
            quantity=order["quantity"],
            amount=order["amount"],
            paid_amount=order["amount"],
        )
        db.add(sale)

    order["status"] = "completed"
    db.commit()
