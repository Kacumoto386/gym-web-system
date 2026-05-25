# -*- coding: utf-8 -*-
"""添加 membership_card.card_name 列"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import engine
from sqlalchemy import text

conn = engine.connect()
try:
    conn.execute(text("ALTER TABLE membership_card ADD COLUMN card_name VARCHAR(100) DEFAULT ''"))
    conn.commit()
    print("OK - card_name column added")
except Exception as e:
    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
        print("INFO - card_name column already exists, skip")
    else:
        print(f"WARN: {e}")
conn.close()
