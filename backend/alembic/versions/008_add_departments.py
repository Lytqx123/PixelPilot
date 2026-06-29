"""008_add_departments

部门表初始迁移

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008h9i0j1k2l'
down_revision: Union[str, None] = '007g8h9i0j1k'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass