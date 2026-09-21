from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CAPABILITIES = (
    REPOSITORY_ROOT / "docs/migration/studio-frontend-completion/capabilities.json"
)
SUPPORT = (
    REPOSITORY_ROOT
    / "docs/migration/studio-frontend-completion/backend-support-mapping.json"
)
PROVENANCE = (
    REPOSITORY_ROOT / "docs/migration/studio-backend-migration/source-provenance.json"
)
FROZEN_COMMIT = "5ccb900e8dcf1530aae66f676d87593c416c7ebb"
EXPECTED_MILESTONES = {"B1": 5, "B2": 30, "B3": 21, "B4": 88, "B5": 22, "B6": 47}
EXPECTED_CLASSIFICATIONS = {"原版直接迁入": 110, "AutoFlow必要适配": 103}
ACCEPTANCE_STATUSES = {
    "已实现且已验收",
    "已实现待验收",
    "尚未实现",
    "外部等待",
    "明确排除",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _node_type(row: dict[str, object]) -> str:
    for key in ("nodeType", "type", "id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    raise AssertionError("capability is missing its node type")


def _class_node(path: Path, symbol: str) -> ast.ClassDef:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == symbol:
            return node
    raise AssertionError(f"{symbol} is not defined in {path}")


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _registered_manually(path: Path, symbol: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "register" or len(node.args) != 1:
            continue
        if isinstance(node.args[0], ast.Name) and node.args[0].id == symbol:
            return True
    return False


def _executor_submodules() -> set[str]:
    path = REPOSITORY_ROOT / "reference/WebRPA/backend/app/executors/__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_SUBMODULES"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            return set(value)
    raise AssertionError("frozen executor package is missing _SUBMODULES")


def test_all_approved_nodes_have_traceable_backend_sources_and_unique_cases() -> None:
    rows = _load(CAPABILITIES)
    support_rows = _load(SUPPORT)["sharedCapabilities"]
    support_ids = {row["id"] for row in support_rows}

    assert len(rows) == 213
    assert len(support_rows) == 13
    assert "BE.SUPPORT.assistant-langgraph" in support_ids

    node_types: set[str] = set()
    case_ids: set[str] = set()
    milestones: dict[str, int] = {}
    classifications: dict[str, int] = {}
    registrations: dict[str, int] = {}
    submodules = _executor_submodules()

    for row in rows:
        node_type = _node_type(row)
        assert node_type not in node_types
        node_types.add(node_type)

        migration = row["backendMigration"]
        assert migration["status"] in ACCEPTANCE_STATUSES
        source = migration["source"]
        source_path = REPOSITORY_ROOT / source["path"]
        assert source["commit"] == FROZEN_COMMIT
        assert source["productVersion"] == "3.2.0"
        assert source["licensePath"] == "LICENSE.WebRPA"
        assert source_path.is_file()
        class_node = _class_node(source_path, source["symbol"])
        assert source["line"] == class_node.lineno
        assert source_path.stem in submodules
        if source["registration"] == "decorator":
            assert "register_executor" in {
                _decorator_name(item) for item in class_node.decorator_list
            }
        else:
            assert source["registration"] == "registry.register"
            assert _registered_manually(source_path, source["symbol"])
        execute_line = source.get("executeLine")
        assert isinstance(execute_line, int)
        if source.get("executeInherited"):
            assert source.get("executeOwner") == "AppriseNotifyExecutor"
            assert execute_line == 23
        else:
            assert execute_line > source["line"]

        milestones[migration["milestone"]] = (
            milestones.get(migration["milestone"], 0) + 1
        )
        classification = migration["classification"]
        classifications[classification] = classifications.get(classification, 0) + 1
        registration = source["registration"]
        registrations[registration] = registrations.get(registration, 0) + 1
        assert set(migration["sharedCapabilityRefs"]).issubset(support_ids)

        cases = migration["acceptanceCases"]
        assert [case["id"] for case in cases] == [
            f"BE.{node_type}.source-parity",
            f"BE.{node_type}.contract",
            f"BE.{node_type}.real-execution",
        ]
        for case in cases:
            assert case["status"] in ACCEPTANCE_STATUSES
            if case["status"] == "尚未实现":
                assert case["evidencePath"] is None
            elif case["status"] == "已实现且已验收":
                evidence = case["evidencePath"]
                assert isinstance(evidence, str) and evidence
                assert (REPOSITORY_ROOT / evidence).is_file()
            elif case["evidencePath"] is not None:
                assert (REPOSITORY_ROOT / case["evidencePath"]).is_file()
            assert case["id"] not in case_ids
            case_ids.add(case["id"])

    assert milestones == EXPECTED_MILESTONES
    assert classifications == EXPECTED_CLASSIFICATIONS
    assert registrations == {"decorator": 212, "registry.register": 1}
    assert len(case_ids) == 639


def test_shared_capabilities_only_reference_existing_sources_and_contracts() -> None:
    rows = _load(SUPPORT)["sharedCapabilities"]
    identifiers = {row["id"] for row in rows}

    for row in rows:
        for key in ("webRpaSources", "autoFlowReusable", "contractRefs"):
            for raw_path in row.get(key, []):
                path = REPOSITORY_ROOT / raw_path.split("#", 1)[0]
                assert path.exists(), (
                    f"{row['id']} references missing {key} path {raw_path}"
                )
        assert set(row.get("sharedCapabilityRefs", [])).issubset(identifiers)


def test_source_authorization_record_is_scoped_and_license_copy_is_exact() -> None:
    provenance = _load(PROVENANCE)
    authorization = provenance["sourceAuthorization"]

    assert authorization == {
        "status": "confirmed",
        "confirmedAt": "2026-09-15",
        "scope": "已获得在本项目范围内使用并迁入WebRPA源码的授权",
        "nonInferences": ["不推断为具体商业授权", "不推断为公开发布授权"],
        "decisionRecord": ".ai/decisions/2026-09-15-studio-webrpa-backend-source-authorization.md",
    }
    required = set(provenance["requiredFileFields"])
    migrated = provenance["migratedFiles"]
    assert migrated
    identities: set[tuple[str, str]] = set()
    for entry in migrated:
        assert required.issubset(entry)
        assert entry["sourceCommit"] == FROZEN_COMMIT
        assert (REPOSITORY_ROOT / entry["sourcePath"]).is_file()
        assert (REPOSITORY_ROOT / entry["targetPath"]).is_file()
        assert entry["licenseRecord"] == "LICENSE.WebRPA"
        identity = (entry["sourcePath"], entry["targetPath"])
        assert identity not in identities
        identities.add(identity)
    upstream = REPOSITORY_ROOT / provenance["source"]["licenseSource"]
    retained = REPOSITORY_ROOT / provenance["source"]["retainedLicenseCopy"]
    assert (
        hashlib.sha256(retained.read_bytes()).digest()
        == hashlib.sha256(upstream.read_bytes()).digest()
    )
