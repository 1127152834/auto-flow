import pytest

from autoflow.application.android.fleet import AndroidFleet


@pytest.mark.asyncio
async def test_listing_profiles_does_not_persist_a_default_template() -> None:
    resources = _Resources()
    fleet = AndroidFleet(_Devices(), resources, None, None)

    assert await fleet.profiles() == []
    assert resources.saved == []


@pytest.mark.asyncio
async def test_listing_profiles_does_not_expose_archive_request_id() -> None:
    resources = _Resources()
    resources.items = [
        {
            "id": "profile-1",
            "revision": 2,
            "name": "标准",
            "imageId": "sha256:" + "a" * 64,
            "width": 720,
            "height": 1280,
            "dpi": 320,
            "cpu": 1,
            "memoryMb": 1536,
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "shellRoot": "unknown",
            "applicationRoot": "unknown",
            "archived": True,
            "archiveRequestId": "private-replay-key",
        }
    ]
    fleet = AndroidFleet(_Devices(), resources, None, None)

    result = await fleet.profiles()

    assert result[0]["id"] == "profile-1"
    assert "archiveRequestId" not in result[0]


class _Resources:
    def __init__(self):
        self.saved = []
        self.items = []

    def list(self, kind):
        return list(self.items) if kind == "profile" else []

    def save(self, kind, item):
        self.saved.append((kind, item))


class _Devices:
    async def environment(self):
        return {"images": [{"id": "sha256:" + "a" * 64}]}
