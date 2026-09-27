"""contact and newsletter

Revision ID: ef4cc7330a25
Revises: f77a1bb0033b
Create Date: 2026-09-27 12:54:53.271439
"""
from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op


revision: str = 'ef4cc7330a25'
down_revision: str | None = 'f77a1bb0033b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS enquiry_ref_seq")
    op.create_table('newsletter_subscribers',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('source', sa.String(length=40), server_default='footer', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('email', name=op.f('pk_newsletter_subscribers'))
    )
    op.create_table('enquiries',
    sa.Column('ref', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('topic', sa.String(length=30), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='new', nullable=False),
    sa.Column('handled_by_id', sa.Uuid(), nullable=True),
    sa.Column('handled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('complaint_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], name=op.f('fk_enquiries_complaint_id_complaints')),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_enquiries_customer_id_customers')),
    sa.ForeignKeyConstraint(['handled_by_id'], ['users.id'], name=op.f('fk_enquiries_handled_by_id_users')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_enquiries_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_enquiries')),
    sa.UniqueConstraint('ref', name=op.f('uq_enquiries_ref'))
    )
    op.create_index(op.f('ix_enquiries_status'), 'enquiries', ['status'], unique=False)
    op.create_index(op.f('ix_enquiries_topic'), 'enquiries', ['topic'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_enquiries_topic'), table_name='enquiries')
    op.drop_index(op.f('ix_enquiries_status'), table_name='enquiries')
    op.drop_table('enquiries')
    op.drop_table('newsletter_subscribers')
    op.execute("DROP SEQUENCE IF EXISTS enquiry_ref_seq")
