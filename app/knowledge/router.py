"""RAG query router - determines if a query needs knowledge base retrieval.

Signal-based scoring with zero latency overhead (no LLM calls).
Transit, schedule, vault, and real-time queries skip RAG entirely.
Knowledge, policy, SOP, and document queries trigger RAG.
"""

import hashlib
import re
from typing import NamedTuple

from app.core.logging import get_logger

logger = get_logger(__name__)


class RoutingDecision(NamedTuple):
    """Result of RAG routing classification."""

    needs_rag: bool
    rag_score: int
    skip_score: int


# Signals that indicate the query needs document retrieval.
# No trailing \b — Latvian words have inflected suffixes (e.g. "procedura", "dokumenti").
_RAG_SIGNALS: list[re.Pattern[str]] = [
    # Policy / regulation / compliance
    re.compile(r"\b(policy|politic|politi[kc]a|regulation|regulej|noteikum|likum)", re.I),
    # Procedures and SOPs
    re.compile(
        r"\b(procedure|procedur|protocol|protokol|SOP|instrukcij|kartib)",
        re.I,
    ),
    # Documents and manuals
    re.compile(r"\b(document|dokument|manual|rokasgramat|handbook|guidelines)", re.I),
    # Training and HR
    re.compile(r"\b(training|apmacib|onboarding|certification|sertifik)", re.I),
    # Safety and compliance
    re.compile(r"\b(safety|drosib|compliance|atbilstib|audit|parbaud)", re.I),
    # Knowledge lookups
    re.compile(r"\b(find.*document|atrast.*dokument|search.*knowledge|mekle)", re.I),
    # "What does the X say about Y" pattern
    re.compile(r"\bwhat\s+(does|do)\s+the\b.*\b(say|state|require|specify)", re.I),
    # "How to" procedural queries
    re.compile(r"\bhow\s+to\s+\w+", re.I),
    # "Ka" (Latvian "how") + procedural context
    re.compile(r"\bka\s+(rikoties|veikt|pieteikt|noformet)", re.I),
]

# Signals that the query does NOT need RAG (transit/schedule/vault operations).
# No trailing \b — Latvian words have inflected suffixes (e.g. "marsruti", "kaveja").
_SKIP_SIGNALS: list[re.Pattern[str]] = [
    # Route/transit queries
    re.compile(r"\b(route|marsrut|bus|autobus|trolleybus|trolejbus|tram)", re.I),
    # Delay/status
    re.compile(r"\b(delay|kavej|late|on.?time|laika)", re.I),
    # Schedule lookups
    re.compile(r"\b(schedule|grafik|timetable|sarakst|next bus|nakos)", re.I),
    # Stops
    re.compile(r"\b(stop|pietura|nearest|tuvak)", re.I),
    # Real-time status
    re.compile(r"\b(active|aktiv|current|paslaik|right now|tagad)", re.I),
    # Vault/Obsidian
    re.compile(r"\b(vault|note|piezim|obsidian|folder|mape)", re.I),
    # Driver/vehicle lookup (operational, not knowledge)
    re.compile(r"\b(driver|vaditaj|vehicle|transportlidzekl)", re.I),
    # Counting/status queries
    re.compile(r"\b(how many|cik|count|status|statuss)", re.I),
]


def needs_rag(query: str) -> RoutingDecision:
    """Classify whether a query needs RAG knowledge base retrieval.

    Uses signal-based scoring: counts matches against RAG and SKIP
    pattern lists. RAG wins when rag_score > skip_score.

    Args:
        query: The user's natural language query.

    Returns:
        RoutingDecision with needs_rag flag and both scores.
    """
    text = query.strip()
    rag_score = sum(1 for p in _RAG_SIGNALS if p.search(text))
    skip_score = sum(1 for p in _SKIP_SIGNALS if p.search(text))

    decision = RoutingDecision(
        needs_rag=rag_score > skip_score,
        rag_score=rag_score,
        skip_score=skip_score,
    )

    query_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
    logger.info(
        "knowledge.router.decision",
        query_hash=query_hash,
        needs_rag=decision.needs_rag,
        rag_score=rag_score,
        skip_score=skip_score,
    )

    return decision
