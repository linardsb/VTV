"""Data access layer for agent skills."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.skills.models import AgentSkill
from app.skills.schemas import SkillCreate, SkillUpdate


class SkillRepository:
    """Database operations for agent skills."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, skill_id: int) -> AgentSkill | None:
        result = await self.db.execute(select(AgentSkill).where(AgentSkill.id == skill_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AgentSkill | None:
        result = await self.db.execute(select(AgentSkill).where(AgentSkill.name == name))
        return result.scalar_one_or_none()

    async def find(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> list[AgentSkill]:
        query = select(AgentSkill)
        if category is not None:
            query = query.where(AgentSkill.category == category)
        if is_active is not None:
            query = query.where(AgentSkill.is_active == is_active)
        query = (
            query.order_by(AgentSkill.priority.desc(), AgentSkill.name).offset(offset).limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        category: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        query = select(func.count()).select_from(AgentSkill)
        if category is not None:
            query = query.where(AgentSkill.category == category)
        if is_active is not None:
            query = query.where(AgentSkill.is_active == is_active)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def list_active(self) -> list[AgentSkill]:
        query = (
            select(AgentSkill)
            .where(AgentSkill.is_active == True)  # noqa: E712
            .order_by(AgentSkill.priority.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, data: SkillCreate, created_by_id: int | None = None) -> AgentSkill:
        skill = AgentSkill(**data.model_dump(), created_by_id=created_by_id)
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def update(self, skill: AgentSkill, data: SkillUpdate) -> AgentSkill:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(skill, field, value)
        await self.db.commit()
        await self.db.refresh(skill)
        return skill

    async def delete(self, skill: AgentSkill) -> None:
        await self.db.delete(skill)
        await self.db.commit()
