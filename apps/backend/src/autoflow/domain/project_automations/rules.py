from __future__ import annotations

import json
import math
from typing import Any
from uuid import UUID

from autoflow.domain.project_data.identity import RecordKey, encode_record_key
from autoflow.domain.project_data.query import (
    MAX_ENCODED,
    compatible,
    validate_filter,
    validate_order,
)
from autoflow.domain.projects.models import ProjectError


def validate_write(
    payload: dict[str, Any], project_id: str | None = None
) -> dict[str, Any]:
    required = {
        "name",
        "description",
        "workflowId",
        "inputPlan",
        "parameterSchema",
        "environmentPolicy",
        "runPolicy",
    }
    if set(payload) != required:
        missing, extra = required - set(payload), set(payload) - required
        field = min(missing or extra)
        raise validation_error(field, "Required" if missing else "Unexpected field")
    result = dict(payload)
    result["name"] = _text(result["name"], "name", required=True, maximum=80)
    result["description"] = _text(result["description"], "description", maximum=1000)
    result["workflowId"] = _uuid(result["workflowId"], "workflowId")
    result["inputPlan"] = _input_plan(result["inputPlan"], project_id)
    result["parameterSchema"] = _parameters(result["parameterSchema"])
    result["environmentPolicy"] = _environment(result["environmentPolicy"])
    if result["environmentPolicy"]["source"] == "inputEnvironment" and result[
        "environmentPolicy"
    ]["inputId"] not in {item["inputId"] for item in result["inputPlan"]["inputs"]}:
        raise validation_error(
            "environmentPolicy.inputId", "Must reference an input in inputPlan"
        )
    result["runPolicy"] = _run_policy(result["runPolicy"])
    return result


def _input_plan(value: Any, project_id: str | None) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"inputs"}
        or not isinstance(value["inputs"], list)
    ):
        raise validation_error("inputPlan", "Must contain inputs")
    inputs: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value["inputs"]):
        path = f"inputPlan.inputs.{index}"
        required = {
            "inputId",
            "alias",
            "tableId",
            "datasetGeneration",
            "mode",
            "required",
            "fieldBindings",
            "filter",
            "orderBy",
        }
        if (
            not isinstance(item, dict)
            or not required <= set(item)
            or set(item) - required - {"fixedRecord", "relation"}
        ):
            raise validation_error(path, "Invalid input definition")
        input_id = _uuid(item.get("inputId"), f"{path}.inputId")
        if input_id in inputs:
            raise validation_error(f"{path}.inputId", "Must be unique")
        _text(item["alias"], f"{path}.alias", required=True)
        _uuid(item["tableId"], f"{path}.tableId")
        _uuid(item["datasetGeneration"], f"{path}.datasetGeneration")
        if (
            item["mode"] not in {"independent", "fixedRecord", "related"}
            or type(item["required"]) is not bool
        ):
            raise validation_error(path, "Invalid mode or required flag")
        if (item["mode"] == "fixedRecord") != ("fixedRecord" in item) or (
            item["mode"] == "related"
        ) != ("relation" in item):
            raise validation_error(path, "Input mode does not match its reference")
        if item["mode"] == "independent" and ({"fixedRecord", "relation"} & set(item)):
            raise validation_error(path, "Independent input cannot contain a relation")
        if "fixedRecord" in item:
            _record_ref(
                item["fixedRecord"],
                path,
                project_id,
                item["tableId"],
                item["datasetGeneration"],
            )
        fields = _field_bindings(
            item["fieldBindings"],
            path,
            project_id,
            item["tableId"],
            item["datasetGeneration"],
        )
        _validate_filter_shape(item["filter"], path)
        _validate_order_shape(item["orderBy"], path)
        field_types = _filter_field_types(item["filter"], fields)
        statuses = _filter_statuses(item["filter"])
        try:
            item["filter"] = validate_filter(item["filter"], field_types, statuses)
            item["orderBy"] = validate_order(item["orderBy"], field_types)
        except ProjectError as error:
            raise validation_error(path, error.message) from error
        inputs[input_id] = item
    for input_id, item in inputs.items():
        if "relation" in item:
            _relation(item["relation"], input_id, inputs, project_id)
    return value


def _field_bindings(value, path, project_id, table_id, generation):
    if not isinstance(value, list):
        raise validation_error(f"{path}.fieldBindings", "Must be an array")
    fields: set[str] = set()
    for index, binding in enumerate(value):
        current = f"{path}.fieldBindings.{index}"
        if not isinstance(binding, dict) or set(binding) != {
            "inputFieldId",
            "inputFieldAlias",
            "fieldRef",
        }:
            raise validation_error(current, "Invalid field binding")
        field_id = _uuid(binding["inputFieldId"], f"{current}.inputFieldId")
        if field_id in fields:
            raise validation_error(f"{current}.inputFieldId", "Must be unique")
        fields.add(field_id)
        _text(binding["inputFieldAlias"], f"{current}.inputFieldAlias", required=True)
        _field_ref(
            binding["fieldRef"], f"{current}.fieldRef", project_id, table_id, generation
        )
    return {binding["fieldRef"]["fieldId"] for binding in value}


def _field_ref(value, path, project_id, table_id=None, generation=None):
    if not isinstance(value, dict) or set(value) != {
        "projectId",
        "tableId",
        "datasetGeneration",
        "fieldId",
    }:
        raise validation_error(path, "Invalid field reference")
    for key in ("projectId", "tableId", "datasetGeneration", "fieldId"):
        _uuid(value[key], f"{path}.{key}")
    if project_id is not None and value["projectId"] != project_id:
        raise validation_error(f"{path}.projectId", "Must belong to the parent project")
    if table_id is not None and (
        value["tableId"] != table_id or value["datasetGeneration"] != generation
    ):
        raise validation_error(path, "Must belong to the input table generation")


def _record_ref(value, path, project_id, table_id, generation):
    if not isinstance(value, dict) or set(value) != {
        "projectId",
        "tableId",
        "datasetGeneration",
        "recordKey",
    }:
        raise validation_error(f"{path}.fixedRecord", "Invalid record reference")
    for key in ("projectId", "tableId", "datasetGeneration"):
        _uuid(value[key], f"{path}.fixedRecord.{key}")
    if project_id is not None and value["projectId"] != project_id:
        raise validation_error(
            f"{path}.fixedRecord.projectId", "Must belong to the parent project"
        )
    if value["tableId"] != table_id or value["datasetGeneration"] != generation:
        raise validation_error(
            f"{path}.fixedRecord", "Must belong to the input table generation"
        )
    key = value["recordKey"]
    if (
        not isinstance(key, dict)
        or set(key) != {"type", "value"}
        or key.get("type") not in {"text", "integer", "uuid"}
        or not isinstance(key.get("value"), str)
    ):
        raise validation_error(
            f"{path}.fixedRecord.recordKey", "Invalid typed record key"
        )
    try:
        encode_record_key(RecordKey(key["type"], key["value"]))
    except ProjectError as error:
        raise validation_error(
            f"{path}.fixedRecord.recordKey", error.message
        ) from error


def _relation(value, input_id, inputs, project_id):
    if not isinstance(value, dict) or value.get("type") not in {
        "recordSlot",
        "fieldEquals",
        "sameRecord",
    }:
        raise validation_error("inputPlan.inputs.relation", "Invalid relation")
    expected = {
        "recordSlot": {"type", "slotId", "sourceInputId"},
        "fieldEquals": {"type", "sourceInputId", "sourceFieldRef", "targetFieldRef"},
        "sameRecord": {"type", "sourceInputId"},
    }[value["type"]]
    if set(value) != expected:
        raise validation_error(
            "inputPlan.inputs.relation", "Relation does not match type"
        )
    source_id = _uuid(value["sourceInputId"], "inputPlan.inputs.relation.sourceInputId")
    if source_id == input_id or source_id not in inputs:
        raise validation_error(
            "inputPlan.inputs.relation.sourceInputId", "Must reference another input"
        )
    if value["type"] == "recordSlot":
        _uuid(value["slotId"], "inputPlan.inputs.relation.slotId")
    if value["type"] == "sameRecord":
        source, target = inputs[source_id], inputs[input_id]
        if (source["tableId"], source["datasetGeneration"]) != (
            target["tableId"],
            target["datasetGeneration"],
        ):
            raise validation_error(
                "inputPlan.inputs.relation",
                "sameRecord inputs must use one table generation",
            )
    if value["type"] == "fieldEquals":
        source, target = inputs[source_id], inputs[input_id]
        _field_ref(
            value["sourceFieldRef"],
            "inputPlan.inputs.relation.sourceFieldRef",
            project_id,
            source["tableId"],
            source["datasetGeneration"],
        )
        _field_ref(
            value["targetFieldRef"],
            "inputPlan.inputs.relation.targetFieldRef",
            project_id,
            target["tableId"],
            target["datasetGeneration"],
        )


