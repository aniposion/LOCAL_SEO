"""Tests for the production environment check script."""

import scripts.check_prod_env as check_prod_env


def test_redact_url_credentials_hides_database_password() -> None:
    redacted = check_prod_env._redact_url_credentials(
        "postgresql+psycopg2://seo:super-secret@db.example.com:5432/app"
    )

    assert "super-secret" not in redacted
    assert redacted == "postgresql+psycopg2://seo:***@db.example.com:5432/app"


def test_check_prod_env_require_prod_fails_outside_prod(monkeypatch, capsys) -> None:
    monkeypatch.setattr(check_prod_env.settings, "app_env", "dev")
    monkeypatch.setattr(
        check_prod_env.settings,
        "database_url",
        "postgresql+psycopg2://seo:super-secret@db.example.com:5432/app",
    )

    exit_code = check_prod_env.main(["--require-prod"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "APP_ENV must be prod" in output
    assert "super-secret" not in output
    assert "postgresql+psycopg2://seo:***@db.example.com:5432/app" in output
