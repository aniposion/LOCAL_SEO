from datetime import date

from app.models.analytics import Analytics


def test_analytics_ingest_upserts_and_summary_handles_platform_case(
    client,
    db,
    auth_headers,
    test_location,
):
    today = date.today().isoformat()

    first = client.post(
        "/analytics/ingest/gbp",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "data": [
                {
                    "date": today,
                    "impressions": 100,
                    "clicks": 10,
                    "calls": 2,
                    "direction_requests": 3,
                }
            ],
        },
    )
    second = client.post(
        "/analytics/ingest/gbp",
        headers=auth_headers,
        json={
            "location_id": str(test_location.id),
            "data": [
                {
                    "date": today,
                    "impressions": 150,
                    "clicks": 12,
                    "calls": 4,
                    "direction_requests": 5,
                }
            ],
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201

    rows = db.query(Analytics).filter(Analytics.location_id == test_location.id).all()
    assert len(rows) == 1
    assert rows[0].platform == "GBP"
    assert rows[0].date == date.today()
    assert rows[0].impressions == 150
    assert rows[0].source_raw["date"] == today

    db.add(
        Analytics(
            location_id=test_location.id,
            platform="website",
            date=date.today(),
            page_views=25,
            unique_visitors=10,
        )
    )
    db.commit()

    summary = client.get(
        "/analytics/summary",
        headers=auth_headers,
        params={"location_id": str(test_location.id), "from_date": today, "to_date": today},
    )

    assert summary.status_code == 200
    payload = summary.json()
    assert payload["gbp"]["impressions"] == 150
    assert payload["gbp"]["calls"] == 4
    assert payload["website"]["page_views"] == 25
    assert payload["totals"]["total_impressions"] == 175


def test_analytics_ingest_blocks_other_location(client, auth_headers, other_location):
    response = client.post(
        "/analytics/ingest/ig",
        headers=auth_headers,
        json={
            "location_id": str(other_location.id),
            "data": [{"date": date.today().isoformat(), "reach": 10}],
        },
    )

    assert response.status_code == 404
