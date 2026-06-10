"""Dedicated scheduler worker entry point."""

import asyncio
import contextlib
import logging
import os
import signal

from app.core.config import settings
from app.jobs.scheduler import (
    shutdown_scheduler as shutdown_jobs_scheduler,
    start_scheduler as start_jobs_scheduler,
)
from app.scheduler_runtime import (
    shutdown_configured_schedulers,
    start_configured_schedulers,
)
from app.workers.scheduler import (
    setup_scheduler as start_workers_scheduler,
    shutdown_scheduler as shutdown_workers_scheduler,
)

logger = logging.getLogger(__name__)
_WORKER_HEALTH_BODY = b"scheduler worker ok"
_WORKER_HEALTH_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    + f"Content-Length: {len(_WORKER_HEALTH_BODY)}\r\n".encode("ascii")
    + b"Connection: close\r\n\r\n"
    + _WORKER_HEALTH_BODY
)


def _install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    """Install basic signal handlers for graceful worker shutdown."""

    def _handle_signal(signum: int, _frame) -> None:
        logger.info("Scheduler worker received signal %s", signum)
        stop_event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, _handle_signal)


async def _handle_health_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Serve a tiny health endpoint so Cloud Run can keep the worker revision alive."""
    try:
        await reader.read(1024)
        writer.write(_WORKER_HEALTH_RESPONSE)
        await writer.drain()
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def start_worker_health_server(
    host: str = "0.0.0.0",
    port: int | None = None,
) -> tuple[asyncio.AbstractServer | None, int | None]:
    """Start a minimal HTTP server when a worker port is configured."""
    resolved_port = port
    if resolved_port is None:
        raw_port = os.getenv("PORT")
        if not raw_port:
            logger.info("Worker health server is disabled because PORT is not set.")
            return None, None
        resolved_port = int(raw_port)

    server = await asyncio.start_server(_handle_health_connection, host, resolved_port)
    bound_port = None
    if server.sockets:
        bound_port = int(server.sockets[0].getsockname()[1])

    logger.info("Worker health server listening on %s:%s", host, bound_port or resolved_port)
    return server, bound_port or resolved_port


async def run_scheduler_worker(stop_event: asyncio.Event | None = None) -> list[str]:
    """Run configured schedulers in a dedicated worker process."""
    started = start_configured_schedulers(
        settings=settings,
        process_name="scheduler-worker",
        start_jobs_scheduler=start_jobs_scheduler,
        start_workers_scheduler=start_workers_scheduler,
    )
    if not started:
        raise RuntimeError(
            "No schedulers were started. Set SCHEDULER_ENABLED=true and choose "
            "SCHEDULER_TARGET=jobs|workers|all for the scheduler worker process."
        )

    managed_stop_event = stop_event or asyncio.Event()
    if stop_event is None:
        _install_shutdown_handlers(managed_stop_event)

    health_server: asyncio.AbstractServer | None = None
    try:
        health_server, _ = await start_worker_health_server()
        await managed_stop_event.wait()
        return started
    finally:
        if health_server is not None:
            health_server.close()
            await health_server.wait_closed()
        shutdown_configured_schedulers(
            started=started,
            process_name="scheduler-worker",
            shutdown_jobs_scheduler=shutdown_jobs_scheduler,
            shutdown_workers_scheduler=shutdown_workers_scheduler,
        )


def main() -> int:
    """CLI entry point for ``python -m app.worker``."""
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_scheduler_worker())
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
