# -*- coding: utf-8 -*-
"""
商品零售 API 路由 + HTMX HTML 片段端点
V3.1.2 — 购物车模式
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from decimal import Decimal
from backend.database import get_db
from backend.models.models import Product, ProductSale, Member
from backend.services.id_gen import generate_id
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["商品零售"])


# ═══════════════════════════════════════════
# 商品管理
# ═══════════════════════════════════════════

def _build_product_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无商品</div>'
    trs = ""
    for p in rows:
        stock_cls = "text-red-500" if (p.stock or 0) <= 5 else "text-gray-700"
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{p.product_id}</td>
            <td class="px-4 py-3">{p.name}</td>
            <td class="px-4 py-3 text-sm">{p.category or ''}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (p.cost_price or 0)}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (p.selling_price or 0)}</td>
            <td class="px-4 py-3 text-sm <stock_cls>">{p.stock or 0} {p.unit or '个'}</td>
            <td class="px-4 py-3 text-sm">{p.supplier or ''}</td>
            <td class="px-4 py-3 text-sm">
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
                stock=data.stock or 0, unit=data.unit or "个",
                supplier=data.supplier or "", remark=data.remark or "")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/products/{product_id}")
def delete_product(product_id: str, request: Request, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.product_id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    db.delete(p)
    db.commit()

    return {"success": True, "message": f"商品已删除"}


# ═══════════════════════════════════════════
# 商品零售记录
# ═══════════════════════════════════════════

def _build_sale_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无零售记录</div>'
    trs = ""
    for s in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{s.sale_id}</td>
            <td class="px-4 py-3 text-sm">{s.sale_date}</td>
            <td class="px-4 py-3">{s.member_name or ''}</td>
            <td class="px-4 py-3">{s.product_name}</td>
            <td class="px-4 py-3 text-sm">x{s.quantity}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (s.unit_price or 0)}</td>
            <td class="px-4 py-3 text-sm font-medium">{'%.2f' % (s.total_price or 0)}</td>
            <td class="px-4 py-3 text-sm">{s.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/product-sales/{s.sale_id}" hx-target="#productSaleTable" hx-confirm="确认删除？">删除</button>
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
    return _build_sale_table(db.query(ProductSale).order_by(ProductSale.sale_date.desc()).limit(100).all())


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
    sid = generate_id("PS", db, ProductSale.sale_id)
    s = ProductSale(sale_id=sid, sale_date=date.today(),
                    member_id=data.member_id or "", member_name=data.member_name or "",
                    product_name=data.product_name, quantity=data.quantity or 1,
                    unit_price=data.unit_price or 0, total_price=data.total_price or 0,
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
    db.delete(s)
    db.commit()

    return {"success": True, "message": "零售记录已删除"}


# ═══════════════════════════════════════════
# 购物车模式（V3.1.2 新增）
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
    """获取会员储值余额"""
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
    """批量创建零售记录（购物车提交）"""
    if not data.items:
        raise HTTPException(status_code=400, detail="购物车为空")

    grand_total = sum(item.total_price for item in data.items)

    # 如果使用储值，校验余额并扣减
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
        sid = f"PS{today_str}{next_seq:04d}"
        next_seq += 1
        s = ProductSale(
            sale_id=sid,
            sale_date=date.today(),
            member_id=data.member_id or "",
            member_name=data.member_name or "",
            product_name=item.product_name,
            quantity=item.quantity or 1,
            unit_price=item.unit_price or 0,
            total_price=item.total_price or 0,
            payment_method="储值" if data.use_balance else (data.payment_method or "现金"),
            operator=data.operator or "",
            remark=data.remark or ""
        )
        db.add(s)
        created.append(s)

    db.commit()
    for s in created:
        db.refresh(s)

    return {
        "success": True,
        "count": len(created),
        "total": grand_total,
        "use_balance": data.use_balance,
        "message": f"成功创建 {len(created)} 条零售记录，合计 ¥{grand_total:.2f}"
    }
