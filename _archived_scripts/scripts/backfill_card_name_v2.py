# -*- coding: utf-8 -*-
"""V2: 改进回填逻辑 - 处理无 card_type 的旧卡"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.models.models import MembershipCard

db = SessionLocal()
cards = db.query(MembershipCard).filter(
    (MembershipCard.card_name == None) | (MembershipCard.card_name == "") | (MembershipCard.card_name == "会籍卡")
).all()
count = 0
for c in cards:
    name = None
    if c.card_name and c.card_name != "会籍卡":
        continue  # skip already okay
    ct = (c.card_type or "").strip()

    if c.is_product == 1:
        # 卡产品：用 remark
        name = c.remark or ""
    elif ct:
        if "次卡" in ct:
            total = c.total_classes or 0
            name = "{} {}次".format(ct, total) if total else ct
        elif "现金" in ct:
            name = "现金卡"
        else:
            days = c.duration_days or 0
            name = "{} {}天".format(ct, days) if days else ct
    else:
        # 无 card_type：通过日期推断
        price = float(c.price or 0)
        if c.end_date and c.start_date:
            actual_days = (c.end_date - c.start_date).days
            if actual_days > 0:
                if actual_days <= 31:    name = "月卡 ¥{:.0f}".format(price)
                elif actual_days <= 93:  name = "季卡 ¥{:.0f}".format(price)
                elif actual_days <= 366: name = "年卡 ¥{:.0f}".format(price)
                else:                    name = "长期卡 ¥{:.0f}".format(price)
        if not name:
            name = "会籍卡 ¥{:.0f}".format(price) if price else "会籍卡"

    if name:
        c.card_name = name
        count += 1

db.commit()
print("OK - {} cards backfilled (v2)".format(count))
db.close()
