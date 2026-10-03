"""Remediation M2 R2-27: the webhook path takes the schedule secret instead of the rotating local token."""

from uuid import uuid4


def test_webhook_path_skips_the_local_token_but_other_schedule_routes_do_not(client):
    base = f"/api/v1/projects/{uuid4()}/automations/{uuid4()}/schedules"
    anonymous = {"x-autoflow-token": ""}
    assert client.get(base, headers=anonymous).status_code == 401
    assert client.post(base, headers=anonymous, json={}).status_code == 401
    # Reaches the route (unknown schedule), proving only the secret guards it.
    called = client.post(f"{base}/{uuid4()}/webhook", headers=anonymous, json={"eventId": "e1"})
    assert called.status_code == 404, called.text
    assert client.get(f"{base}/{uuid4()}/webhook", headers=anonymous).status_code == 401
