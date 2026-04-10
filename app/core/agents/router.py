"""Heuristic agent router (AI-6.3).

Scores incoming prompts against three keyword signal sets - transit,
knowledge, vault - and returns the AgentName of the best-fit domain.
Ties or zero-score prompts fall back to "unified".

This module is intentionally LLM-free: scoring is regex-based, runs in
microseconds, and mirrors the design of ``app/core/agents/routing.py``
(model-tier classifier) and ``app/knowledge/router.py`` (RAG signal
scorer). It is the upstream classifier for the BaseAgentService pipeline.
"""

from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

from app.core.agents.schemas import AgentName
from app.core.logging import get_logger

logger = get_logger(__name__)


# Keyword signal sets. Each entry is a regex (case-insensitive). Latvian
# stems are written WITHOUT trailing word boundary so inflected forms
# match (`maršrut` -> `maršruti`, `maršrutu`, `maršrutā`). Both diacritized
# and undiacriticized variants are listed because users frequently type
# without diacritics (`kavejas` instead of `kavējas`).

_TRANSIT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"maršrut",
        r"marsrut",
        r"pietur",
        r"autobus",
        r"kavēj",
        r"kavej",
        r"reis",
        r"grafik",
        r"vadītāj",
        r"vaditaj",
        r"transport",
        r"\broute\b",
        r"\broutes\b",
        r"\bstop\b",
        r"\bstops\b",
        r"\bdelay\b",
        r"\bdelays\b",
        r"\bdelayed\b",
        r"\bbus\b",
        r"\bbuses\b",
        r"\bschedule\b",
        r"\bschedules\b",
        r"\bdeparture\b",
        r"\bdepartures\b",
        r"\barrival\b",
        r"\bdriver\b",
        r"\bdrivers\b",
        r"\bvehicle\b",
        r"\bvehicles\b",
    )
)

_KNOWLEDGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"dokument",
        r"noteikum",
        r"procedūr",
        r"procedur",
        r"regul",
        r"likum",
        r"instrukcij",
        r"\bSOP\b",
        r"\bpolicy\b",
        r"\bpolicies\b",
        r"\bdocument\b",
        r"\bdocuments\b",
        r"\bprocedure\b",
        r"\bprocedures\b",
        r"\bregulation\b",
        r"\bregulations\b",
        r"\bcompliance\b",
        r"\bguideline\b",
        r"\bguidelines\b",
    )
)

_VAULT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvault\b",
        r"\bobsidian\b",
        r"piezīm",
        r"piezim",
        r"\bnote\b",
        r"\bnotes\b",
        r"\bfolder\b",
        r"\bfolders\b",
        r"\btag\b",
        r"\btags\b",
        r"\bbacklink\b",
        r"\bbacklinks\b",
        r"\bmarkdown\b",
    )
)


class RoutingDecision(NamedTuple):
    """Result of a single classification call."""

    domain: AgentName
    transit_score: int
    knowledge_score: int
    vault_score: int


def _score(prompt: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    """Count how many distinct patterns match anywhere in ``prompt``."""
    return sum(1 for pat in patterns if pat.search(prompt))


def _prompt_hash(prompt: str) -> str:
    """Short SHA-256 prefix for log correlation without leaking content."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


class AgentRouter:
    """Heuristic prompt -> domain agent classifier.

    Usage:
        router = AgentRouter()
        decision = router.classify("Kuri maršruti kavējas?")
        # decision.domain == "transit"
    """

    def classify(self, prompt: str) -> RoutingDecision:
        """Score the prompt and return the best-fit ``AgentName``.

        Tie-breaking rules (in order):

        1. If the maximum score is 0, return ``"unified"``.
        2. If two or more domains share the maximum score, return
           ``"unified"`` (treat as cross-domain).
        3. Otherwise return the unique top-scoring domain.

        Args:
            prompt: Raw user prompt text.

        Returns:
            ``RoutingDecision`` with the chosen domain and per-domain scores.
        """
        text = prompt.strip()
        if not text:
            decision = RoutingDecision("unified", 0, 0, 0)
            self._log(text, decision)
            return decision

        transit = _score(text, _TRANSIT_PATTERNS)
        knowledge = _score(text, _KNOWLEDGE_PATTERNS)
        vault = _score(text, _VAULT_PATTERNS)

        scores: dict[AgentName, int] = {
            "transit": transit,
            "knowledge": knowledge,
            "vault": vault,
        }
        top_score = max(scores.values())

        domain: AgentName
        if top_score == 0:
            domain = "unified"
        else:
            winners: list[AgentName] = [
                name for name, score in scores.items() if score == top_score
            ]
            domain = winners[0] if len(winners) == 1 else "unified"

        decision = RoutingDecision(
            domain=domain,
            transit_score=transit,
            knowledge_score=knowledge,
            vault_score=vault,
        )
        self._log(text, decision)
        return decision

    def route(self, prompt: str) -> AgentName:
        """Convenience wrapper that returns only the chosen ``AgentName``.

        Args:
            prompt: Raw user prompt text.

        Returns:
            The selected ``AgentName`` for downstream agent resolution.
        """
        return self.classify(prompt).domain

    @staticmethod
    def _log(prompt: str, decision: RoutingDecision) -> None:
        logger.info(
            "agent.router.decision",
            prompt_hash=_prompt_hash(prompt),
            prompt_length=len(prompt),
            domain=decision.domain,
            transit_score=decision.transit_score,
            knowledge_score=decision.knowledge_score,
            vault_score=decision.vault_score,
        )


_singleton: AgentRouter | None = None


def get_agent_router() -> AgentRouter:
    """Return the process-wide ``AgentRouter`` singleton."""
    global _singleton
    if _singleton is None:
        _singleton = AgentRouter()
    return _singleton
