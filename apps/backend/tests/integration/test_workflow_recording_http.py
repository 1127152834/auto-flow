from __future__ import annotations

import httpx
import pytest
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings


@pytest.mark.asyncio
async def test_recording_review_http_persists_and_checks_revision(tmp_path) -> None:
    app = create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="recording-http",
            instance_token="test-token",
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"x-autoflow-token": "test-token"},
    ) as client:
        initial_status = await client.get("/api/recorder/status")
        unavailable = await client.post(
            "/api/recorder/start", json={"sessionId": "record-without-browser"}
        )
        missing = await client.get("/api/recorder/reviews/document-1")
        saved = await client.put(
            "/api/recorder/reviews/document-1",
            json={
                "expectedRevision": 0,
                "autoWait": True,
                "events": [
                    {
                        "sequence": 1,
                        "type": "navigate",
                        "url": "https://example.test",
                    }
                ],
            },
        )
        conflict = await client.put(
            "/api/recorder/reviews/document-1",
            json={"expectedRevision": 0, "autoWait": False, "events": []},
        )
        restored = await client.get("/api/recorder/reviews/document-1")
        await app.state.workflow_services.shutdown()

    assert initial_status.json() == {
        "success": True,
        "sessionId": None,
        "recording": False,
        "paused": False,
        "nextSeq": 0,
    }
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "INSPECTION_BROWSER_CLOSED"
    assert missing.status_code == 404
    assert saved.status_code == 200
    assert saved.json() == restored.json() == {
        "documentId": "document-1",
        "revision": 1,
        "autoWait": True,
        "events": [
            {
                "sequence": 1,
                "type": "navigate",
                "url": "https://example.test",
            }
        ],
    }
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "RECORDING_REVIEW_CONFLICT"
