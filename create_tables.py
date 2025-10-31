"""
Create database tables for Conversation Agent Service.

Run this script once to initialize the database schema.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from shared.database.base import Base
from shared.common.config import get_settings

# Import all models to register them with Base
from services.conversation_agent_service.app.models.conversation import Conversation, Message


async def create_tables():
    """Create all database tables."""
    settings = get_settings()

    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True  # Show SQL statements
    )

    print("Creating database tables...")

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Database tables created successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
