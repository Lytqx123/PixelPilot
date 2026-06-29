"""010_add_is_public_to_all_to_documents

添加全局公开字段

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '010j1k2l3m4n'
down_revision: Union[str, None] = '009i0j1k2l3m'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass