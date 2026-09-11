from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.providers.kernel.catalog import current_platform_tag, executable_path


def test_profile_bootstrap_uses_the_real_installed_kernel_lookup(tmp_path) -> None:
    app = create_app(
        Settings(data_dir=str(tmp_path), instance_id="integration", instance_token="secret")
    )
    version = "146.0.7680.80"
    directory = app.state.paths.kernels / f"chromium-{version}"
    executable = executable_path(directory, current_platform_tag())
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"kernel")

    with TestClient(app, headers={"x-autoflow-token": "secret"}) as client:
        response = client.post(
            "/api/v1/profiles",
            json={"name": "真实内核扫描", "browserVersion": version},
        )

    assert response.status_code == 201, response.text
    assert response.json()["browserVersion"] == version
