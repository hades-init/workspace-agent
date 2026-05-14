"""Initial revision create messages table

Revision ID: eb1d6153fa97
Revises: 
Create Date: 2026-05-09 00:04:50.158447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb1d6153fa97'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table("messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False),
        sa.Column("from_address", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("received_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_text", sa.String()),
        sa.Column("body_html", sa.String()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("messages")
