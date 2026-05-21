# -*- coding: utf-8 -*-
"""
自动编号生成器
"""
from sqlalchemy import func
from datetime import date


def generate_id(db, model_class, id_field, prefix="", length=4):
    """生成自动编号
    
    Args:
        db: Session
        model_class: ORM Model 类
        id_field: ID 字段名 (如 record_id, sale_id)
        prefix: 编号前缀 (如 CR, SA)
        length: 序号长度 (4位 = 0001)
    
    Returns:
        新编号字符串: {prefix}{日期}{序号}
    """
    today = date.today()
    date_part = today.strftime("%Y%m%d")
    
    # 查找当天最大的序号
    base_pattern = f"{prefix}{date_part}%"
    max_id = (
        db.query(func.max(getattr(model_class, id_field)))
        .filter(getattr(model_class, id_field).like(base_pattern))
        .scalar()
    )
    
    if max_id:
        seq = int(max_id[-length:]) + 1
    else:
        seq = 1
    
    return f"{prefix}{date_part}{seq:0{length}d}"