def _filter_field_types(node, field_ids):
    candidates = {
        field_id: {"string", "number", "boolean", "date"} for field_id in field_ids
    }

    def walk(item):
        if not isinstance(item, dict):
            return
        kind = item.get("type")
        if not isinstance(kind, str):
            return
        if kind in {"all", "any"} and isinstance(item.get("items"), list):
            for child in item["items"]:
                walk(child)
        elif kind == "not":
            walk(item.get("item"))
        elif (
            kind == "compare"
            and isinstance(item.get("fieldId"), str)
            and item["fieldId"] in candidates
        ):
            operator, present, value = (
                item.get("operator"),
                "value" in item,
                item.get("value"),
            )
            allowed = {
                kind
                for kind in candidates[item["fieldId"]]
                if operator in {"isNull", "isNotNull"}
                or (
                    operator in {"eq", "neq"}
                    and (not present or compatible(kind, value))
                )
                or (kind == "string" and operator in {"contains", "startsWith"})
                or (
                    kind in {"number", "date"}
                    and operator in {"gt", "gte", "lt", "lte"}
                    and compatible(kind, value)
                )
            }
            candidates[item["fieldId"]] &= allowed

    walk(node)
    if any(not values for values in candidates.values()):
        raise validation_error(
            "inputPlan.inputs.filter", "Conflicting field operators or values"
        )
    return {field_id: min(values) for field_id, values in candidates.items()}


def _validate_filter_shape(node: Any, path: str) -> None:
    leaves = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal leaves
        if not isinstance(item, dict) or depth > 5 or "type" not in item:
            raise validation_error(f"{path}.filter", "Invalid filter expression")
        kind = item["type"]
        if not isinstance(kind, str):
            raise validation_error(f"{path}.filter.type", "Must be a string")
        if kind in {"all", "any"}:
            if (
                set(item) != {"type", "items"}
                or not isinstance(item["items"], list)
                or len(item["items"]) > 50
            ):
                raise validation_error(f"{path}.filter", "Invalid filter group")
            for child in item["items"]:
                walk(child, depth + 1)
        elif kind == "not":
            if set(item) != {"type", "item"}:
                raise validation_error(f"{path}.filter", "Invalid not filter")
            walk(item["item"], depth + 1)
        elif kind == "compare":
            if (
                set(item) - {"type", "fieldId", "operator", "value"}
                or not isinstance(item.get("fieldId"), str)
                or not isinstance(item.get("operator"), str)
            ):
                raise validation_error(f"{path}.filter", "Invalid field comparison")
            leaves += 1
        elif kind == "status":
            if (
                set(item) - {"type", "operator", "statusId"}
                or not isinstance(item.get("operator"), str)
                or ("statusId" in item and not isinstance(item["statusId"], str))
            ):
                raise validation_error(f"{path}.filter", "Invalid status filter")
            leaves += 1
        else:
            raise validation_error(f"{path}.filter.type", "Unknown filter type")
        if leaves > 100:
            raise validation_error(f"{path}.filter", "Filter is too complex")

    walk(node, 1)
    _query_size(node, f"{path}.filter")


def _validate_order_shape(value: Any, path: str) -> None:
    if not isinstance(value, list) or len(value) > 8:
        raise validation_error(f"{path}.orderBy", "Invalid orderBy")
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) not in ({"fieldId", "direction"}, {"systemField", "direction"})
            or not isinstance(item.get("direction"), str)
        ):
            raise validation_error(f"{path}.orderBy", "Invalid orderBy")
        if not isinstance(item.get("fieldId", item.get("systemField")), str):
            raise validation_error(f"{path}.orderBy", "Invalid orderBy target")
    _query_size(value, f"{path}.orderBy")


