# -*- coding: utf-8 -*-
"""V3: 次卡名称包含总次数+赠送"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.models.models import MembershipCard

db = SessionLocal()
cards = db.query(MembershipCard).filter(
    MembershipCard.total_classes > 0,
).all()
count = 0
for c in cards:
    ct = (c.card_type or "").strip()
    total = c.total_classes or 0
    bonus = c.bonus_classes or 0
    if not total:
        continue
    # 优先用已有 card_name 做基础名（去掉可能含的旧次数后缀）
    base = c.card_name or ct or "次卡"
    # 去掉旧格式的 " X次" 或 " X+Y次" 后缀
    import re
    base_clean = re.sub(r'\s+\d+\+?\d*次$', '', base).strip()
    if not base_clean:
        base_clean = ct or "次卡"

    if bonus:
        new_name = "{} {}+{}次".format(base_clean, total, bonus)
    else:
        new_name = "{} {}次".format(base_clean, total)

    if c.card_name != new_name:
        c.card_name = new_name
        count += 1

db.commit()
print("OK - {}次卡 card_name updated".format(count))
db.close()
