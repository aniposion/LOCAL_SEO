from app.routers import ab_testing as ab_router
from app.services.ab_testing import ABTestingService


def _test_payload(location_id: str) -> dict:
    return {
        "name": "Title Test",
        "description": "Compare two titles",
        "location_id": location_id,
        "test_type": "title",
        "primary_metric": "engagement",
        "control_content": {"title": "Weekend Special"},
        "variant_content": {"title": "Weekend Special with Emoji"},
        "traffic_split": 50,
        "min_sample_size": 10,
    }


def test_ab_tests_return_empty_without_demo(client, auth_headers, test_location, monkeypatch):
    monkeypatch.setattr(ab_router, "_ab_service", ABTestingService())

    response = client.get("/ab-tests/", headers=auth_headers, params={"location_id": str(test_location.id)})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["tests"] == []


def test_ab_tests_reject_other_account_location(client, auth_headers, other_location, monkeypatch):
    monkeypatch.setattr(ab_router, "_ab_service", ABTestingService())

    response = client.get(
        f"/ab-tests/suggestions/{other_location.id}",
        headers=auth_headers,
    )
    assert response.status_code == 404

    create = client.post("/ab-tests/", headers=auth_headers, json=_test_payload(str(other_location.id)))
    assert create.status_code == 404


def test_ab_test_suggestions_use_clean_customer_facing_copy(client, auth_headers, test_location, monkeypatch):
    monkeypatch.setattr(ab_router, "_ab_service", ABTestingService())

    response = client.get(
        f"/ab-tests/suggestions/{test_location.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert suggestions[0]["name"] == "Urgency vs Standard Title"
    assert suggestions[0]["variant"] == "Weekend Special: Save 20% Today"
    assert all("?" not in item["variant"] for item in suggestions)


def test_ab_tests_crud_is_owned_and_coherent(client, auth_headers, test_location, monkeypatch):
    monkeypatch.setattr(ab_router, "_ab_service", ABTestingService())

    create = client.post("/ab-tests/", headers=auth_headers, json=_test_payload(str(test_location.id)))
    assert create.status_code == 200
    test_id = create.json()["id"]

    list_response = client.get("/ab-tests/", headers=auth_headers, params={"location_id": str(test_location.id)})
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(f"/ab-tests/{test_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["location_id"] == str(test_location.id)

    start_response = client.post(f"/ab-tests/{test_id}/start", headers=auth_headers)
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    pause_response = client.post(f"/ab-tests/{test_id}/pause", headers=auth_headers)
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    complete_response = client.post(f"/ab-tests/{test_id}/complete", headers=auth_headers)
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    results = client.get(f"/ab-tests/{test_id}/results", headers=auth_headers)
    assert results.status_code == 200
    assert results.json()["test_id"] == test_id

    delete_response = client.delete(f"/ab-tests/{test_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    missing = client.get(f"/ab-tests/{test_id}", headers=auth_headers)
    assert missing.status_code == 404
