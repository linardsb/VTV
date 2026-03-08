"""Create admin user directly in the database."""

import asyncio
import os

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def go() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(engine, class_=AsyncSession)
    pw = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()
    sql = (
        "INSERT INTO users (email, hashed_password, full_name, role, is_active)"
        " VALUES (:e, :p, :n, :r, true)"
        " ON CONFLICT (email) DO NOTHING"
    )
    async with Session() as s:
        await s.execute(text(sql), {"e": "admin@vtv.lv", "p": pw, "n": "Admin", "r": "admin"})
        await s.commit()
        print("Admin user created: admin@vtv.lv / admin")
    await engine.dispose()


asyncio.run(go())
