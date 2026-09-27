from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.errors import install_error_handlers
from autoflow.adapters.http.workflow_inspection import workflow_inspection_router


class Inspection:
    def check_project_access(self, project_id, *, writable=False, browser=True):
        assert project_id is None

    async def status(self):
        return {"isOpen": True, "pickerActive": True, "sessionId": "browser-1", "profileId": "profile-1"}

    async def open(self, *, profile_id, url=None, project_id=None):
        return {
            "isOpen": True,
            "pickerActive": False,
            "sessionId": "browser-1",
            "profileId": profile_id,
            "url": url,
        }

    async def close(self, session_id=None, project_id=None):
        return {"success": True, "sessionId": session_id}

    async def navigate(self, url):
        return {"success": True, "url": url}

    async def current_url(self):
        return {"url": "https://example.test"}

    async def pages(self):
        return {
            "sessionId": "browser-1",
            "revision": 2,
            "targetPageId": "page-1",
            "pages": [{"pageId": "page-1", "title": "受控页", "url": "https://example.test"}],
        }

    async def page(self, request):
        assert request["expectedRevision"] == 2
        return await self.pages()

    async def start_picker(self, *, session_id, profile_id, url, project_id=None):
        return {"success": True, "sessionId": session_id, "active": True, "selected": False}

    async def stop_picker(self, session_id):
        return {"success": True, "sessionId": session_id, "active": False, "selected": False}

    def picker_status(self, session_id):
        return {"success": True, "sessionId": session_id or "picker-1", "active": True, "selected": False}

    async def picker_result(self, session_id, *, similar):
        if similar:
            return {
                "success": True,
                "sessionId": session_id,
                "active": True,
                "selected": True,
                "similar": {"pattern": ".item:nth-child({index})", "count": 2, "minIndex": 1, "maxIndex": 2},
            }
        return {
            "success": True,
            "sessionId": session_id,
            "active": True,
            "selected": True,
            "element": {"selector": "#target"},
        }

    async def test_selector(self, request):
        return {
            "success": True,
            "matched": True,
            "count": 1,
            "matchedSelector": request["selector"],
            "isPrimary": True,
            "element": {"tag": "button", "text": "确定"},
            "tried": [{"selector": request["selector"], "count": 1}],
        }


def client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(workflow_inspection_router(Inspection()))  # type: ignore[arg-type]
    return TestClient(app)


def test_browser_and_picker_contract_roundtrip():
    api = client()
    assert api.get("/api/browser/status").json()["sessionId"] == "browser-1"
    assert api.post("/api/browser/open", json={"profileId": "profile-1"}).status_code == 200
    pages = api.get("/api/browser/pages").json()
    assert pages["targetPageId"] == "page-1"
    assert api.post(
        "/api/browser/pages",
        json={"sessionId": "browser-1", "expectedRevision": 2, "pageId": "page-1", "action": "select"},
    ).status_code == 200

    started = api.post(
        "/api/element-picker/start",
        json={"sessionId": "picker-1", "profileId": "profile-1", "url": None},
    ).json()
    assert started == {"success": True, "sessionId": "picker-1", "active": True, "selected": False}
    assert api.get("/api/element-picker/selected?sessionId=picker-1").json()["element"]["selector"] == "#target"
    similar = api.get("/api/element-picker/similar?sessionId=picker-1").json()
    assert similar["sessionId"] == "picker-1"
    assert similar["similar"]["count"] == 2
    tested = api.post(
        "/api/element-picker/test-selector",
        json={"selector": "#target", "sessionId": "picker-1", "highlight": True},
    ).json()
    assert tested["matched"] is True and tested["count"] == 1


def test_inspection_contract_rejects_unknown_or_invalid_fields():
    api = client()
    assert api.post("/api/browser/open", json={"profileId": "", "extra": True}).status_code == 422
    assert api.post("/api/element-picker/start", json={"sessionId": "picker-1"}).status_code == 422
    assert api.post("/api/element-picker/test-selector", json={"selector": " "}).status_code == 422
