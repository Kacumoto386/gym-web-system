# -*- coding: utf-8 -*-
"""
商品零售 API 路由 + HTMX HTML 片段端点
V3.7.1 — 进销存增强
"""
from typing import Optional, List
from fastapi import Request, APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from decimal import Decimal
from backend.database import get_db
from backend.routers.operation_log import record_log
from backend.utils.response import success
from backend.models.models import Product, ProductSale, StockInbound, Member
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["商品零售"])


# ═══════════════════════════════════════════
# 商品管理
# ═══════════════════════════════════════════

def _build_product_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无商品</div>'
    trs = ""
    for p in rows:
        stock = p.stock or 0
        min_stock = p.min_stock or 0
        if stock == 0:
            stock_cls = "text-red-500 font-bold"
        elif stock <= min_stock:
            stock_cls = "text-orange-500"
        else:
            stock_cls = "text-gray-700"
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{p.product_id}</td>
            <td class="px-4 py-3">{p.name}</td>
            <td class="px-4 py-3 text-sm">{p.category or ''}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (p.cost_price or 0)}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (p.selling_price or 0)}</td>
            <td class="px-4 py-3 text-sm {stock_cls}">{stock} {p.unit or '个'}</td>
            <td class="px-4 py-3 text-sm">{p.supplier or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-blue-500 hover:text-blue-700 mr-2" onclick="openEditProduct('{p.product_id}')">编辑</button>
                <button class="text-green-500 hover:text-green-700 mr-2" onclick="openAdjustStock('{p.product_id}')">盘点</button>
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/products/{p.product_id}" hx-target="#productTable" hx-confirm="确认删除商品？">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">名称</th><th class="px-4 py-3">类别</th><th class="px-4 py-3">进价</th><th class="px-4 py-3">售价</th><th class="px-4 py-3">库存</th><th class="px-4 py-3">供应商</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/products/table", response_class=HTMLResponse)
def product_table(db: Session = Depends(get_db)):
    return _build_product_table(db.query(Product).order_by(Product.id.desc()).limit(100).all())


class ProductCreate(BaseModel):
    name: str
    category: str = ""
    cost_price: float = 0
    selling_price: float = 0
    stock: int = 0
    min_stock: int = 0
    unit: str = "个"
    supplier: str = ""
    remark: str = ""


class ProductOut(BaseModel):
    id: int
    product_id: str
    name: str
    category: str
    cost_price: float
    selling_price: float
    stock: int
    min_stock: int
    unit: str
    supplier: str

    class Config:
        from_attributes = True


@router.get("/products", response_model=List[ProductOut])
def list_products(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(Product).order_by(Product.id.desc()).offset(skip).limit(limit).all()


@router.post("/products", response_model=ProductOut)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    pid = generate_id("P", db, Product.product_id)
    p = Product(product_id=pid, name=data.name, category=data.category or "",
                cost_price=data.cost_price or 0, selling_price=data.selling_price or 0,
                stock=data.stock or 0, min_stock=data.min_stock or 0,
                unit=data.unit or "个",
                supplier=data.supplier or "", remark=data.remark or "")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: str, data: ProductCreate, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.product_id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    p.name = data.name
    p.category = data.category or ""
    p.cost_price = data.cost_price or 0
    p.selling_price = data.selling_price or 0
    p.stock = data.stock or 0
    p.min_stock = data.min_stock or 0
    p.unit = data.unit or "个"
    p.supplier = data.supplier or ""
    p.remark = data.remark or ""
    db.commit()
    db.refresh(p)
    return p


@router.put("/products/{product_id}/adjust-stock")
def adjust_stock(product_id: str, new_stock: int = Query(..., ge=0), reason: str = Query(""), db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.product_id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    old_stock = p.stock or 0
    p.stock = new_stock
    db.commit()
    return success(data={"product_id": product_id, "old_stock": old_stock, "new_stock": new_stock, "reason": reason})


@router.delete("/products/{product_id}")
def delete_product(product_id: str, request: Request, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.product_id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    # 记录操作日志
    token = request.cookies.get("access_token", "")
    op = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            op = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub", "系统")
        except Exception:
            pass
    record_log(db, op, "delete", "商品", product_id, f"删除商品：{p.name}({product_id})")
    db.delete(p)
    db.commit()
    return success(message="商品已删除")


# ═══════════════════════════════════════════
# 商品零售记录
# ═══════════════════════════════════════════

def _build_sale_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无零售记录</div>'
    trs = ""
    for s in rows:
        voided = getattr(s, 'voided', 0)
        row_cls = "hover:bg-gray-50 border-b" + (" opacity-50" if voided else "")
        if voided:
            action_cell = '<span class="text-gray-400 text-xs">已作废</span>'
            badge = '<span class="ml-2 text-xs bg-gray-200 text-gray-500 px-2 py-0.5 rounded">已作废</span>'
        else:
            action_cell = f'<button class="text-red-500 hover:text-red-700" onclick="openVoidModal(\'{s.sale_id}\', \'/api/product-sales/{s.sale_id}/void\')">作废</button>'
            badge = ''
        trs += f"""<tr class="{row_cls}">
            <td class="px-4 py-3 text-sm text-gray-500">{s.sale_id}</td>
            <td class="px-4 py-3 text-sm">{s.sale_date}</td>
            <td class="px-4 py-3">{s.member_name or ''}</td>
            <td class="px-4 py-3">{s.product_name}{badge}</td>
            <td class="px-4 py-3 text-sm">x{s.quantity}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (s.unit_price or 0)}</td>
            <td class="px-4 py-3 text-sm font-medium">{'%.2f' % (s.total_price or 0)}</td>
            <td class="px-4 py-3 text-sm">{s.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">
                {action_cell}
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">会员</th><th class="px-4 py-3">商品</th><th class="px-4 py-3">数量</th><th class="px-4 py-3">单价</th><th class="px-4 py-3">总价</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/product-sales/table", response_class=HTMLResponse)
def product_sale_table(db: Session = Depends(get_db)):
    return _build_sale_table(db.query(ProductSale).filter(ProductSale.voided == 0).order_by(ProductSale.sale_date.desc()).limit(100).all())


class ProductSaleCreate(BaseModel):
    member_id: str = ""
    member_name: str = ""
    product_name: str
    quantity: int = 1
    unit_price: float = 0
    total_price: float = 0
    payment_method: str = ""
    operator: str = ""
    remark: str = ""


class ProductSaleOut(BaseModel):
    id: int
    sale_id: str
    sale_date: date
    product_name: str
    quantity: int
    total_price: float

    class Config:
        from_attributes = True


@router.get("/product-sales", response_model=List[ProductSaleOut])
def list_product_sales(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(ProductSale).order_by(ProductSale.sale_date.desc()).offset(skip).limit(limit).all()


@router.post("/product-sales", response_model=ProductSaleOut)
def create_product_sale(data: ProductSaleCreate, db: Session = Depends(get_db)):
    # 查询商品成本价并扣减库存
    product = db.query(Product).filter(Product.name == data.product_name).first()
    cost_price = float(product.cost_price or 0) if product else 0
    qty = data.quantity or 1
    if product:
        if (product.stock or 0) < qty:
            raise HTTPException(status_code=422, detail=f"库存不足（当前: {product.stock or 0}，需要: {qty}）")
        product.stock = (product.stock or 0) - qty
        db.flush()

    unit_price = data.unit_price or 0
    profit = round((unit_price - cost_price) * qty, 2)

    sid = generate_id("PS", db, ProductSale.sale_id)
    s = ProductSale(sale_id=sid, sale_date=date.today(),
                    member_id=data.member_id or "", member_name=data.member_name or "",
                    product_name=data.product_name, quantity=qty,
                    unit_price=unit_price, total_price=data.total_price or 0,
                    cost_price=cost_price, profit=profit,
                    payment_method=data.payment_method or "",
                    operator=data.operator or "", remark=data.remark or "")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/product-sales/{sale_id}")
def delete_product_sale(sale_id: str, request: Request, db: Session = Depends(get_db)):
    s = db.query(ProductSale).filter(ProductSale.sale_id == sale_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="零售记录不存在")

    # 归还库存
    product = db.query(Product).filter(Product.name == s.product_name).first()
    if product:
        product.stock = (product.stock or 0) + (s.quantity or 0)

    # 记录操作日志
    token = request.cookies.get("access_token", "")
    op = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            op = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub", "系统")
        except Exception:
            pass
    record_log(db, op, "delete", "商品零售", sale_id, f"删除零售记录：{sale_id}")
    db.delete(s)
    db.commit()
    return success(message="零售记录已删除")


class VoidRequest(BaseModel):
    reason: str = ""


@router.put("/product-sales/{sale_id}/void")
def void_product_sale(sale_id: str, data: VoidRequest, request: Request, db: Session = Depends(get_db)):
    """作废零售记录（标记作废 + 归还库存）"""
    s = db.query(ProductSale).filter(ProductSale.sale_id == sale_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="零售记录不存在")
    if getattr(s, 'voided', 0):
        raise HTTPException(status_code=400, detail="该记录已作废")
    # 归还库存
    product = db.query(Product).filter(Product.name == s.product_name).first()
    if product:
        product.stock = (product.stock or 0) + (s.quantity or 0)
    # 获取操作人
    token = request.cookies.get("access_token", "")
    operator = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            operator = payload.get("sub", "系统")
        except Exception:
            pass
    s.voided = 1
    s.void_reason = data.reason
    s.void_time = datetime.now()
    s.void_operator = operator
    record_log(db, operator, "void", "商品零售", sale_id, f"作废零售记录：{sale_id}")
    db.commit()
    return success(message="零售记录已作废")


# ═══════════════════════════════════════════
# 购物车模式
# ═══════════════════════════════════════════

class CartItem(BaseModel):
    product_id: str = ""
    product_name: str
    quantity: int = 1
    unit_price: float = 0
    total_price: float = 0


class BatchSaleCreate(BaseModel):
    items: List[CartItem]
    member_id: str = ""
    member_name: str = ""
    payment_method: str = ""
    use_balance: bool = False
    operator: str = ""
    remark: str = ""


@router.get("/members/{member_id}/balance")
def get_member_balance(member_id: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")
    return {
        "member_id": member.member_id,
        "member_name": member.name,
        "balance": float(member.balance or 0)
    }


@router.post("/product-sales/batch")
def batch_create_sales(data: BatchSaleCreate, db: Session = Depends(get_db)):
    if not data.items:
        raise HTTPException(status_code=400, detail="购物车为空")

    grand_total = sum(item.total_price for item in data.items)

    # 先校验所有商品库存
    for item in data.items:
        product = db.query(Product).filter(Product.name == item.product_name).first()
        if product and (product.stock or 0) < (item.quantity or 1):
            raise HTTPException(status_code=400, detail=f"「{item.product_name}」库存不足（当前: {product.stock or 0}，需要: {item.quantity or 1}）")

    if data.use_balance and data.member_id:
        member = db.query(Member).filter(Member.member_id == data.member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="会员不存在")
        if float(member.balance or 0) < grand_total:
            raise HTTPException(status_code=400, detail=f"储值余额不足（余额: ¥{float(member.balance or 0):.2f}，需: ¥{grand_total:.2f}）")
        member.balance = Decimal(str(float(member.balance) - grand_total))
        db.flush()

    created = []
    today_str = date.today().strftime('%Y%m%d')
    base_q = db.query(func.max(ProductSale.sale_id)).filter(ProductSale.sale_id.like(f"PS{today_str}%")).scalar()
    next_seq = (int(base_q[-4:]) + 1) if base_q else 1

    for item in data.items:
        product = db.query(Product).filter(Product.name == item.product_name).first()
        cost_price = float(product.cost_price or 0) if product else 0

        if product:
            product.stock = (product.stock or 0) - (item.quantity or 1)

        unit_price = item.unit_price or 0
        profit = round((unit_price - cost_price) * (item.quantity or 1), 2)

        sid = f"PS{today_str}{next_seq:04d}"
        next_seq += 1
        s = ProductSale(
            sale_id=sid,
            sale_date=date.today(),
            member_id=data.member_id or "",
            member_name=data.member_name or "",
            product_name=item.product_name,
            quantity=item.quantity or 1,
            unit_price=unit_price,
            total_price=item.total_price or 0,
            cost_price=cost_price,
            profit=profit,
            payment_method="储值" if data.use_balance else (data.payment_method or "现金"),
            operator=data.operator or "",
            remark=data.remark or ""
        )
        db.add(s)
        created.append(s)

    db.commit()
    for s in created:
        db.refresh(s)

    return success(
        data={"count": len(created), "total": grand_total, "use_balance": data.use_balance},
        message=f"成功创建 {len(created)} 条零售记录，合计 ¥{grand_total:.2f}",
    )


# ═══════════════════════════════════════════
# 进货入库
# ═══════════════════════════════════════════

def _build_inbound_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无进货记录</div>'
    trs = ""
    for r in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{r.inbound_id}</td>
            <td class="px-4 py-3 text-sm">{r.inbound_date}</td>
            <td class="px-4 py-3">{r.product_name}</td>
            <td class="px-4 py-3 text-sm">x{r.quantity}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (r.unit_cost or 0)}</td>
            <td class="px-4 py-3 text-sm font-medium">{'%.2f' % (r.total_cost or 0)}</td>
            <td class="px-4 py-3 text-sm">{r.supplier or ''}</td>
            <td class="px-4 py-3 text-sm">{r.operator or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/products/inbounds/{r.inbound_id}" hx-target="#inboundTable" hx-confirm="确认删除进货记录？库存将自动回滚。">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">入库编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">商品</th><th class="px-4 py-3">数量</th><th class="px-4 py-3">单价</th><th class="px-4 py-3">总成本</th><th class="px-4 py-3">供应商</th><th class="px-4 py-3">操作员</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/products/inbounds/table", response_class=HTMLResponse)
def inbound_table(db: Session = Depends(get_db)):
    return _build_inbound_table(db.query(StockInbound).order_by(StockInbound.inbound_date.desc()).limit(100).all())


@router.get("/products/inbounds/form-options", response_class=HTMLResponse)
def inbound_form_options(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.name).all()
    opts = ""
    for p in products:
        opts += f'<option value="{p.product_id}" data-name="{p.name}" data-supplier="{p.supplier or ""}" data-cost="{p.cost_price or 0}">{p.name}（库存: {p.stock or 0}）</option>'
    return f'<select id="inboundProduct" class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"><option value="">-- 选择商品 --</option>{opts}</select>'


class InboundCreate(BaseModel):
    product_id: str
    quantity: int
    unit_cost: float = 0
    supplier: str = ""
    inbound_date: str = ""
    operator: str = ""
    remark: str = ""


@router.post("/products/inbounds")
def create_inbound(data: InboundCreate, db: Session = Depends(get_db)):
    if not data.product_id:
        raise HTTPException(status_code=400, detail="请选择商品")

    product = db.query(Product).filter(Product.product_id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    qty = data.quantity or 1
    unit_cost = data.unit_cost or 0
    total_cost = round(qty * unit_cost, 2)

    inbound_date = date.today()
    if data.inbound_date:
        try:
            inbound_date = date.fromisoformat(data.inbound_date)
        except ValueError:
            pass

    iid = generate_id("SI", db, StockInbound.inbound_id)
    rec = StockInbound(
        inbound_id=iid, inbound_date=inbound_date,
        product_id=product.product_id, product_name=product.name,
        quantity=qty, unit_cost=unit_cost, total_cost=total_cost,
        supplier=data.supplier or product.supplier or "",
        operator=data.operator or "", remark=data.remark or ""
    )
    db.add(rec)

    # 增加库存
    product.stock = (product.stock or 0) + qty

    db.commit()
    return success(data={"inbound_id": iid}, message=f"入库成功，{product.name} +{qty}")


@router.delete("/products/inbounds/{inbound_id}")
def delete_inbound(inbound_id: str, request: Request, db: Session = Depends(get_db)):
    rec = db.query(StockInbound).filter(StockInbound.inbound_id == inbound_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="进货记录不存在")

    # 回滚库存
    product = db.query(Product).filter(Product.product_id == rec.product_id).first()
    if product:
        product.stock = max(0, (product.stock or 0) - (rec.quantity or 0))

    # 记录操作日志
    token = request.cookies.get("access_token", "")
    op = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            op = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub", "系统")
        except Exception:
            pass
    record_log(db, op, "delete", "进货记录", inbound_id, f"删除进货记录：{inbound_id}")
    db.delete(rec)
    db.commit()
    return success(message="进货记录已删除，库存已回滚")


# ═══════════════════════════════════════════
# 库存预警 + 利润统计
# ═══════════════════════════════════════════

@router.get("/products/low-stock", response_class=HTMLResponse)
def low_stock_report(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.stock.asc()).all()
    rows = ""
    low_count = 0
    for p in products:
        stock = p.stock or 0
        min_stock = p.min_stock or 0
        if stock > min_stock:
            continue
        low_count += 1
        if stock == 0:
            badge = '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded font-medium">⛔ 缺货</span>'
        elif stock <= min_stock:
            diff = min_stock - stock
            badge = f'<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded font-medium">🔴 库存不足(差{diff})</span>'
        else:
            badge = '<span class="text-xs bg-green-100 text-green-600 px-2 py-0.5 rounded">正常</span>'
        rows += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3">{p.name}</td>
            <td class="px-4 py-3 text-sm">{stock} {p.unit or '个'}</td>
            <td class="px-4 py-3 text-sm">{min_stock}</td>
            <td class="px-4 py-3">{badge}</td>
        </tr>"""

    if not rows:
        return f"""<div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6 text-center text-gray-400 text-sm">全部商品库存正常 ✅</div>"""

    return f"""<div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div class="px-4 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
            <span class="text-sm font-medium text-gray-700">库存预警</span>
            <span class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">{low_count} 项异常</span>
        </div>
        <table class="w-full">
            <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                <tr><th class="px-4 py-3">商品名</th><th class="px-4 py-3">当前库存</th><th class="px-4 py-3">安全库存</th><th class="px-4 py-3">状态</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>"""


@router.get("/products/profit-summary", response_class=HTMLResponse)
def profit_summary(db: Session = Depends(get_db)):
    # 汇总
    total_sales = db.query(func.sum(ProductSale.total_price)).scalar() or 0
    total_profit = db.query(func.sum(ProductSale.profit)).scalar() or 0
    total_cost = float(total_sales) - float(total_profit)
    profit_rate = (float(total_profit) / float(total_sales) * 100) if float(total_sales) > 0 else 0

    # 按商品分组
    rows = db.query(
        ProductSale.product_name,
        func.sum(ProductSale.quantity).label("qty"),
        func.sum(ProductSale.total_price).label("sales"),
        func.sum(ProductSale.profit).label("profit"),
    ).group_by(ProductSale.product_name).order_by(func.sum(ProductSale.profit).desc()).all()

    items_html = ""
    for r in rows:
        rate = (float(r.profit) / float(r.sales) * 100) if float(r.sales) > 0 else 0
        items_html += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3">{r.product_name}</td>
            <td class="px-4 py-3 text-sm">{int(r.qty)}</td>
            <td class="px-4 py-3 text-sm">¥{float(r.sales):,.2f}</td>
            <td class="px-4 py-3 text-sm">¥{float(r.sales) - float(r.profit):,.2f}</td>
            <td class="px-4 py-3 text-sm font-medium {'text-green-600' if float(r.profit) >= 0 else 'text-red-600'}">¥{float(r.profit):,.2f}</td>
            <td class="px-4 py-3 text-sm">{rate:.1f}%</td>
        </tr>"""

    if not items_html:
        return """<div class="text-center py-8 text-gray-400 text-sm">暂无销售数据</div>"""

    return f"""
    <div class="grid grid-cols-4 gap-4 mb-4">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
            <div class="text-xs text-gray-400">总销售额</div>
            <div class="text-xl font-bold text-gray-800 mt-1">¥{float(total_sales):,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
            <div class="text-xs text-gray-400">总成本</div>
            <div class="text-xl font-bold text-orange-600 mt-1">¥{float(total_cost):,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
            <div class="text-xs text-gray-400">总利润</div>
            <div class="text-xl font-bold text-green-600 mt-1">¥{float(total_profit):,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
            <div class="text-xs text-gray-400">利润率</div>
            <div class="text-xl font-bold text-blue-600 mt-1">{profit_rate:.1f}%</div>
        </div>
    </div>
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div class="px-4 py-3 bg-gray-50 border-b border-gray-100">
            <span class="text-sm font-medium text-gray-700">商品利润排行</span>
        </div>
        <table class="w-full">
            <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                <tr><th class="px-4 py-3">商品</th><th class="px-4 py-3">销量</th><th class="px-4 py-3">销售额</th><th class="px-4 py-3">成本</th><th class="px-4 py-3">利润</th><th class="px-4 py-3">利润率</th></tr>
            </thead>
            <tbody>{items_html}</tbody>
        </table>
    </div>"""
