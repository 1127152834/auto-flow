from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.adapters.http.android_management import android_management_router
from autoflow.adapters.http.errors import install_error_handlers
from autoflow.application.android.diagnostics import EnvironmentCheckService
from autoflow.application.android.images import AndroidImageService
from autoflow.domain.android.ports import AndroidError


def test_image_pull_rejects_command_options_before_provider_access() -> None:
    runtime = type("Runtime", (), {"environment": lambda _self: {"available": True, "platformSupported": True, "runtimeId": "test", "images": []}})()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(runtime), images=object()))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/android/management/image-pulls",
            json={"requestId": "pull-1", "reference": "repo:tag\n--privileged"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_registration_returns_server_inspected_metadata() -> None:
    class Resources:
        def __init__(self):
            self.items = {}

        def list(self, kind):
            return [value for (stored_kind, _), value in self.items.items() if stored_kind == kind]

        def save(self, kind, value):
            self.items[(kind, value["id"])] = value

    class Devices:
        def list(self):
            return []

    class Catalog:
        async def inspect(self, _reference):
            return SimpleNamespace(
                image_id="sha256:" + "a" * 64,
                source_digest="sha256:" + "b" * 64,
                architecture="arm64",
                os="linux",
                android_version="13",
                google_components="absent",
            )

    service = AndroidImageService(Resources(), Devices(), Catalog())
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), images=service))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/android/management/images",
            json={
                "id": "sha256:" + "a" * 64,
                "name": "image",
                "reference": "redroid/redroid:13",
            },
        )
        listed = client.get("/api/v1/android/management/images")

    assert response.status_code == 201, response.text
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["items"]) == 1
    assert listed.json()["items"][0]["imageId"] == "sha256:" + "a" * 64
    assert "workspaceId" not in listed.json()["items"][0]
    assert "requestId" not in listed.json()["items"][0]
    body = response.json()
    assert body["sourceDigest"] == "sha256:" + "b" * 64
    assert body["architecture"] == "arm64"


@pytest.mark.asyncio
async def test_image_verification_uses_server_catalog_evidence_instead_of_client_passed() -> None:
    class Resources:
        def __init__(self):
            self.items = {}

        def get(self, kind, identifier):
            return self.items[(kind, identifier)]

        def list(self, kind):
            return [value for (stored_kind, _), value in self.items.items() if stored_kind == kind]

        def save(self, kind, value):
            self.items[(kind, value["id"])] = value

    class Devices:
        def list(self):
            return []

    class Catalog:
        async def inspect(self, _reference):
            return SimpleNamespace(
                image_id="sha256:" + "9" * 64,
                source_digest="sha256:" + "8" * 64,
                architecture="arm64",
                os="linux",
                android_version="13",
                google_components="unknown",
            )

    resources = Resources()
    class RegistrationCatalog:
        async def inspect(self, _reference):
            return SimpleNamespace(
                image_id="sha256:" + "4" * 64,
                source_digest="sha256:" + "8" * 64,
                architecture="arm64",
                os="linux",
                android_version="13",
                google_components="unknown",
            )

    service = AndroidImageService(resources, Devices(), RegistrationCatalog())
    image = await service.register({"id": "sha256:" + "4" * 64, "name": "image", "reference": "redroid/redroid:13"})
    service.catalog = Catalog()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), images=service))

    with TestClient(app) as client:
        invalid = client.post(
            f"/api/v1/android/management/images/{image['id']}/verifications",
            json={"check": "image_metadata", "result": "passed", "evidence": {}},
        )
        response = client.post(
            f"/api/v1/android/management/images/{image['id']}/verifications",
            json={"check": "image_metadata", "evidence": {"imageId": image["imageId"]}},
        )

    assert invalid.status_code == 422, invalid.text
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["verification"]["state"] == "failed"
    assert body["verification"]["records"][-1]["source"] == "server"


@pytest.mark.asyncio
async def test_image_delete_unknown_has_explicit_server_verification_route() -> None:
    class Resources:
        def __init__(self):
            self.items = {}

        def get(self, kind, identifier):
            if (kind, identifier) not in self.items:
                raise AndroidError("NOT_FOUND", "not found", 404)
            return self.items[(kind, identifier)]

        def list(self, kind):
            return [value for (stored_kind, _), value in self.items.items() if stored_kind == kind]

        def save(self, kind, value):
            self.items[(kind, value["id"])] = value

    class Runtime:
        async def delete_image(self, _image_id):
            raise TimeoutError("lost response")

        async def inspect_image(self, _image_id):
            raise AndroidError("ANDROID_IMAGE_NOT_FOUND", "镜像不存在", 404)

    class Devices:
        def __init__(self):
            self.runtime = Runtime()

        def list(self):
            return []

    resources = Resources()
    devices = Devices()
    class RegistrationCatalog:
        async def inspect(self, _reference):
            return SimpleNamespace(
                image_id="sha256:" + "5" * 64,
                source_digest="sha256:" + "f" * 64,
                architecture="arm64",
                os="linux",
                android_version="13",
                google_components="unknown",
            )

    service = AndroidImageService(resources, devices, RegistrationCatalog())
    image = await service.register({"id": "sha256:" + "5" * 64, "name": "image", "reference": "redroid/redroid:13"})
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(android_management_router(EnvironmentCheckService(None), images=service))

    with TestClient(app) as client:
        delete = client.request(
            "DELETE",
            f"/api/v1/android/management/images/{image['id']}",
            json={"requestId": "delete-unknown", "expectedRevision": 1, "deleteContent": True},
        )
        verify = client.post(
            f"/api/v1/android/management/images/{image['id']}/delete-verifications",
            json={"requestId": "delete-unknown"},
        )

    assert delete.status_code == 503, delete.text
    assert verify.status_code == 200, verify.text
    assert verify.json()["state"] == "deleted"
