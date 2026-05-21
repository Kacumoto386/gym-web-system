# -*- coding: utf-8 -*-
"""
编号生成器
V3.0.0
"""
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func


def generate_id(prefix: str, db: Session, column) -> str:
    """生成编号：前缀 + 年月日 + 4位序号
    
    Args:
        prefix: 编号前缀 (M=会员, S=员工, C=课程, etc.)
        db: 数据库会话
        column: 对应模型列（用于查询当前最大序号）
    
    Returns:
        如: M202605080001
    """
    today = datetime.date.today()
    date_str = today.strftime("%Y%m%d")
    prefix_match = f"{prefix}{date_str}%"
    
    max_id = db.query(func.max(column)).filter(column.like(prefix_match)).scalar()
    
    if max_id:
        seq = int(max_id[-4:]) + 1
    else:
        seq = 1
    
    return f"{prefix}{date_str}{seq:04d}"
