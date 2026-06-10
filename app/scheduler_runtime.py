"""Shared scheduler runtime helpers for web and worker processes."""

from collections.abc import Callable
import logging

from app.core.config import Settings

logger = logging.getLogger(__name__)

SchedulerStarter = Callable[[], None]
SchedulerStopper = Callable[[], None]


def start_configured_schedulers(
    *,
    settings: Settings,
    process_name: str,
    start_jobs_scheduler: SchedulerStarter,
    start_workers_scheduler: SchedulerStarter,
) -> list[str]:
    """Start only the schedulers explicitly enabled for the current process."""
    if settings.app_env == "test" or not settings.scheduler_enabled:
        logger.info(
            "Background schedulers are disabled for %s. env=%s enabled=%s",
            process_name,
            settings.app_env,
            settings.scheduler_enabled,
        )
        return []

    started: list[str] = []

    if settings.scheduler_target in {"jobs", "all"}:
        start_jobs_scheduler()
        started.append("jobs")

    if settings.scheduler_target in {"workers", "all"}:
        start_workers_scheduler()
        started.append("workers")

    logger.info(
        "Started background schedulers for %s: %s",
        process_name,
        ", ".join(started) or "none",
    )
    return started


def shutdown_configured_schedulers(
    *,
    started: list[str],
    process_name: str,
    shutdown_jobs_scheduler: SchedulerStopper,
    shutdown_workers_scheduler: SchedulerStopper,
) -> None:
    """Shutdown only the schedulers started by the current process."""
    if "jobs" in started:
        shutdown_jobs_scheduler()
    if "workers" in started:
        shutdown_workers_scheduler()

    logger.info(
        "Stopped background schedulers for %s: %s",
        process_name,
        ", ".join(started) or "none",
    )
