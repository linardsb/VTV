"""Lightweight multi-phase pipeline for complex transit queries.

For complex-tier prompts, breaks execution into phases:
1. Analyze: gather data via tools
2. Synthesize: combine findings into a coherent response
3. (Future: validate, escalate, etc.)

For now this wraps single-agent execution with phase tracking,
preparing the infrastructure for future multi-agent support.
"""

import time
from dataclasses import dataclass, field

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PipelinePhase:
    """A single execution phase in the pipeline."""

    name: str
    instructions: str
    max_retries: int = 1


@dataclass
class PhaseDetail:
    """Execution details for a completed phase."""

    name: str
    duration_ms: float
    status: str  # "success" or "failed"


@dataclass
class PipelineResult:
    """Result of a full pipeline execution."""

    output: str
    phases_completed: list[str] = field(default_factory=list)
    total_duration_ms: float = 0.0
    phase_details: list[PhaseDetail] = field(default_factory=list)


class Pipeline:
    """Sequential multi-phase execution pipeline using a single agent.

    Executes phases in order, passing each phase's output as context
    to the next. If a phase fails after retries, the pipeline stops
    and returns whatever was completed.

    Args:
        phases: Ordered list of phases to execute.
        agent: The pydantic_ai Agent instance.
        deps: Unified dependencies for agent tool execution.
    """

    def __init__(
        self,
        phases: list[PipelinePhase],
        agent: Agent[UnifiedDeps, str],
        deps: UnifiedDeps,
    ) -> None:
        self._phases = phases
        self._agent = agent
        self._deps = deps

    async def run(
        self,
        prompt: str,
        message_history: list[ModelMessage] | None = None,
        instructions: str | None = None,
        model: object | None = None,
    ) -> PipelineResult:
        """Execute all phases sequentially.

        Each phase receives the original prompt plus accumulated context
        from prior phases. Phase-specific instructions are prepended to
        any existing instructions.

        Args:
            prompt: The user's original prompt.
            message_history: Prior conversation messages.
            instructions: Base instructions (e.g. skills content).
            model: Optional model override for tier routing.

        Returns:
            PipelineResult with the final output and phase details.
        """
        pipeline_start = time.monotonic()
        result = PipelineResult(output="")
        accumulated_context = ""

        logger.info(
            "agent.pipeline.run_started",
            phase_count=len(self._phases),
            prompt_length=len(prompt),
        )

        for phase in self._phases:
            phase_start = time.monotonic()
            phase_succeeded = False

            # Build phase prompt: original prompt + prior context + phase instructions
            phase_prompt = prompt
            if accumulated_context:
                phase_prompt = (
                    f"Previous analysis:\n{accumulated_context}\n\nOriginal request: {prompt}"
                )

            # Prepend phase instructions to base instructions
            phase_instructions = phase.instructions
            if instructions:
                phase_instructions = f"{phase.instructions}\n\n{instructions}"

            for attempt in range(1, phase.max_retries + 1):
                try:
                    logger.info(
                        "agent.pipeline.phase_started",
                        phase=phase.name,
                        attempt=attempt,
                    )

                    agent_result = await self._agent.run(
                        phase_prompt,
                        deps=self._deps,
                        message_history=message_history,
                        instructions=phase_instructions,
                        model=model,
                    )

                    accumulated_context = agent_result.output
                    phase_succeeded = True

                    logger.info(
                        "agent.pipeline.phase_completed",
                        phase=phase.name,
                        attempt=attempt,
                        output_length=len(agent_result.output),
                    )
                    break

                except Exception:
                    logger.warning(
                        "agent.pipeline.phase_failed",
                        phase=phase.name,
                        attempt=attempt,
                        max_retries=phase.max_retries,
                        exc_info=True,
                    )

            phase_duration_ms = (time.monotonic() - phase_start) * 1000

            if phase_succeeded:
                result.phases_completed.append(phase.name)
                result.phase_details.append(
                    PhaseDetail(
                        name=phase.name,
                        duration_ms=phase_duration_ms,
                        status="success",
                    )
                )
            else:
                result.phase_details.append(
                    PhaseDetail(
                        name=phase.name,
                        duration_ms=phase_duration_ms,
                        status="failed",
                    )
                )
                logger.error(
                    "agent.pipeline.stopped",
                    failed_phase=phase.name,
                    completed_phases=result.phases_completed,
                )
                break

        result.output = accumulated_context
        result.total_duration_ms = (time.monotonic() - pipeline_start) * 1000

        logger.info(
            "agent.pipeline.run_completed",
            phases_completed=result.phases_completed,
            total_duration_ms=result.total_duration_ms,
        )

        return result


def get_complex_pipeline(
    agent: Agent[UnifiedDeps, str],
    deps: UnifiedDeps,
) -> Pipeline:
    """Create a pre-configured pipeline for complex-tier prompts.

    Two-phase pipeline:
    1. Analyze — gather and organize data using transit tools.
    2. Synthesize — combine findings into an actionable summary.

    Args:
        agent: The pydantic_ai Agent instance.
        deps: Unified dependencies for agent tool execution.

    Returns:
        A Pipeline configured for complex query handling.
    """
    phases = [
        PipelinePhase(
            name="analyze",
            instructions=(
                "Focus on gathering and organizing all relevant data. "
                "Use transit tools to fetch real-time information. "
                "Present raw findings clearly."
            ),
            max_retries=1,
        ),
        PipelinePhase(
            name="synthesize",
            instructions=(
                "Based on the analysis above, synthesize a clear, actionable "
                "summary for the dispatcher. Highlight critical issues first, "
                "then details."
            ),
            max_retries=1,
        ),
    ]
    return Pipeline(phases=phases, agent=agent, deps=deps)
