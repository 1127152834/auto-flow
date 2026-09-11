"""Publish proxy contracts before mounting their implemented routes."""

from typing import Any

from pydantic.json_schema import models_json_schema

from . import proxy_schemas as schemas

PROXY_SCHEMAS = (
    schemas.ApiError, schemas.ErrorResponse, schemas.Capability, schemas.Endpoint,
    schemas.HealthSnapshot, schemas.ConnectionView, schemas.ConnectionList,
    schemas.ConnectionCreate, schemas.ConnectionUpdate, schemas.ApiKeyUpdate,
    schemas.SyncSnapshot, schemas.ProxyView, schemas.ProxyPage, schemas.ProxyUpdate,
    schemas.ResourceReference, schemas.ProxyReferences, schemas.GroupView,
    schemas.GroupPage, schemas.GroupCreate, schemas.GroupUpdate, schemas.GroupReferences,
    schemas.LocationView, schemas.LocationList, schemas.RotationSchedule,
    schemas.IpAllowlist, schemas.CredentialView, schemas.OperationView, schemas.ActionResult,
    schemas.ProbeRequest,
    schemas.ExpectedRevision, schemas.RelocateRequest, schemas.RotationScheduleUpdate,
    schemas.IpAllowlistUpdate, schemas.AccountSummary, schemas.UsagePoint, schemas.UsageView,
)


def add_proxy_schemas(document: dict[str, Any]) -> None:
    _, definitions = models_json_schema(
        [(model, "validation") for model in PROXY_SCHEMAS],
        ref_template="#/components/schemas/{model}",
    )
    target = document.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in definitions.get("$defs", {}).items():
        target.setdefault(name, definition)
