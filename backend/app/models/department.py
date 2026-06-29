from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user import User


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    roles: Mapped[List[Role]] = relationship("Role", back_populates="department", lazy="selectin")
    users: Mapped[List[User]] = relationship("User", back_populates="department", foreign_keys="User.department_id", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, name={self.name})>"