"""Scheduler runtime configuration tests."""

import app.main as main_module


def test_start_configured_schedulers_skips_when_disabled(monkeypatch) -> None:
    """Web processes should not start schedulers unless explicitly enabled."""
    calls: list[str] = []

    monkeypatch.setattr(main_module.settings, "app_env", "prod", raising=False)
    monkeypatch.setattr(main_module.settings, "scheduler_enabled", False, raising=False)
    monkeypatch.setattr(main_module, "start_jobs_scheduler", lambda: calls.append("jobs"))
    monkeypatch.setattr(main_module, "start_workers_scheduler", lambda: calls.append("workers"))

    started = main_module._start_configured_schedulers()

    assert started == []
    assert calls == []


def test_start_and_shutdown_configured_schedulers_respects_target(monkeypatch) -> None:
    """Only the configured scheduler targets should start and stop."""
    started_calls: list[str] = []
    stopped_calls: list[str] = []

    monkeypatch.setattr(main_module.settings, "app_env", "prod", raising=False)
    monkeypatch.setattr(main_module.settings, "scheduler_enabled", True, raising=False)
    monkeypatch.setattr(main_module.settings, "scheduler_target", "all", raising=False)
    monkeypatch.setattr(main_module, "start_jobs_scheduler", lambda: started_calls.append("jobs"))
    monkeypatch.setattr(main_module, "start_workers_scheduler", lambda: started_calls.append("workers"))
    monkeypatch.setattr(main_module, "shutdown_jobs_scheduler", lambda: stopped_calls.append("jobs"))
    monkeypatch.setattr(main_module, "shutdown_workers_scheduler", lambda: stopped_calls.append("workers"))

    started = main_module._start_configured_schedulers()
    main_module._shutdown_configured_schedulers(started)

    assert started == ["jobs", "workers"]
    assert started_calls == ["jobs", "workers"]
    assert stopped_calls == ["jobs", "workers"]
