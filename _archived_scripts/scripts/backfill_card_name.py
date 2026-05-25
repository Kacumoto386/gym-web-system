# -*- coding: utf-8 -*-
"""回填现有会籍卡的 card_name 字段"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.models.models import MembershipCard

db = SessionLocal()
cards = db.query(MembershipCard).filter(
    (MembershipCard.card_name == None) | (MembershipCard.card_name == "")
).all()
count = 0
for c in cards:
    name = ""
    if c.is_product == 1:
        # 卡产品：用 remark
        name = c.remark or ""
    else:
        # 已售卡：优先从 remark 提取（"来自产品: xxx"），否则拼 card_type
        if c.remark and not c.remark.startswith("来自产品"):
            name = c.remark
        if not name and c.card_type:
            ct = c.card_type.strip()
            if "次卡" in ct or "次" in ct:
                total = c.total_classes or 0
                name = "{} {}次".format(ct, total) if total else ct
            elif "现金" in ct:
                name = "现金卡"
            else:
                name = "{} {}天".format(ct, c.duration_days or 0) if c.duration_days else ct
        if not name:
            name = "会籍卡"
    if name:
        c.card_name = name
        count += 1

db.commit()
print("OK - {} cards backfilled".format(count))
db.close()
