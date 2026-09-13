"""Publish frontend service contracts without installing automation business routes."""

from typing import Any

from pydantic.json_schema import models_json_schema

from .workflow_studio_schemas import StudioCommandLookup, StudioCommandReceipt


def add_workflow_studio_schemas(document: dict[str, Any]) -> None:
    _, definitions = models_json_schema(
        [(model, "validation") for model in (StudioCommandReceipt, StudioCommandLookup)],
        ref_template="#/components/schemas/{model}",
    )
    target = document.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in definitions.get("$defs", {}).items():
        target.setdefault(name, definition)
