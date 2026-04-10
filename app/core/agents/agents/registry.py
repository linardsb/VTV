"""Per-agent singleton registry for the ``ChatCompletionRequest.agent`` selector.

The registry resolves the ``agent`` field on the incoming chat request to a
concrete ``BaseAgentService`` subclass instance. The unified fallback is
delegated to ``get_agent_service()`` so the existing ``AgentService``
singleton lifecycle is unchanged; only the three new domain agents are owned
here.
"""

from __future__ import annotations

from app.core.agents.agents.knowledge import KnowledgeAgent
from app.core.agents.agents.transit import TransitAgent
from app.core.agents.agents.vault import VaultAgent
from app.core.agents.base import BaseAgentService
from app.core.agents.schemas import AgentName
from app.core.agents.service import get_agent_service
from app.core.logging import get_logger

logger = get_logger(__name__)

_transit: TransitAgent | None = None
_knowledge: KnowledgeAgent | None = None
_vault: VaultAgent | None = None


def get_agent_by_name(name: AgentName) -> BaseAgentService:
    """Resolve a per-domain agent singleton.

    Args:
        name: One of ``"unified"``, ``"transit"``, ``"knowledge"``, ``"vault"``.
            Pydantic validates the literal at the HTTP layer, so unknown
            values never reach this function in normal flow.

    Returns:
        A ``BaseAgentService`` instance. For ``"unified"`` this is the
        existing ``AgentService`` singleton; the three domain agents are
        instantiated lazily on first use.
    """
    global _transit, _knowledge, _vault
    if name == "unified":
        return get_agent_service()
    if name == "transit":
        if _transit is None:
            _transit = TransitAgent()
        return _transit
    if name == "knowledge":
        if _knowledge is None:
            _knowledge = KnowledgeAgent()
        return _knowledge
    if name == "vault":
        if _vault is None:
            _vault = VaultAgent()
        return _vault
    msg = f"Unknown agent name: {name}"  # unreachable: Literal-validated
    raise ValueError(msg)


async def close_all_agents() -> None:
    """Close per-domain agent HTTP clients on shutdown.

    Does NOT touch the unified ``AgentService`` — that singleton is closed by
    ``close_agent_service()`` in the lifespan handler. Calling both here
    would double-close the same client.
    """
    global _transit, _knowledge, _vault
    for label, instance in (
        ("transit", _transit),
        ("knowledge", _knowledge),
        ("vault", _vault),
    ):
        if instance is None:
            continue
        try:
            await instance.close()
        except Exception:
            logger.warning("agent.registry.close_failed", agent=label, exc_info=True)
    _transit = None
    _knowledge = None
    _vault = None


__all__ = ["close_all_agents", "get_agent_by_name", "logger"]
