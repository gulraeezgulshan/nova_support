"""Product images

Revision ID: f77a1bb0033b
Revises: 1bd855c1994d
Create Date: 2026-09-27 12:23:32.507942
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f77a1bb0033b'
down_revision: str | None = '1bd855c1994d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('product_images',
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('media_type', sa.String(length=40), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_images_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_product_images'))
    )
    op.create_index(op.f('ix_product_images_product_id'), 'product_images', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_images_product_id'), table_name='product_images')
    op.drop_table('product_images')
