"""Daily schedule adherence computation, publishing, and background task lifecycle (ML-5.2).

Computes fleet-wide on-time performance for a given date, stores the result,
publishes summaries to Slack/email, and fires alerts when adherence drops
below the configured threshold.
"""

from __future__ import annotations

import asyncio
import datetime
import smtplib
from collections import defaultdict
from collections.abc import Awaitable, Callable
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.schemas import AlertInstanceCreate
from app.alerts.service import AlertService
from app.analytics.models import DailyAdherenceReport
from app.core.agents.tools.transit.client import GTFSRealtimeClient, TripUpdateData
from app.core.agents.tools.transit.get_adherence_report import _compute_route_adherence
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.core.metrics import record_poller_tick

logger = get_logger(__name__)

_adherence_task: asyncio.Task[None] | None = None


async def compute_daily_report(
    target_date: datetime.date,
    db: AsyncSession,
) -> DailyAdherenceReport:
    """Compute and persist a daily adherence report for the given date.

    Fetches GTFS static schedule and real-time data, computes per-route and
    per-hour adherence breakdowns, inserts (or updates) a row in
    ``daily_adherence_reports``, and triggers an alert if overall adherence
    falls below the configured threshold.

    Args:
        target_date: Calendar date to analyse.
        db: Async database session.

    Returns:
        The persisted ``DailyAdherenceReport`` model instance.
    """
    settings = get_settings()
    logger.info(
        "analytics.adherence.compute_started",
        target_date=str(target_date),
    )

    # Load GTFS static data (requires DB access for DB-backed store)
    static = await get_static_store(get_db_context, settings)
    service_ids = static.get_active_service_ids(target_date)

    # Fetch real-time trip updates across all configured feeds
    trip_update_map: dict[str, TripUpdateData] = {}
    for feed in settings.transit_feeds:
        if not feed.enabled:
            continue
        try:
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                rt_client = GTFSRealtimeClient(http_client, settings)
                updates = await rt_client.fetch_trip_updates()
                for upd in updates:
                    trip_update_map[upd.trip_id] = upd
        except Exception:
            logger.warning(
                "analytics.adherence.feed_fetch_failed",
                feed_id=feed.feed_id,
                exc_info=True,
            )

    per_route_list: list[dict[str, Any]] = []
    per_hour_agg: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "on_time": 0})
    total_trips = 0
    on_time_total = 0
    late_total = 0
    early_total = 0
    anomaly_count = 0

    for route_id, route_info in static.routes.items():
        route_name = route_info.route_short_name
        all_route_trips = static.route_trips.get(route_id, [])
        active_trips = [t for t in all_route_trips if t.service_id in service_ids]
        if not active_trips:
            continue

        adherence = _compute_route_adherence(
            route_id,
            route_name,
            active_trips,
            trip_update_map,
            static.trip_stop_times,
            None,
            None,
        )

        per_route_list.append(
            {
                "route_id": route_id,
                "route_short_name": route_name,
                "total_trips": adherence.tracked_trips,
                "on_time_trips": adherence.on_time_count,
                "late_trips": adherence.late_count,
                "early_trips": adherence.early_count,
                "on_time_pct": adherence.on_time_percentage,
                "avg_delay_seconds": adherence.average_delay_seconds,
            }
        )

        total_trips += adherence.tracked_trips
        on_time_total += adherence.on_time_count
        late_total += adherence.late_count
        early_total += adherence.early_count

        # Per-hour aggregation from trip details
        for trip in adherence.trips:
            if trip.scheduled_departure:
                try:
                    parts = trip.scheduled_departure.split(":")
                    hour = int(parts[0]) % 24
                    per_hour_agg[hour]["total"] += 1
                    if trip.status == "on_time":
                        per_hour_agg[hour]["on_time"] += 1
                except (ValueError, IndexError):
                    pass

    overall_pct = (on_time_total / total_trips * 100.0) if total_trips > 0 else 0.0

    per_hour_list: list[dict[str, Any]] = []
    for hour in sorted(per_hour_agg):
        h = per_hour_agg[hour]
        per_hour_list.append(
            {
                "hour": hour,
                "total_trips": h["total"],
                "on_time_trips": h["on_time"],
                "on_time_pct": (h["on_time"] / h["total"] * 100.0) if h["total"] > 0 else 0.0,
            }
        )

    # Upsert: check if report for this date already exists
    existing_stmt = select(DailyAdherenceReport).where(
        DailyAdherenceReport.report_date == target_date
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    alert_triggered = overall_pct < settings.analytics_adherence_threshold_pct

    if existing is not None:
        existing.overall_pct = overall_pct
        existing.total_trips = total_trips
        existing.on_time_trips = on_time_total
        existing.late_trips = late_total
        existing.early_trips = early_total
        existing.per_route_json = per_route_list
        existing.per_hour_json = per_hour_list
        existing.anomaly_count = anomaly_count
        existing.alert_triggered = alert_triggered
        report = existing
    else:
        report = DailyAdherenceReport(
            report_date=target_date,
            overall_pct=overall_pct,
            total_trips=total_trips,
            on_time_trips=on_time_total,
            late_trips=late_total,
            early_trips=early_total,
            per_route_json=per_route_list,
            per_hour_json=per_hour_list,
            anomaly_count=anomaly_count,
            alert_triggered=alert_triggered,
        )
        db.add(report)

    await db.flush()

    # Trigger alert if below threshold
    if alert_triggered:
        try:
            alert_svc = AlertService(db)
            await alert_svc.create_alert(
                AlertInstanceCreate(
                    title="Daily adherence below threshold",
                    severity="high",
                    alert_type="schedule_adherence",
                    source_entity_type=None,
                    source_entity_id=None,
                    details={
                        "overall_pct": overall_pct,
                        "threshold": settings.analytics_adherence_threshold_pct,
                        "report_date": str(target_date),
                    },
                    rule_id=None,
                )
            )
            logger.info(
                "analytics.adherence.alert_triggered",
                overall_pct=overall_pct,
                threshold=settings.analytics_adherence_threshold_pct,
            )
        except Exception:
            logger.warning("analytics.adherence.alert_create_failed", exc_info=True)

    await db.commit()

    logger.info(
        "analytics.adherence.compute_completed",
        target_date=str(target_date),
        overall_pct=overall_pct,
        total_trips=total_trips,
    )
    return report


async def publish_report(report: DailyAdherenceReport) -> None:
    """Publish a daily adherence report summary to Slack and/or email.

    Fail-open: errors are logged but never raised to the caller.

    Args:
        report: The persisted report to summarise.
    """
    settings = get_settings()

    # Slack webhook
    if settings.analytics_adherence_slack_webhook:
        try:
            payload = {
                "text": (
                    f"Daily Adherence Report ({report.report_date})\n"
                    f"Overall: {report.overall_pct:.1f}% "
                    f"({report.on_time_trips}/{report.total_trips} on-time)\n"
                    f"Late: {report.late_trips} | Early: {report.early_trips}"
                ),
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    settings.analytics_adherence_slack_webhook,
                    json=payload,
                )
                resp.raise_for_status()
            logger.info("analytics.adherence.slack_published")
        except Exception:
            logger.warning("analytics.adherence.slack_publish_failed", exc_info=True)

    # Email via SMTP
    if settings.analytics_adherence_smtp_enabled and settings.analytics_adherence_smtp_to:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"VTV Daily Adherence Report - {report.report_date}"
            msg["From"] = settings.analytics_adherence_smtp_from
            msg["To"] = settings.analytics_adherence_smtp_to
            msg.set_content(
                f"Overall: {report.overall_pct:.1f}%\n"
                f"Trips: {report.total_trips} total, "
                f"{report.on_time_trips} on-time, "
                f"{report.late_trips} late, {report.early_trips} early\n"
                f"Alert triggered: {report.alert_triggered}"
            )

            def _send_email() -> None:
                with smtplib.SMTP(
                    settings.analytics_adherence_smtp_host,
                    settings.analytics_adherence_smtp_port,
                ) as server:
                    server.starttls()
                    server.send_message(msg)

            await asyncio.to_thread(_send_email)
            logger.info("analytics.adherence.email_published")
        except Exception:
            logger.warning("analytics.adherence.email_publish_failed", exc_info=True)


async def get_daily_reports(
    db: AsyncSession,
    date_from: datetime.date,
    date_to: datetime.date,
) -> list[DailyAdherenceReport]:
    """Retrieve daily adherence reports for a date range.

    Args:
        db: Async database session.
        date_from: Start date (inclusive).
        date_to: End date (inclusive).

    Returns:
        List of reports ordered by report_date ascending.
    """
    stmt = (
        select(DailyAdherenceReport)
        .where(
            DailyAdherenceReport.report_date >= date_from,
            DailyAdherenceReport.report_date <= date_to,
        )
        .order_by(DailyAdherenceReport.report_date)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _run_daily_adherence() -> None:
    """Execute the daily adherence report computation and publish."""
    yesterday = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    async with get_db_context() as db:
        report = await compute_daily_report(yesterday, db)
        await publish_report(report)
    record_poller_tick("daily_adherence")


async def _run_at_hour(
    hour: int,
    name: str,
    coro_factory: Callable[[], Awaitable[None]],
) -> None:
    """Run a coroutine daily at a specific UTC hour.

    Args:
        hour: UTC hour (0-23) to execute at.
        name: Task name for logging.
        coro_factory: Async callable returning the coroutine to run.
    """
    while True:
        now = datetime.datetime.now(datetime.UTC)
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logger.info(
            f"analytics.{name}.next_run",
            wait_seconds=int(wait_seconds),
            target_hour=hour,
        )
        await asyncio.sleep(wait_seconds)
        try:
            await coro_factory()
        except Exception:
            logger.warning(f"analytics.{name}.run_failed", exc_info=True)


async def start_adherence_task() -> None:
    """Start the daily adherence background task if enabled.

    Defers to the arq job queue when ``background_queue_enabled`` is True.
    """
    global _adherence_task
    settings = get_settings()

    if not settings.analytics_adherence_enabled:
        logger.info("analytics.adherence.lifecycle_disabled")
        return

    if settings.background_queue_enabled:
        logger.info("analytics.adherence.deferred_to_queue")
        return

    _adherence_task = asyncio.create_task(
        _run_at_hour(
            settings.analytics_adherence_cron_hour,
            "adherence",
            _run_daily_adherence,
        )
    )
    logger.info(
        "analytics.adherence.lifecycle_started",
        cron_hour=settings.analytics_adherence_cron_hour,
    )


async def stop_adherence_task() -> None:
    """Cancel the daily adherence background task."""
    global _adherence_task
    if _adherence_task is not None:
        _adherence_task.cancel()
        try:
            await _adherence_task
        except asyncio.CancelledError:
            pass
        _adherence_task = None
        logger.info("analytics.adherence.lifecycle_stopped")
