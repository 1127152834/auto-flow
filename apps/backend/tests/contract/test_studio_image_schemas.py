import pytest
from pydantic import ValidationError

from autoflow.adapters.http import workflow_studio_schemas as schemas
from autoflow.bootstrap.schema_export import export_schema

ASSET = {
    "id": "image-1",
    "name": "image.png",
    "originalName": "图像.png",
    "size": 4,
    "uploadedAt": "2026-09-14T00:00:00Z",
    "folder": "",
    "extension": ".png",
}


def test_upload_and_rename_require_the_asset_envelope_used_by_the_frontend():
    upload = schemas.StudioImageUploadResult.model_validate({"asset": ASSET})
    assert upload.asset.original_name == "图像.png"
    rename = schemas.StudioImageRenameResult.model_validate(
        {"success": True, "asset": ASSET}
    )
    assert rename.asset.id == upload.asset.id
    with pytest.raises(ValidationError):
        schemas.StudioImageUploadResult.model_validate(ASSET)
    with pytest.raises(ValidationError):
        schemas.StudioImageRenameResult.model_validate({"success": True})


@pytest.mark.parametrize("field", list(ASSET))
def test_asset_rejects_missing_required_metadata(field):
    payload = {key: value for key, value in ASSET.items() if key != field}
    with pytest.raises(ValidationError):
        schemas.StudioImageAsset.model_validate(payload)


@pytest.mark.parametrize("size", [-1, 1.5, "4", True, 9_007_199_254_740_992])
def test_image_size_is_a_nonnegative_safe_integer(size):
    with pytest.raises(ValidationError):
        schemas.StudioImageAsset.model_validate({**ASSET, "size": size})


@pytest.mark.parametrize(
    "path", [None, "data:image/png;base64,eA==", "/workspace/image.png"]
)
def test_image_path_is_optional_and_existing_extensions_are_preserved(path):
    value = schemas.StudioImageAsset.model_validate(
        {**ASSET, "path": path, "dataUrl": "fixture"}
    )
    assert value.path == path
    assert value.model_dump(by_alias=True)["dataUrl"] == "fixture"


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (schemas.StudioImageFolderCreated, "path", "a"),
        (schemas.StudioImageFolderRenamed, "newPath", "b"),
        (schemas.StudioImageFolderDeleted, "deletedCount", 2),
        (schemas.StudioImageMoved, "newFolder", ""),
    ],
)
def test_mutations_require_the_confirmed_location_or_count(model, field, value):
    payload = {"success": True, field: value}
    assert model.model_validate(payload).model_dump(by_alias=True) == payload
    with pytest.raises(ValidationError):
        model.model_validate({"success": True})
    with pytest.raises(ValidationError):
        model.model_validate({**payload, "success": "true"})


def test_image_contracts_are_published_by_the_existing_exporter():
    definitions = export_schema()["components"]["schemas"]
    assert (
        definitions["StudioImageUploadResult"]["properties"]["asset"]["$ref"]
        == "#/components/schemas/StudioImageAsset"
    )
    assert definitions["StudioImageAsset"]["properties"]["size"]["minimum"] == 0
