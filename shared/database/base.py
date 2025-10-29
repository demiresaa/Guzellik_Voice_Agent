"""
shared/database/base.py

Base Database Models

Provides base classes for SQLAlchemy models.
"""

from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TimestampMixin:
    """
    Mixin for created_at and updated_at timestamps.

    Usage:
        class User(Base, TimestampMixin):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Record creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
        comment="Record last update timestamp"
    )
