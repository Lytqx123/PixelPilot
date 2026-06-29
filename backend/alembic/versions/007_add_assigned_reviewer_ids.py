"""007_add_assigned_reviewer_ids

Revision ID: 007g8h9i0j1k
Revises: 006f7g8h9i0j
Create Date: 2026-04-20 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007g8h9i0j1k'
down_revision: Union[str, None] = '006f7g8h9i0j'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass