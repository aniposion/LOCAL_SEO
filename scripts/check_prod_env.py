"""Validate production configuration before deployment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.core.production_readiness import validate_runtime_settings


def _redact_url_credentials(raw_url: str) -> str:
    """Hide URL passwords before printing config to CI or release logs."""
    parsed = urlsplit(str(raw_url))
    if not parsed.username and not parsed.password:
        return str(raw_url)

    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = f"{parsed.username or ''}:***@"
    return urlunsplit(
        (parsed.scheme, f"{auth}{host}{port}", parsed.path, parsed.query, parsed.fragment)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate production configuration before deployment."
    )
    parser.add_argument(
        "--require-prod",
        action="store_true",
        help="Fail when APP_ENV is not prod. Use this in release pipelines.",
    )
    args = parser.parse_args(argv)

    readiness = validate_runtime_settings(settings)
    errors = list(readiness["errors"])
    warnings = list(readiness["warnings"])

    if args.require_prod and settings.app_env != "prod":
        errors.append("APP_ENV must be prod when --require-prod is used.")

    print("Production readiness configuration check")
    print(f"APP_ENV={settings.app_env}")
    print(f"APP_URL={settings.app_url}")
    print(f"DATABASE_URL={_redact_url_credentials(settings.database_url)}")
    print()

    if errors:
        print("Errors:")
        for item in errors:
            print(f"- {item}")
    else:
        print("Errors: none")

    print()
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")
    else:
        print("Warnings: none")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