def _query_size(value: Any, path: str) -> None:
    try:
        size = len(
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise validation_error(path, "Invalid JSON value") from error
    if size > MAX_ENCODED:
        raise validation_error(path, "Query exceeds 64 KiB")


def _filter_statuses(node):
    result = set()

    def walk(item):
        if not isinstance(item, dict):
            return
        if isinstance(item.get("statusId"), str):
            result.add(item["statusId"])
        children = item.get("items")
        if isinstance(children, list):
            for child in children:
                walk(child)
        if "item" in item:
            walk(item["item"])

    walk(node)
    return result


def _parameters(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise validation_error("parameterSchema", "Must be an array")
    seen: set[str] = set()
    result = []
    for index, item in enumerate(value):
        field = f"parameterSchema.{index}"
        if (
            not isinstance(item, dict)
            or not {"parameterId", "name", "type", "required"} <= set(item)
            or set(item) - {"parameterId", "name", "type", "required", "defaultValue"}
        ):
            raise validation_error(field, "Invalid parameter definition")
        parameter_id = _uuid(item["parameterId"], f"{field}.parameterId")
        if parameter_id in seen:
            raise validation_error(f"{field}.parameterId", "Must be unique")
        seen.add(parameter_id)
        parameter_type = item["type"]
        if parameter_type not in {"string", "number", "boolean"}:
            raise validation_error(f"{field}.type", "Invalid parameter type")
        normalized = dict(item)
        normalized["parameterId"] = parameter_id
        normalized["name"] = _text(item["name"], f"{field}.name", required=True)
        if type(item["required"]) is not bool:
            raise validation_error(f"{field}.required", "Must be a boolean")
        if "defaultValue" in item and not _scalar_matches(
            item["defaultValue"], parameter_type
        ):
            raise validation_error(
                f"{field}.defaultValue", f"Must be a {parameter_type} or null"
            )
        result.append(normalized)
    return result


def _environment(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("source") not in {
        "newFromProfile",
        "fixedEnvironment",
        "inputEnvironment",
    }:
        raise validation_error("environmentPolicy", "Invalid environment source")
    allowed = {
        "newFromProfile": {"source", "profileId", "proxyOverride"},
        "fixedEnvironment": {"source", "environmentId", "proxyOverride"},
        "inputEnvironment": {"source", "inputId", "proxyOverride"},
    }[value["source"]]
    if set(value) - allowed:
        raise validation_error("environmentPolicy", "Unexpected field")
    required_ref = {
        "fixedEnvironment": "environmentId",
        "inputEnvironment": "inputId",
    }.get(value["source"])
    if required_ref:
        _uuid(value.get(required_ref), f"environmentPolicy.{required_ref}")
    if "profileId" in value:
        _uuid(value["profileId"], "environmentPolicy.profileId")
    if "proxyOverride" in value:
        _proxy(value["proxyOverride"])
    return value


def _proxy(value: Any) -> None:
    if not isinstance(value, dict) or value.get("mode") not in {
        "sourceDefault",
        "none",
        "fixed",
        "pool",
    }:
        raise validation_error("proxyOverride", "Invalid proxy mode")
    expected = {"mode"}
    if value["mode"] == "fixed":
        expected.add("proxyId")
    if value["mode"] == "pool":
        expected.add("proxyPoolId")
    if set(value) != expected:
        raise validation_error("proxyOverride", "Proxy selection does not match mode")
    for key in expected - {"mode"}:
        _uuid(value[key], f"proxyOverride.{key}")


def _run_policy(value: Any) -> dict[str, Any]:
    required = {
        "maxTasks",
        "concurrency",
        "maxLiveInstances",
        "continueAfterFailure",
        "automaticExecutionTimeoutSeconds",
        "manualDeadlineSeconds",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise validation_error("runPolicy", "A complete run policy is required")
    for key in ("maxTasks", "concurrency", "maxLiveInstances"):
        if type(value[key]) is not int or value[key] < 1:
            raise validation_error(f"runPolicy.{key}", "Must be a positive integer")
    for key in ("automaticExecutionTimeoutSeconds", "manualDeadlineSeconds"):
        if not _finite_positive(value[key]):
            raise validation_error(
                f"runPolicy.{key}", "Must be a finite positive number"
            )
    if not 1 <= value["maxTasks"] <= 100:
        raise validation_error("runPolicy.maxTasks", "Must be between 1 and 100")
    if value["concurrency"] != 1 or value["maxLiveInstances"] != 1:
        raise validation_error(
            "runPolicy.concurrency", "PM3 supports exactly one concurrent live instance"
        )
    if type(value["continueAfterFailure"]) is not bool:
        raise validation_error("runPolicy.continueAfterFailure", "Must be a boolean")
    return value


def _finite_positive(value: Any) -> bool:
    return _finite_number(value) and value > 0


def _finite_number(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _scalar_matches(value: Any, kind: str) -> bool:
    if value is None:
        return True
    return {
        "string": lambda: isinstance(value, str),
        "number": lambda: _finite_number(value),
        "boolean": lambda: type(value) is bool,
    }[kind]()


def _text(
    value: Any, field: str, required: bool = False, maximum: int | None = None
) -> str:
    if not isinstance(value, str):
        raise validation_error(field, "Must be a string")
    value = value.strip()
    if required and not value:
        raise validation_error(field, "Must contain at least one Unicode code point")
    if maximum is not None and len(value) > maximum:
        raise validation_error(
            field, f"Must contain at most {maximum} Unicode code points"
        )
    return value


def _uuid(value: Any, field: str) -> str:
    try:
        canonical = str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise validation_error(field, "Must be a UUID")
    if type(value) is not str or value != canonical:
        raise validation_error(field, "Must be a canonical UUID")
    return canonical


def validation_error(field: str, message: str) -> ProjectError:
    return ProjectError(
        "VALIDATION_ERROR",
        "Request validation failed",
        422,
        {
            "fields": {field: message},
            "domainCode": "validation_error",
            "retryable": False,
        },
    )
