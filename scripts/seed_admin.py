"""Create admin user directly in the database.

Reads DEMO_USER_PASSWORD from env so local dev, CI, and the backend's
own seed path (app.auth.service.AuthService.seed_demo_users) share a
single source of truth for the admin password. Falls back to 'admin'
for legacy callers that don't set the env var.

ON CONFLICT DO NOTHING — re-running after the user exists is a no-op
so this is safe to call unconditionally after services are healthy.
"""

import asyncio
import os

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def go() -> None:
    password = os.environ.get("DEMO_USER_PASSWORD", "admin")
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(engine, class_=AsyncSession)
    pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    # DO UPDATE not DO NOTHING: if anything else (tests, auto-seed, a previous
    # CI run with stale volume) created the admin user with a different
    # password, the seed script must win. Otherwise the DB keeps whatever was
    # there first and Playwright auth.setup silently fails with 401.
    sql = (
        "INSERT INTO users (email, hashed_password, name, role, is_active, failed_attempts, created_at, updated_at)"
        " VALUES (:e, :p, :n, :r, true, 0, now(), now())"
        " ON CONFLICT (email) DO UPDATE SET"
        "   hashed_password = EXCLUDED.hashed_password,"
        "   failed_attempts = 0,"
        "   locked_until = NULL,"
        "   is_active = true,"
        "   updated_at = now()"
    )
    async with Session() as s:
        await s.execute(text(sql), {"e": "admin@vtv.lv", "p": pw, "n": "Admin", "r": "admin"})
        await s.commit()
        print(f"Admin user ensured: admin@vtv.lv (password length {len(password)})")
    await engine.dispose()


asyncio.run(go())
