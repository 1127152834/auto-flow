#!/usr/bin/env python3
"""Run an isolated, secret-safe live verification of the model HTTP API."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import secrets
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1] / "apps" / "backend"
sys.path.insert(0, str(BACKEND / "src"))

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.credentials.system import SystemCredentialStore
from autoflow.infrastructure.database.model_providers import (
    model_repository_transaction,
)
from fastapi.testclient import TestClient

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "liquid/lfm-2.5-2.6b:free"
FALLBACK_MODEL = "openrouter/free"
SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,79}$")


class VerificationFailure(RuntimeError):
    def __init__(self, code: str, count: int | None = None) -> None:
        super().__init__(code)
        self.code = code if SAFE_CODE.fullmatch(code) else "UNSAFE_ERROR"
        self.count = count


class Report:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.refs: list[str] = []
        self.flow_completed = False

    def pass_(self, name: str, **facts: Any) -> None:
        row = {"name": name, "status": "PASS", "code": "OK", **facts}
        self.steps.append(row)
        suffix = f" count={facts['count']}" if "count" in facts else ""
        print(f"PASS {name} code=OK{suffix}")

    def fail(self, name: str, code: str, count: int | None = None) -> None:
        row: dict[str, Any] = {"name": name, "status": "FAIL", "code": code}
        if count is not None:
            row["count"] = count
        self.steps.append(row)
        suffix = f" count={count}" if count is not None else ""
        print(f"FAIL {name} code={code}{suffix}")

    def run(self, name: str, check: Callable[[], dict[str, Any] | None]) -> bool:
        try:
            self.pass_(name, **(check() or {}))
            return True
        except VerificationFailure as error:
            self.fail(name, error.code, error.count)
        except Exception:  # noqa: BLE001 - never expose a possibly secret-bearing error
            self.fail(name, "UNEXPECTED_EXCEPTION")
        return False


class TrackingCredentialStore(SystemCredentialStore):
    """Track refs before delegating every operation to the real OS store."""

    def __init__(self, report: Report) -> None:
        super().__init__()
        self.report = report

    def write(self, key: str, value: bytes) -> None:
        if key not in self.report.refs:
            self.report.refs.append(key)
        super().write(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser.parse_args()


def read_key() -> str:
    if sys.stdin.isatty():
        return getpass.getpass("OpenRouter API Key: ")
    print("OpenRouter API Key: ", end="", file=sys.stderr, flush=True)
    return sys.stdin.readline()


def normalize_key(value: str) -> str:
    value = value.strip()
    for prefix in ("router:", "userrouter:"):
        if value.casefold().startswith(prefix):
            value = value[len(prefix) :].strip()
            break
    if not value:
        raise VerificationFailure("EMPTY_API_KEY")
    return value


def error_code(response: Any) -> str:
    try:
        code = response.json().get("error", {}).get("code")
    except (AttributeError, ValueError):
        code = None
    return (
        code
        if isinstance(code, str) and SAFE_CODE.fullmatch(code)
        else "UNEXPECTED_RESPONSE"
    )


def expect(response: Any, status: int, code: str | None = None) -> dict[str, Any]:
    if response.status_code != status:
        raise VerificationFailure(error_code(response))
    body = {} if status == 204 else response.json()
    if code is not None and error_code(response) != code:
        raise VerificationFailure(error_code(response))
    return body


def assert_secret_free_response(response: Any, key: str) -> None:
    if key.encode() in response.content:
        raise VerificationFailure("RESPONSE_CONTAINS_KEY")
    try:
        body = response.json()
    except ValueError:
        return

    def contains_private_field(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                name in {"apiKey", "secretRef"} or contains_private_field(item)
                for name, item in value.items()
            )
        if isinstance(value, list):
            return any(contains_private_field(item) for item in value)
        return False

    if contains_private_field(body):
        raise VerificationFailure("RESPONSE_CONTAINS_PRIVATE_FIELD")


def provider_input(name: str, key: str) -> dict[str, Any]:
    return {
        "name": name,
        "presetId": "openrouter",
        "providerKind": "openai-compatible",
        "baseUrl": BASE_URL,
        "apiKey": key,
        "enabled": True,
        "description": "isolated live verification",
    }


def model_input(
    model_key: str, display_name: str, context: int | None
) -> dict[str, Any]:
    return {
        "modelKey": model_key,
        "displayName": display_name,
        "tagsJson": ["live-verification"],
        "contextWindow": context,
        "enabled": True,
        "description": "temporary verification model",
    }


def client_for(data_dir: str, token: str, store: SystemCredentialStore) -> TestClient:
    app = create_app(
        Settings(
            data_dir=data_dir, instance_id="openrouter-live", instance_token=token
        ),
        credential_store=store,
    )
    return TestClient(app, headers={"x-autoflow-token": token})


def internal_provider(client: TestClient, provider_id: str) -> Any:
    return client.app.state.model_service.get_provider(provider_id)


def verify(report: Report, key: str, data_dir: str, requested_model: str) -> None:
    token = secrets.token_urlsafe(24)
    store = TrackingCredentialStore(report)
    zero_id = main_id = selected_id = manual_id = None

    with client_for(data_dir, token, store) as client:
        initial_total = expect(client.get("/api/v1/model-providers"), 200)["total"]

        def preview() -> dict[str, Any]:
            body = expect(
                client.post(
                    "/api/v1/model-providers/connection-preview",
                    json=provider_input("Preview", key),
                ),
                200,
            )
            current = expect(client.get("/api/v1/model-providers"), 200)["total"]
            if current != initial_total:
                raise VerificationFailure("PREVIEW_PERSISTED", current)
            return {"count": body["total"]}

        report.run("connection_preview_not_persisted", preview)

        bad_key = f"invalid-{secrets.token_urlsafe(18)}"
        report.run(
            "invalid_key_rejected",
            lambda: (
                expect(
                    client.post(
                        "/api/v1/model-providers/connection-preview",
                        json=provider_input("Invalid key", bad_key),
                    ),
                    409,
                    "MODEL_PROVIDER_AUTH_FAILED",
                )
                and None
            ),
        )

        zero_name = f"OpenRouter zero {secrets.token_hex(4)}"
        zero_response = client.post(
            "/api/v1/model-providers/connect",
            json={"provider": provider_input(zero_name, key), "selectedModels": []},
        )
        if zero_response.status_code == 201:
            zero = zero_response.json()
            zero_id = zero["id"]
            zero_ref = internal_provider(client, zero_id).secret_ref
            if zero_ref:
                report.refs.append(zero_ref)
            if zero["models"] == []:
                report.pass_("connect_zero_models", count=0)
            else:
                report.fail(
                    "connect_zero_models", "EXPECTED_ZERO_MODELS", len(zero["models"])
                )
        else:
            report.fail("connect_zero_models", error_code(zero_response))

        discovery_response = client.get(
            f"/api/v1/model-providers/{zero_id}/models/discover"
            if zero_id
            else "/api/v1/model-providers/missing/models/discover"
        )
        catalog: dict[str, Any] | None = None
        if discovery_response.status_code == 200:
            discovery = discovery_response.json()
            candidates = {
                item.get("modelKey"): item
                for item in discovery.get("items", [])
                if isinstance(item, dict)
                and isinstance(item.get("modelKey"), str)
                and isinstance(item.get("displayName"), str)
                and bool(item["displayName"].strip())
                and type(item.get("contextWindow")) is int
                and item["contextWindow"] > 0
            }
            choices = tuple(dict.fromkeys((requested_model, FALLBACK_MODEL)))
            catalog = next(
                (candidates[item] for item in choices if item in candidates), None
            )
            if catalog is None:
                report.fail(
                    "discover_catalog_name_context",
                    "PREFERRED_MODEL_NOT_FOUND",
                    len(candidates),
                )
            else:
                report.pass_("discover_catalog_name_context", count=len(candidates))
        else:
            report.fail("discover_catalog_name_context", error_code(discovery_response))

        if catalog is None:
            raise VerificationFailure("NO_ELIGIBLE_MODEL")

        selected = model_input(
            catalog["modelKey"], catalog["displayName"], catalog.get("contextWindow")
        )
        main_name = f"OpenRouter live {secrets.token_hex(4)}"
        connected_response = client.post(
            "/api/v1/model-providers/connect",
            json={
                "provider": provider_input(main_name, key),
                "selectedModels": [selected],
            },
        )
        if connected_response.status_code != 201:
            raise VerificationFailure(error_code(connected_response))
        main = connected_response.json()
        main_id, selected_id = main["id"], main["models"][0]["id"]
        main_ref = internal_provider(client, main_id).secret_ref
        if main_ref:
            report.refs.append(main_ref)
        report.pass_("connect_with_model", count=len(main["models"]))

        def secret_boundaries() -> dict[str, Any]:
            responses = (
                connected_response,
                client.get("/api/v1/model-providers"),
                client.get(f"/api/v1/model-providers/{main_id}"),
            )
            for response in responses:
                expect(response, 201 if response is connected_response else 200)
                assert_secret_free_response(response, key)
            database = client.app.state.paths.database
            if key.encode() in database.read_bytes():
                raise VerificationFailure("DATABASE_CONTAINS_KEY")
            return {"count": len(responses)}

        report.run("secret_free_responses_and_database", secret_boundaries)

        report.run(
            "get_and_list_provider",
            lambda: (
                {"count": expect(client.get("/api/v1/model-providers"), 200)["total"]}
                if expect(client.get(f"/api/v1/model-providers/{main_id}"), 200)["id"]
                == main_id
                else (_ for _ in ()).throw(VerificationFailure("PROVIDER_ID_MISMATCH"))
            ),
        )

        metadata = {
            "name": main_name + " updated",
            "description": "updated",
            "enabled": True,
        }
        report.run(
            "provider_metadata_update",
            lambda: (
                None
                if expect(
                    client.put(f"/api/v1/model-providers/{main_id}", json=metadata), 200
                )["description"]
                == "updated"
                else (_ for _ in ()).throw(VerificationFailure("METADATA_NOT_UPDATED"))
            ),
        )
        main_name = metadata["name"]

        before = expect(client.get(f"/api/v1/model-providers/{main_id}"), 200)
        old_ref = internal_provider(client, main_id).secret_ref

        def rejected_connection(payload: dict[str, Any], wanted: str) -> dict[str, Any]:
            response = client.put(
                f"/api/v1/model-providers/{main_id}/connection", json=payload
            )
            expect(
                response, 409 if wanted == "MODEL_PROVIDER_AUTH_FAILED" else 422, wanted
            )
            after = expect(client.get(f"/api/v1/model-providers/{main_id}"), 200)
            fields = ("name", "presetId", "providerKind", "baseUrl", "description")
            if any(after[field] != before[field] for field in fields):
                raise VerificationFailure("CONFIG_OVERWRITTEN")
            if (
                internal_provider(client, main_id).secret_ref != old_ref
                or store.read(old_ref) != key.encode()
            ):
                raise VerificationFailure("CREDENTIAL_OVERWRITTEN")
            return {"count": 1}

        wrong_key_payload = provider_input(main_name + " rejected", bad_key)
        report.run(
            "connection_wrong_key_preserves_state",
            lambda: rejected_connection(
                wrong_key_payload, "MODEL_PROVIDER_AUTH_FAILED"
            ),
        )
        wrong_url_payload = provider_input(
            main_name + " rejected", "replacement-not-sent"
        )
        wrong_url_payload["baseUrl"] = BASE_URL + "#invalid"
        report.run(
            "connection_bad_url_preserves_state",
            lambda: rejected_connection(
                wrong_url_payload, "MODEL_PROVIDER_BASE_URL_INVALID"
            ),
        )

        manual = model_input("autoflow-live-manual", "Manual", 1024)
        created_response = client.post(
            f"/api/v1/model-providers/{main_id}/models", json=manual
        )
        if created_response.status_code == 201:
            manual_id = created_response.json()["id"]
            report.pass_("model_create", count=1)
        else:
            report.fail("model_create", error_code(created_response))

        report.run(
            "model_duplicate_rejected",
            lambda: (
                expect(
                    client.post(
                        f"/api/v1/model-providers/{main_id}/models", json=manual
                    ),
                    409,
                    "MODEL_EXISTS",
                )
                and None
            ),
        )
        invalid = {**manual, "modelKey": "invalid-context", "contextWindow": 0}
        report.run(
            "model_field_validation",
            lambda: (
                expect(
                    client.post(
                        f"/api/v1/model-providers/{main_id}/models", json=invalid
                    ),
                    422,
                    "VALIDATION_ERROR",
                )
                and None
            ),
        )
        changed_id = {**manual, "modelKey": "changed-id"}
        report.run(
            "model_id_immutable",
            lambda: (
                expect(
                    client.put(f"/api/v1/models/{manual_id}", json=changed_id),
                    422,
                    "VALIDATION_ERROR",
                )
                and None
            ),
        )
        edited = {**manual, "displayName": "Manual edited", "description": "edited"}
        report.run(
            "model_update",
            lambda: (
                None
                if expect(client.put(f"/api/v1/models/{manual_id}", json=edited), 200)[
                    "displayName"
                ]
                == "Manual edited"
                else (_ for _ in ()).throw(VerificationFailure("MODEL_NOT_UPDATED"))
            ),
        )

        def double_filter() -> dict[str, Any]:
            enabled = expect(client.get("/api/v1/models/options"), 200)["total"]
            disabled_model = {**selected, "enabled": False}
            expect(
                client.put(f"/api/v1/models/{selected_id}", json=disabled_model), 200
            )
            without_model = expect(client.get("/api/v1/models/options"), 200)["total"]
            expect(
                client.put(
                    f"/api/v1/model-providers/{main_id}",
                    json={
                        "name": main_name,
                        "description": "updated",
                        "enabled": False,
                    },
                ),
                200,
            )
            without_provider = expect(client.get("/api/v1/models/options"), 200)[
                "total"
            ]
            expect(
                client.put(
                    f"/api/v1/model-providers/{main_id}",
                    json={"name": main_name, "description": "updated", "enabled": True},
                ),
                200,
            )
            expect(client.put(f"/api/v1/models/{selected_id}", json=selected), 200)
            if not (
                enabled >= 2 and without_model == enabled - 1 and without_provider == 0
            ):
                raise VerificationFailure("OPTIONS_FILTER_MISMATCH", without_provider)
            return {"count": enabled}

        report.run("enabled_double_filter", double_filter)
        report.run(
            "model_delete",
            lambda: expect(client.delete(f"/api/v1/models/{manual_id}"), 204) and None,
        )

        def generation() -> dict[str, Any]:
            body = expect(
                client.post(
                    f"/api/v1/model-providers/{main_id}/models/test",
                    json={"modelKey": catalog["modelKey"]},
                ),
                200,
            )
            length = len(body.get("outputPreview", ""))
            if not 1 <= length <= 240:
                raise VerificationFailure("OUTPUT_PREVIEW_INVALID", length)
            return {"count": 1, "outputLength": length}

        report.run("small_live_generation", generation)

    recreated_store = TrackingCredentialStore(report)
    with client_for(data_dir, token, recreated_store) as client:

        def persisted() -> dict[str, Any]:
            providers = expect(client.get("/api/v1/model-providers"), 200)
            current = expect(client.get(f"/api/v1/model-providers/{main_id}"), 200)
            ref = internal_provider(client, main_id).secret_ref
            if current["models"][0]["modelKey"] != catalog["modelKey"]:
                raise VerificationFailure("MODEL_NOT_PERSISTED")
            if recreated_store.read(ref) != key.encode():
                raise VerificationFailure("CREDENTIAL_NOT_PERSISTED")
            return {"count": providers["total"]}

        report.run("recreate_app_persistence_and_credential", persisted)
        report.run(
            "provider_test",
            lambda: {
                "count": expect(
                    client.post(f"/api/v1/model-providers/{main_id}/test"), 200
                )["total"]
            },
        )

        def cascade_delete() -> dict[str, Any]:
            ref = internal_provider(client, main_id).secret_ref
            expect(client.delete(f"/api/v1/model-providers/{main_id}"), 204)
            expect(
                client.get(f"/api/v1/model-providers/{main_id}"),
                404,
                "MODEL_PROVIDER_NOT_FOUND",
            )
            expect(
                client.delete(f"/api/v1/models/{selected_id}"), 404, "MODEL_NOT_FOUND"
            )
            if recreated_store.read(ref) is not None:
                raise VerificationFailure("CREDENTIAL_NOT_DELETED")
            return {"count": 1}

        report.run("provider_cascade_and_credential_cleanup", cascade_delete)
        if zero_id:
            report.run(
                "zero_provider_cleanup",
                lambda: (
                    expect(client.delete(f"/api/v1/model-providers/{zero_id}"), 204)
                    and None
                ),
            )

        def empty_state() -> dict[str, Any]:
            providers = expect(client.get("/api/v1/model-providers"), 200)["total"]
            options = expect(client.get("/api/v1/models/options"), 200)["total"]
            with model_repository_transaction(
                client.app.state.session_factory
            ) as repository:
                intents = repository.list_cleanup()
            if providers or options or intents:
                raise VerificationFailure(
                    "DELETE_STATE_NOT_EMPTY", providers + options + len(intents)
                )
            return {"count": 0}

        report.run("deleted_state_empty", empty_state)

    with client_for(data_dir, token, TrackingCredentialStore(report)) as client:

        def rebuilt_empty() -> dict[str, Any]:
            providers = expect(client.get("/api/v1/model-providers"), 200)["total"]
            options = expect(client.get("/api/v1/models/options"), 200)["total"]
            if providers or options:
                raise VerificationFailure(
                    "REBUILT_STATE_NOT_EMPTY", providers + options
                )
            return {"count": 0}

        report.run("rebuild_after_delete_empty", rebuilt_empty)
    report.flow_completed = not any(step["status"] == "FAIL" for step in report.steps)


def cleanup_refs(report: Report, store: SystemCredentialStore | None = None) -> None:
    try:
        store = store or SystemCredentialStore()
    except Exception:  # noqa: BLE001 - keep credential backend details out of output
        report.fail("finally_credential_cleanup", "CREDENTIAL_STORE_UNAVAILABLE")
        return
    remaining = 0
    for ref in dict.fromkeys(report.refs):
        try:
            store.delete(ref)
            remaining += store.read(ref) is not None
        except Exception:  # noqa: BLE001 - keep credential backend details out of output
            remaining += 1
    if remaining:
        report.fail(
            "finally_credential_cleanup", "CREDENTIAL_CLEANUP_FAILED", remaining
        )
    else:
        report.pass_("finally_credential_cleanup", count=len(set(report.refs)))


def main() -> int:
    args = parse_args()
    report = Report()
    try:
        key = normalize_key(read_key())
        with tempfile.TemporaryDirectory(
            prefix="autoflow-openrouter-live-"
        ) as data_dir:
            try:
                verify(report, key, data_dir, args.model)
            except VerificationFailure as error:
                report.fail("verification_flow", error.code, error.count)
            except Exception:  # noqa: BLE001 - never expose a possibly secret-bearing error
                report.fail("verification_flow", "UNEXPECTED_EXCEPTION")
            finally:
                cleanup_refs(report)
        key = ""
    except VerificationFailure as error:
        report.fail("input", error.code, error.count)
    except (EOFError, KeyboardInterrupt):
        report.fail("input", "INPUT_CANCELLED")

    passed = sum(step["status"] == "PASS" for step in report.steps)
    failed = len(report.steps) - passed
    result = {
        "status": "PASS" if failed == 0 else "FAIL",
        "summary": {"passed": passed, "failed": failed},
        "routesCovered": 14 if report.flow_completed and failed == 0 else None,
        "generationRequestsMaximum": 1,
        "requestedModel": args.model,
        "credentialRefsCreated": len(set(report.refs)),
        "steps": report.steps,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{'PASS' if failed == 0 else 'FAIL'} summary code={'OK' if failed == 0 else 'CHECKS_FAILED'} count={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
