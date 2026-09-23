import pytest

from autoflow.domain.android.image_models import ImageMetadata
from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.image_catalog import ImageCatalog


def test_local_id_is_not_a_registry_digest() -> None:
    metadata = ImageMetadata(
        image_id="sha256:" + "a" * 64,
        source_digest=None,
        architecture="arm64",
        os="linux",
        android_version=None,
    )
    assert metadata.source_digest is None
    assert metadata.android_version is None


def test_tag_reference_is_not_treated_as_immutable_identity() -> None:
    metadata = ImageMetadata(
        image_id="sha256:" + "b" * 64,
        source_digest="sha256:" + "c" * 64,
        architecture="arm64",
        os="linux",
        android_version="13",
        reference="repo:latest",
    )
    assert metadata.image_id != metadata.source_digest


@pytest.mark.parametrize(
    ("reference", "code"),
    [
        ("repo;unexpected:tag", "ANDROID_IMAGE_REFERENCE_INVALID"),
        ("unapproved/repo:tag", "ANDROID_IMAGE_SOURCE_NOT_ALLOWED"),
    ],
)
@pytest.mark.asyncio
async def test_pull_rejects_disallowed_reference_before_network_side_effect(reference: str, code: str) -> None:
    pulled: list[str] = []

    class Runtime:
        async def pull_image(self, reference: str) -> None:
            pulled.append(reference)

    with pytest.raises(AndroidError) as error:
        await ImageCatalog(Runtime()).pull(reference)

    assert error.value.code == code
    assert pulled == []


@pytest.mark.parametrize("reference", ["redroid/redroid:13", "docker.io/redroid/redroid@sha256:" + "a" * 64])
@pytest.mark.asyncio
async def test_pull_accepts_approved_redroid_repository(reference: str) -> None:
    pulled: list[str] = []

    class Runtime:
        async def pull_image(self, value: str) -> None:
            pulled.append(value)

        async def inspect_image(self, _value: str) -> dict[str, str]:
            return {"imageId": "sha256:" + "b" * 64, "architecture": "arm64", "os": "linux"}

    await ImageCatalog(Runtime()).pull(reference)

    assert pulled == [reference]
