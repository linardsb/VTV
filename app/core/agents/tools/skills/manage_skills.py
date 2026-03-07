"""Agent tool for managing operational skills.

Allows the agent to list available skills and create new ones
when dispatchers describe procedures worth remembering.
"""

from __future__ import annotations

import json

from pydantic_ai import RunContext

from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.skills.schemas import SkillCreate
from app.skills.service import SkillService

logger = get_logger(__name__)

_VALID_CATEGORIES = ("transit_ops", "procedures", "glossary", "reporting")


async def manage_agent_skills(
    ctx: RunContext[UnifiedDeps],
    action: str,
    name: str | None = None,
    description: str | None = None,
    content: str | None = None,
    category: str | None = None,
) -> str:
    """Manage operational knowledge skills that guide your responses.

    WHEN TO USE: When a dispatcher describes a repeatable procedure worth
    remembering ("We always check X before doing Y"), or when asked about
    available operational procedures, protocols, or terminology. Also use
    when asked to list what you know about operations.

    WHEN NOT TO USE: For one-time information lookups. Use the knowledge
    base (search_knowledge_base) for existing documents and policies.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        action: "list" to show active skills, "create" to add a new skill.
        name: Skill name (required for create, max 100 chars).
        description: Short description (required for create, max 500 chars).
        content: Skill content text (required for create, max 10000 chars).
        category: One of "transit_ops", "procedures", "glossary", "reporting".
            Defaults to "transit_ops" for create.

    Returns:
        JSON string with operation results.
    """
    _settings = ctx.deps.settings
    _ = _settings  # Referenced per convention

    logger.info("agent.skills.manage_started", action=action)

    try:
        if action == "list":
            return await _list_skills()
        if action == "create":
            return await _create_skill(name, description, content, category)
        return json.dumps({"error": f"Unknown action: {action}. Use 'list' or 'create'."})
    except Exception as e:
        logger.error(
            "agent.skills.manage_failed",
            exc_info=True,
            action=action,
            error=str(e),
        )
        return f"Skill management error: {e}"


async def _list_skills() -> str:
    """List all active skills."""
    async with AsyncSessionLocal() as db:
        service = SkillService(db)
        skills = await service.repository.list_active()

    result = {
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "priority": s.priority,
            }
            for s in skills
        ],
        "count": len(skills),
    }

    logger.info("agent.skills.list_completed", count=len(skills))
    return json.dumps(result, ensure_ascii=False)


async def _create_skill(
    name: str | None,
    description: str | None,
    content: str | None,
    category: str | None,
) -> str:
    """Create a new skill (inactive by default — requires admin activation)."""
    if not name or not description or not content:
        return json.dumps(
            {"error": "name, description, and content are required for creating a skill."}
        )

    # Enforce content length limit to prevent oversized skill injection
    if len(content) > 5000:
        return json.dumps({"error": "Skill content exceeds 5000 character limit."})

    effective_category = category if category in _VALID_CATEGORIES else "transit_ops"

    async with AsyncSessionLocal() as db:
        service = SkillService(db)
        data = SkillCreate(
            name=name,
            description=description,
            content=content,
            category=effective_category,
        )
        skill_response = await service.create_skill(data)

        # Agent-created skills start inactive — require admin activation via UI/API
        from sqlalchemy import update

        from app.skills.models import AgentSkill as SkillModel

        await db.execute(
            update(SkillModel).where(SkillModel.id == skill_response.id).values(is_active=False)
        )
        await db.commit()

    logger.info(
        "agent.skills.create_completed",
        skill_id=skill_response.id,
        name=name,
    )
    return json.dumps(
        {
            "created": True,
            "skill_id": skill_response.id,
            "name": name,
            "requires_activation": True,
            "message": f"Skill '{name}' created (inactive). An admin must activate it before it takes effect.",
        }
    )
