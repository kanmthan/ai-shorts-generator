"""Refresh token model used for JWT session rotation."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base, CreatedAtMixin


class RefreshToken(Base, CreatedAtMixin):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token = Column(String(512), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False, server_default="false")

    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.revoked}>"
