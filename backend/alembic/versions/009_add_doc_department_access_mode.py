"""009_add_doc_department_access_mode

添加文档部门访问模式字段

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '009i0j1k2l3m'
down_revision: Union[str, None] = '008h9i0j1k2l'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass