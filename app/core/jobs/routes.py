# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Admin routes for durable job queue status monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.config import get_settings
from app.core.jobs.schemas import JobStatusEntry, JobStatusResponse
from app.core.rate_limit import limiter

router = APIRouter(prefix="/admin/jobs", tags=["admin"])


@router.get("/status", response_model=JobStatusResponse)
@limiter.limit("30/minute")
async def get_job_status(
    request: Request,
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> JobStatusResponse:
    """Return current status of background job queue.

    Args:
        request: FastAPI request (required by rate limiter).
        _current_user: Authenticated admin user.

    Returns:
        Job queue status with per-job details.
    """
    _ = request
    settings = get_settings()

    if not settings.background_queue_enabled:
        return JobStatusResponse(queue_enabled=False, jobs=[])

    from app.core.jobs.queue import get_arq_pool

    pool = await get_arq_pool()
    all_results = await pool.all_job_results()
    jobs: list[JobStatusEntry] = []

    for job_name in ("run_compaction", "run_promotion", "run_daily_adherence"):
        matching = [r for r in all_results if r.function == job_name]
        latest = matching[-1] if matching else None

        jobs.append(
            JobStatusEntry(
                name=job_name,
                last_run=latest.enqueue_time if latest else None,
                next_run=None,
                last_result="success"
                if latest and latest.success
                else "failed"
                if latest
                else None,
                failure_count=sum(1 for r in matching if not r.success),
                last_duration_seconds=(
                    latest.finish_time.timestamp() - latest.start_time.timestamp()
                    if latest and latest.finish_time and latest.start_time
                    else None
                ),
            )
        )

    return JobStatusResponse(queue_enabled=True, jobs=jobs)
