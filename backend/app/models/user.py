"""User account model."""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base, CreatedAtMixin

# Allowed values for ``oauth_provider`` (NULL means a local email/password user).
OAUTH_PROVIDERS = ("google",)


class User(Base, CreatedAtMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    # Nullable: OAuth-only users never set a password.
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    is_verified = Column(Boolean, nullable=False, default=False, server_default="false")
    oauth_provider = Column(String(50), nullable=True)
    avatar_url = Column(String(1024), nullable=True)

    projects = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    render_jobs = relationship(
        "RenderJob",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} email={self.email!r}>"
