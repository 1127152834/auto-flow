"""Publish frontend service contracts without installing automation business routes."""

from typing import Any

from pydantic.json_schema import models_json_schema

from . import workflow_studio_schemas as schemas

STUDIO_SCHEMAS = (
    schemas.StudioCommandReceipt,
    schemas.StudioCommandLookup,
    schemas.StudioImageAsset,
    schemas.StudioImageUploadResult,
    schemas.StudioImageMutationResult,
    schemas.StudioImageRenameResult,
    schemas.StudioImageFolderCreated,
    schemas.StudioImageFolderRenamed,
    schemas.StudioImageFolderDeleted,
    schemas.StudioImageMoved,
    schemas.StudioInputPromptRequest,
    schemas.StudioInputPromptResult,
    schemas.StudioInputPromptState,
    schemas.StudioSelectorTestRequest,
    schemas.StudioSelectorTestResult,
    schemas.StudioSimilarPickerResult,
    schemas.StudioBrowserStatus,
    schemas.StudioJsScriptRequest,
    schemas.StudioJsScriptState,
    schemas.StudioJsScriptClaim,
    schemas.StudioJsScriptResult,
)


def add_workflow_studio_schemas(document: dict[str, Any]) -> None:
    _, definitions = models_json_schema(
        [(model, "validation") for model in STUDIO_SCHEMAS],
        ref_template="#/components/schemas/{model}",
    )
    target = document.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in definitions.get("$defs", {}).items():
        target.setdefault(name, definition)
