"""Storefront: products and shop order fields

Revision ID: 3bc51261ab6a
Revises: a3604f973e34
Create Date: 2026-09-26 21:44:10.490367
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '3bc51261ab6a'
down_revision: str | None = 'a3604f973e34'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Shop order references start at ORD-800001, clear of the dataset and hold-out packs.
    op.execute("CREATE SEQUENCE IF NOT EXISTS order_ref_seq START WITH 800001")
    op.execute("CREATE SEQUENCE IF NOT EXISTS checkout_ref_seq")
    op.create_table('products',
    sa.Column('sku', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('product_line', sa.String(length=40), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('specs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    sa.UniqueConstraint('sku', name=op.f('uq_products_sku'))
    )
    op.create_index(op.f('ix_products_product_line'), 'products', ['product_line'], unique=False)
    op.add_column('orders', sa.Column('product_id', sa.Uuid(), nullable=True))
    op.add_column('orders', sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('orders', sa.Column('checkout_ref', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_orders_checkout_ref'), 'orders', ['checkout_ref'], unique=False)
    op.create_foreign_key(op.f('fk_orders_product_id_products'), 'orders', 'products', ['product_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(op.f('fk_orders_product_id_products'), 'orders', type_='foreignkey')
    op.drop_index(op.f('ix_orders_checkout_ref'), table_name='orders')
    op.drop_column('orders', 'checkout_ref')
    op.drop_column('orders', 'quantity')
    op.drop_column('orders', 'product_id')
    op.drop_index(op.f('ix_products_product_line'), table_name='products')
    op.drop_table('products')
    op.execute("DROP SEQUENCE IF EXISTS checkout_ref_seq")
    op.execute("DROP SEQUENCE IF EXISTS order_ref_seq")
