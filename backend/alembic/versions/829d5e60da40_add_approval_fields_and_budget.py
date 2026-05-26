"""add_approval_fields_and_budget

Revision ID: 829d5e60da40
Revises: 13fc4fb75d63
Create Date: 2026-05-26 15:28:51.936278
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '829d5e60da40'
down_revision: Union[str, None] = '13fc4fb75d63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 创建预算表
    op.create_table('budget',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('budget_id', sa.String(length=20), nullable=False, comment='预算编号'),
        sa.Column('month', sa.String(length=7), nullable=False, comment='预算月份(YYYY-MM)'),
        sa.Column('category', sa.String(length=50), nullable=False, comment='预算类别'),
        sa.Column('type', sa.String(length=10), nullable=False, comment='类型(income/expense)'),
        sa.Column('planned_amount', sa.DECIMAL(precision=10, scale=2), nullable=True, comment='预算金额'),
        sa.Column('note', sa.Text(), nullable=True, comment='备注'),
        sa.Column('store_id', sa.String(length=20), nullable=True, comment='门店编号'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('budget_id')
    )

    # 2. 支出表添加审核字段
    with op.batch_alter_table('finance_expense', schema=None) as batch_op:
        batch_op.add_column(sa.Column('approval_status', sa.String(length=10),
                            nullable=True, server_default='已通过',
                            comment='审核状态(待审核/已通过/已驳回)'))
        batch_op.add_column(sa.Column('approver', sa.String(length=50),
                            nullable=True, comment='审核人'))
        batch_op.add_column(sa.Column('approve_time', sa.DateTime(),
                            nullable=True, comment='审核时间'))


def downgrade() -> None:
    with op.batch_alter_table('finance_expense', schema=None) as batch_op:
        batch_op.drop_column('approve_time')
        batch_op.drop_column('approver')
        batch_op.drop_column('approval_status')

    op.drop_table('budget')
