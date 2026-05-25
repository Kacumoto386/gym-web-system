"""测试会员 PUT 含出生日期的错误"""
import sys
sys.path.insert(0, 'C:/Users/12225/.openclaw/workspace/projects/gym-web-system')

# 直接使用数据库测试
from backend.database import SessionLocal
from backend.models.models import Member
from datetime import date
import traceback

db = SessionLocal()
try:
    member = db.query(Member).filter(Member.member_id == 'M20260507001').first()
    print(f'Testing member: {member.member_id}')

    old_name = member.name
    try:
        # 模拟 Form 参数
        birth_date_str = '1990-05-01'
        
        # 直接按照 update_member 的代码执行
        update_data = {
            "name": "test_birth",
            "gender": "男",
            "phone": "13800138005",
            "level": "普通",
            "staff_id": "",
            "staff_name": "",
            "store_id": "",
            "wristband_id": "",
        }
        for key, val in update_data.items():
            if val is not None and val != "":
                setattr(member, key, val)

        # 单独处理出生日期
        if birth_date_str:
            try:
                member.birth_date = date.fromisoformat(str(birth_date_str))
                print(f'  set birth_date = {member.birth_date}')
            except ValueError as ve:
                print(f'  ValueError: {ve}')

        db.commit()
        db.refresh(member)
        print(f'  After: name={member.name}, birth_date={member.birth_date}')
        print('  SUCCESS')
    except Exception as e:
        print(f'  ERROR during update: {type(e).__name__}: {e}')
        traceback.print_exc()
    finally:
        member.name = old_name
        db.commit()
finally:
    db.close()
