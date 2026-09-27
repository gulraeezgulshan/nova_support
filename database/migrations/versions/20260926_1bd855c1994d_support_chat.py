"""Support chat: conversations and messages

Revision ID: 1bd855c1994d
Revises: 3bc51261ab6a
Create Date: 2026-09-26 21:52:17.404033
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '1bd855c1994d'
down_revision: str | None = '3bc51261ab6a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('chat_conversations',
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=True),
    sa.Column('complaint_id', sa.Uuid(), nullable=True),
    sa.Column('state', sa.String(length=20), nullable=False, server_default='gathering'),
    sa.Column('draft', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    sa.Column('customer_messages', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], name=op.f('fk_chat_conversations_complaint_id_complaints')),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_chat_conversations_customer_id_customers')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_chat_conversations_order_id_orders')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_chat_conversations_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_conversations')),
    sa.UniqueConstraint('complaint_id', name=op.f('uq_chat_conversations_complaint_id'))
    )
    op.create_index(op.f('ix_chat_conversations_customer_id'), 'chat_conversations', ['customer_id'], unique=False)
    op.create_table('chat_messages',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False, server_default='text'),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], name=op.f('fk_chat_messages_conversation_id_chat_conversations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chat_messages'))
    )
    op.create_index(op.f('ix_chat_messages_conversation_id'), 'chat_messages', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_messages_conversation_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index(op.f('ix_chat_conversations_customer_id'), table_name='chat_conversations')
    op.drop_table('chat_conversations')
