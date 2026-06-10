"""Dedicated scheduler worker runtime tests."""

import asyncio
import contextlib

import pytest

import app.worker as worker_module


@pytest.mark.asyncio
async def test_scheduler_worker_requires_explicit_enablement(monkeypatch) -> None:
    """The worker should fail fast when scheduler env flags are missing."""
    monkeypatch.setattr(worker_module.settings, "app_env", "prod", raising=False)
    monkeypatch.setattr(worker_module.settings, "scheduler_enabled", False, raising=False)

    with pytest.raises(RuntimeError):
        await worker_module.run_scheduler_worker(asyncio.Event())


@pytest.mark.asyncio
async def test_scheduler_worker_starts_and_stops_requested_targets(monkeypatch) -> None:
    """Dedicated worker should start only configured targets and shut them down cleanly."""
    started_calls: list[str] = []
    stopped_calls: list[str] = []

    monkeypatch.setattr(worker_module.settings, "app_env", "prod", raising=False)
    monkeypatch.setattr(worker_module.settings, "scheduler_enabled", True, raising=False)
    monkeypatch.setattr(worker_module.settings, "scheduler_target", "all", raising=False)
    monkeypatch.setattr(worker_module, "start_jobs_scheduler", lambda: started_calls.append("jobs"))
    monkeypatch.setattr(worker_module, "start_workers_scheduler", lambda: started_calls.append("workers"))
    monkeypatch.setattr(worker_module, "shutdown_jobs_scheduler", lambda: stopped_calls.append("jobs"))
    monkeypatch.setattr(worker_module, "shutdown_workers_scheduler", lambda: stopped_calls.append("workers"))

    stop_event = asyncio.Event()
    stop_event.set()

    started = await worker_module.run_scheduler_worker(stop_event)

    assert started == ["jobs", "workers"]
    assert started_calls == ["jobs", "workers"]
    assert stopped_calls == ["jobs", "workers"]


@pytest.mark.asyncio
async def test_worker_health_server_returns_ok() -> None:
    """Dedicated worker should expose a simple health endpoint when a port is configured."""
    server, port = await worker_module.start_worker_health_server(host="127.0.0.1", port=0)

    assert server is not None
    assert port is not None

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(b"GET /healthz HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        await writer.drain()
        response = await reader.read(1024)
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        server.close()
        await server.wait_closed()

    decoded = response.decode("utf-8")
    assert "200 OK" in decoded
    assert "scheduler worker ok" in decoded
