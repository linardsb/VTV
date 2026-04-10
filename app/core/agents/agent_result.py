"""``AgentResult`` — internal agent-pipeline result wrapper (AI-6.5).

A lightweight, immutable data container built inside ``BaseAgentService.chat``
from the ``_PipelineOutcome`` returned by ``_execute`` plus the active domain
name. ``AgentResult`` is metadata only — its ``warnings`` are **not** rendered
into the response content; that still happens earlier in ``_post_process``.

The wrapper exists so the confidence-based re-route gate has a clean object
to inspect, and so future consumers (logs, metrics, audit) can read
structured fields without re-parsing the response envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

VALID_DOMAINS: Final[frozenset[str]] = frozenset({"transit", "knowledge", "vault", "unified"})


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Immutable agent pipeline result.

    Attributes:
        content: Already-rendered response text (post ``_post_process`` — may
            include QA warning footnotes). This is what goes into the
            OpenAI-compatible response envelope.
        confidence: Domain-specific confidence in ``[0.0, 1.0]`` or ``None``
            when the agent cannot measure it. Drives the re-route gate in
            ``BaseAgentService.chat``.
        warnings: Metadata only — list of QA warning strings raised during
            validation. These are NOT rendered into ``content`` again; that
            happens earlier in ``_post_process`` so consumers can inspect
            them without double-rendering.
        tools_used: Tuple of tool names invoked during the agent run, for
            observability and re-route heuristics.
        domain: One of ``transit``, ``knowledge``, ``vault``, ``unified``.

    Raises:
        ValueError: If ``domain`` is not in ``VALID_DOMAINS`` or ``confidence``
            is outside ``[0.0, 1.0]``.
    """

    content: str
    confidence: float | None
    warnings: tuple[str, ...]
    tools_used: tuple[str, ...]
    domain: str

    def __post_init__(self) -> None:
        if self.domain not in VALID_DOMAINS:
            msg = f"AgentResult.domain must be one of {sorted(VALID_DOMAINS)}; got {self.domain!r}"
            raise ValueError(msg)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            msg = f"AgentResult.confidence must be in [0.0, 1.0] or None; got {self.confidence!r}"
            raise ValueError(msg)


__all__ = ["VALID_DOMAINS", "AgentResult"]
