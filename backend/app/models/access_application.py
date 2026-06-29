from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import String, BigInteger, SmallInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document import Document


class AccessApplication(Base):
    __tablename__ = "access_applications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)  # 0=待审核, 1=已通过, 2=已拒绝
    reviewer_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    assigned_reviewer_ids: Mapped[Optional[List[int]]] = mapped_column(JSONB, nullable=True)  # 被指定的审核员/管理员ID列表
    expected_hours: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)  # 申请人期望的授权时长（小时），0=永久
    review_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    applicant: Mapped[User] = relationship("User", foreign_keys=[applicant_id], lazy="joined")
    document: Mapped[Document] = relationship("Document", lazy="joined")
    reviewer: Mapped[Optional[User]] = relationship("User", foreign_keys=[reviewer_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<AccessApplication(id={self.id}, status={self.status})>"