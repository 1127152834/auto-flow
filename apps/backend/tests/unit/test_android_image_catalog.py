from autoflow.domain.android.image_models import ImageMetadata


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
