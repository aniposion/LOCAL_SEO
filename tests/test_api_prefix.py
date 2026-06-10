def test_api_v1_health_alias(client):
    response = client.get("/api/v1/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_api_v1_router_alias_reaches_public_contact_requests(client):
    response = client.post(
        "/api/v1/contact/requests",
        json={
            "name": "API Prefix Lead",
            "email": "prefix@example.com",
            "message": "Please review whether the API prefix works for contact leads.",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "prefix@example.com"
