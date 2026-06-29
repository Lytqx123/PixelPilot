from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, BigInteger, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SystemTag(Base):
    __tablename__ = "system_tags"
    __table_args__ = (
        UniqueConstraint("tag_type", "tag_value", name="uq_tag_type_value"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tag_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # 'model' | 'region' | 'doc_type'
    tag_value: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<SystemTag(id={self.id}, type={self.tag_type}, value={self.tag_value})>"