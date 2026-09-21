import pytest

from autoflow.application.android.images import AndroidImageService
from autoflow.domain.android.ports import AndroidError


def test_register_image_keeps_exact_reference_and_delete_checks_device_refs():
    resources = _Resources()
    devices = _Devices()
    service = AndroidImageService(resources, devices)
    image = service.register({"id": "sha256:" + "a" * 64, "name": "候选镜像", "reference": "redroid/redroid:13"})
    assert image["imageId"] == "sha256:" + "a" * 64
    devices.items = [{"imageId": image["imageId"], "deleted": False}]
    with pytest.raises(AndroidError) as error:
        service.delete(image["id"])
    assert error.value.status == 409


class _Resources:
    def __init__(self): self.items = {}
    def get(self, kind, identifier):
        if (kind, identifier) not in self.items: raise AndroidError("NOT_FOUND", "not found", 404)
        return self.items[(kind, identifier)]
    def list(self, kind): return [value for (stored_kind, _), value in self.items.items() if stored_kind == kind]
    def save(self, kind, value): self.items[(kind, value["id"])] = value


class _Devices:
    def __init__(self): self.items = []
    def list(self): return self.items


def test_image_registration_is_idempotent_and_content_delete_requires_real_io():
    service = AndroidImageService(_Resources(), _Devices())
    request = {"id": "sha256:" + "b" * 64, "name": "image", "reference": "redroid/redroid:13"}
    first = service.register(request)
    assert service.register(request)["id"] == first["id"]
    with pytest.raises(AndroidError):
        service.delete(first["id"], delete_content=True)
    assert service.list()[0]["state"] == "registered"
