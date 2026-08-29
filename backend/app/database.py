"""Database engine, session factory and FastAPI dependency.

The connection string is read from the ``DATABASE_URL`` environment variable so
that no secret is ever hard-coded.  A local development default is provided for
convenience only.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/ai_shorts_generator"

DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

if DATABASE_URL == DEFAULT_DATABASE_URL:
    logger.warning(
        "DATABASE_URL is not set; falling back to the local development default."
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and guarantee it is closed afterwards."""

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
