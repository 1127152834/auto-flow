from __future__ import annotations

from autoflow.infrastructure.filesystem.assistant_files import AssistantFileStore


def test_large_values_use_artifact_references_and_hydrate_only_at_provider_boundary(
    tmp_path,
) -> None:
    store = AssistantFileStore(tmp_path)
    large = {"content": "中" * 70_000, "count": 7}

    compact = store.externalize(large)

    assert compact["artifactRef"].startswith("assistant-artifact://")
    assert compact["mediaType"] == "application/json"
    assert compact["size"] > 64 * 1024
    assert store.hydrate_value(compact) == large
    path, media_type = store.artifact_file(compact["artifactRef"])
    assert path.read_bytes()
    assert media_type == "application/json"


def test_public_messages_keep_image_references_instead_of_inlining_base64(tmp_path) -> None:
    store = AssistantFileStore(tmp_path)
    reference = store.store_images(["data:image/png;base64,YQ=="])[0]

    messages = store.public_messages(({"role": "user", "images": [reference]},))

    assert messages == [{"role": "user", "images": [reference]}]
    path, media_type = store.artifact_file(reference)
    assert path.read_bytes() == b"a"
    assert media_type == "image/png"
