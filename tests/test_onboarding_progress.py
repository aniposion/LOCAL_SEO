"""Onboarding progress endpoint tests."""


def test_get_onboarding_progress_creates_default_state(client, auth_headers) -> None:
    """Progress endpoint should bootstrap onboarding state for the current account."""
    response = client.get("/onboarding/progress", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["completed_steps"] == 0
    assert data["total_steps"] == 4
    assert data["current_step"] == "run_audit"
    assert len(data["steps"]) == 4


def test_complete_onboarding_step_updates_progress(client, auth_headers) -> None:
    """Completing a valid step should persist onboarding progress."""
    response = client.post(
        "/onboarding/complete-step",
        headers=auth_headers,
        json={"step": "run_audit"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["completed_steps"] == 1
    assert data["current_step"] == "view_insights"
    completed_step = next(step for step in data["steps"] if step["step"] == "run_audit")
    assert completed_step["completed"] is True
