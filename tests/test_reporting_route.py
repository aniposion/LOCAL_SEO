from datetime import date, timedelta

from app.models.report import Report
from app.services.agency import AgencyService
from app.services.reporting import ReportingService


class _FakeConfiguredStorage:
    def __init__(self, url: str = "https://storage.example.com/reports/test.pdf") -> None:
        self.url = url

    def is_configured(self) -> bool:
        return True

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        folder: str = "uploads",
        object_name: str | None = None,
    ) -> str:
        return self.url if object_name is None else f"https://storage.example.com/{object_name}"


class _FakeUnavailableStorage:
    def is_configured(self) -> bool:
        return False


def test_reports_weekly_creates_report_without_email_when_disabled(
    client,
    db,
    auth_headers,
    test_location,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.reporting.get_storage_service",
        lambda: _FakeConfiguredStorage(),
    )

    response = client.post(
        "/reports/weekly",
        json={"location_id": str(test_location.id), "send_email": False},
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["location_id"] == str(test_location.id)
    assert payload["email_sent"] is False
    assert payload["file_url"].startswith("https://storage.example.com/reports/")
    assert db.query(Report).count() == 1


def test_reports_weekly_returns_503_when_storage_is_unconfigured(
    client,
    db,
    auth_headers,
    test_location,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.reporting.get_storage_service",
        lambda: _FakeUnavailableStorage(),
    )

    response = client.post(
        "/reports/weekly",
        json={"location_id": str(test_location.id), "send_email": False},
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert "configured" in response.json()["detail"].lower()
    assert db.query(Report).count() == 0


def test_reports_weekly_returns_503_when_email_delivery_is_unconfigured(
    client,
    db,
    auth_headers,
    test_location,
    monkeypatch,
):
    async def fake_send_email(self, to_email: str, subject: str, html_body: str, text_body: str | None = None):
        return {"success": False, "error": "Email delivery is not configured"}

    monkeypatch.setattr(
        "app.services.reporting.get_storage_service",
        lambda: _FakeConfiguredStorage(),
    )
    monkeypatch.setattr("app.services.reporting.NotificationService.send_email", fake_send_email)

    response = client.post(
        "/reports/weekly",
        json={"location_id": str(test_location.id), "send_email": True},
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()
    assert db.query(Report).count() == 0


def test_reports_weekly_returns_502_when_email_delivery_fails(
    client,
    db,
    auth_headers,
    test_location,
    monkeypatch,
):
    async def fake_send_email(self, to_email: str, subject: str, html_body: str, text_body: str | None = None):
        return {"success": False, "error": "smtp connection reset"}

    monkeypatch.setattr(
        "app.services.reporting.get_storage_service",
        lambda: _FakeConfiguredStorage(),
    )
    monkeypatch.setattr("app.services.reporting.NotificationService.send_email", fake_send_email)

    response = client.post(
        "/reports/weekly",
        json={"location_id": str(test_location.id), "send_email": True},
        headers=auth_headers,
    )

    assert response.status_code == 502
    assert "smtp connection reset" in response.json()["detail"].lower()
    assert db.query(Report).count() == 0


async def test_reporting_service_generate_monthly_report_uses_previous_month(
    db,
    test_location,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.reporting.get_storage_service",
        lambda: _FakeConfiguredStorage(),
    )

    report = await ReportingService(db).generate_monthly_report(
        location_id=test_location.id,
        send_email=False,
    )

    current_month_start = date.today().replace(day=1)
    expected_end = current_month_start - timedelta(days=1)
    expected_start = expected_end.replace(day=1)

    assert report.period_start == expected_start
    assert report.period_end == expected_end
    assert report.email_sent is False
    assert report.file_url.startswith("https://storage.example.com/reports/")


async def test_agency_service_send_bulk_reports_supports_monthly(
    db,
    test_user,
    test_location,
    monkeypatch,
):
    extra_location = test_location.__class__(
        account_id=test_user.id,
        name="Second Business",
        address="456 Test Ave",
        city="Test City",
        state="TS",
        country="US",
    )
    db.add(extra_location)
    db.commit()
    db.refresh(extra_location)

    called_location_ids: list[str] = []

    async def fake_generate_monthly_report(self, location_id, send_email=True):
        called_location_ids.append(str(location_id))
        return None

    monkeypatch.setattr(
        "app.services.reporting.ReportingService.generate_monthly_report",
        fake_generate_monthly_report,
        raising=False,
    )

    result = await AgencyService(db).send_bulk_reports(
        agency_account_id=test_user.id,
        report_type="monthly",
    )

    assert result["success"] is True
    assert result["sent"] == 2
    assert result["failed"] == 0
    assert sorted(called_location_ids) == sorted([str(test_location.id), str(extra_location.id)])
