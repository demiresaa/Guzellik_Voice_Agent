"""
Shared Database Module

Provides database utilities for all services:
- Async SQLAlchemy engine
- Session management
- Base models
- Generic repository pattern
"""

from .database import init_database, get_engine, get_async_session
from .base import Base, TimestampMixin
from .repository import BaseRepository

__all__ = [
    "init_database",
    "get_engine",
    "get_async_session",
    "Base",
    "TimestampMixin",
    "BaseRepository",
]
