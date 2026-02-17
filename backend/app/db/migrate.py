"""
Standalone migration script.

Creates all tables in the database.
For production, replace this with Alembic.

Usage: python -m app.db.migrate
"""

import asyncio
from app.db.session import engine
from app.models.db_models import Base


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("All tables created successfully.")


if __name__ == "__main__":
    asyncio.run(create_tables())
