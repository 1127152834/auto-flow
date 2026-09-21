import pytest

from autoflow.application.android.fleet import AndroidFleet


@pytest.mark.asyncio
async def test_listing_profiles_does_not_persist_a_default_template() -> None:
    resources = _Resources()
    fleet = AndroidFleet(_Devices(), resources, None, None)

    assert await fleet.profiles() == []
    assert resources.saved == []


class _Resources:
    def __init__(self):
        self.saved = []

    def list(self, kind):
        return []

    def save(self, kind, item):
        self.saved.append((kind, item))


class _Devices:
    async def environment(self):
        return {"images": [{"id": "sha256:" + "a" * 64}]}
