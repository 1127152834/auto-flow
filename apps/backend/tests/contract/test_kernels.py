from fastapi.testclient import TestClient


def test_default_uses_revision_and_requires_an_installed_kernel(client: TestClient) -> None:
    kernel = {"edition": "public", "version": "146.0.1.1"}
    body = {"expectedRevision": 0, "kernel": kernel}

    first = client.put("/api/v1/kernels/default", json=body)
    stale = client.put("/api/v1/kernels/default", json=body)
    missing = client.put(
        "/api/v1/kernels/default",
        json={"expectedRevision": 1, "kernel": {"edition": "licensed", "version": "151.0.1.1"}},
    )

    assert first.status_code == 200
    assert first.json() == {"revision": 1, "kernel": kernel}
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "KERNEL_DEFAULT_CONFLICT"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "KERNEL_NOT_FOUND"


def test_catalog_and_installed_remain_available_offline(client: TestClient) -> None:
    catalog = client.get("/api/v1/kernels/catalog")
    installed = client.get("/api/v1/kernels/installed")
    refreshed = client.post("/api/v1/kernels/check-update")

    assert catalog.status_code == installed.status_code == refreshed.status_code == 200
    assert catalog.json()["catalogError"] == "CloakBrowser catalog is unavailable"
    assert catalog.json()["installed"] == installed.json()["items"]
    assert installed.json()["items"][0]["edition"] == "public"


def test_license_contract_never_returns_or_echoes_the_key(client: TestClient) -> None:
    secret = "invalid-secret-license"
    invalid = client.post("/api/v1/kernels/license", json={"licenseKey": secret})
    valid = client.post("/api/v1/kernels/license", json={"licenseKey": "valid-license"})

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "LICENSE_INVALID"
    assert secret not in invalid.text
    assert valid.status_code == 200
    assert "licenseKey" not in valid.text
    assert valid.json() == {
        "configured": True,
        "valid": True,
        "plan": "pro",
        "expires": None,
        "seats": None,
    }
    assert client.delete("/api/v1/kernels/license").status_code == 204


def test_download_operations_cancel_and_unknown_operation(client: TestClient) -> None:
    started = client.post(
        "/api/v1/kernels/download",
        json={"edition": "public", "version": "146.0.7680.80", "releaseChannel": "stable"},
    )

    assert started.status_code == 202
    operation = started.json()
    assert operation["state"] == "queued"
    assert client.get("/api/v1/kernels/operations").json() == {"items": [operation]}
    assert client.post(f"/api/v1/kernels/operations/{operation['id']}/cancel").status_code == 202
    missing = client.post("/api/v1/kernels/operations/missing/cancel")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "KERNEL_OPERATION_NOT_FOUND"


def test_concurrent_install_returns_kernel_busy(client: TestClient) -> None:
    client.app.state.kernel_service.operations.busy = True

    response = client.post(
        "/api/v1/kernels/download",
        json={"edition": "public", "version": "146.0.7680.80", "releaseChannel": "stable"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "KERNEL_BUSY"


def test_delete_clears_default_but_keeps_profile_reference(client: TestClient, profile_payload: dict) -> None:
    kernel = {"edition": "public", "version": "146.0.1.1"}
    assert client.put(
        "/api/v1/kernels/default", json={"expectedRevision": 0, "kernel": kernel}
    ).status_code == 200
    profile = client.post("/api/v1/profiles", json=profile_payload)
    assert profile.status_code == 201

    deleted = client.delete("/api/v1/kernels/146.0.1.1?edition=public")

    assert deleted.status_code == 204
    assert client.get("/api/v1/kernels/default").json() == {"revision": 2, "kernel": None}
    assert client.get(f"/api/v1/profiles/{profile.json()['id']}").json()["browserVersion"] == "146.0.1.1"
    missing = client.delete("/api/v1/kernels/146.0.1.1?edition=public")
    assert missing.status_code == 404


def test_internal_kernel_resolution_requires_host_token_and_a_ref(client: TestClient) -> None:
    unauthorized = client.post(
        "/internal/kernels/resolve",
        json={"edition": "public", "version": "146.0.1.1"},
    )
    assert unauthorized.status_code == 401
    authorized = client.post(
        "/internal/kernels/resolve",
        json={"edition": "public", "version": "146.0.1.1"},
        headers={"x-autoflow-host-token": "host-secret"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["executablePath"].endswith(
        "/data/kernels/chromium-146.0.1.1/chrome.exe"
    )


def test_kernel_openapi_contains_routes_and_never_internal_path(client: TestClient) -> None:
    document = client.get("/openapi.json").json()
    assert "/api/v1/kernels/default" in document["paths"]
    assert "/api/v1/kernels/{version}" in document["paths"]
    assert "/internal/kernels/resolve" not in document["paths"]
    license_key = document["components"]["schemas"]["LicenseWrite"]["properties"]["licenseKey"]
    assert license_key["writeOnly"] is True
