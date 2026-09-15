from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from autoflow.domain.workflows.scope import (
    APPROVED_NODE_TYPES,
    EXCLUDED_LEGACY_NODE_TYPES,
    validate_workflow_scope,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
CAPABILITIES = (
    REPOSITORY_ROOT / "docs/migration/studio-frontend-completion/capabilities.json"
)
EXPECTED_EXCLUDED = {
    "db_close",
    "db_connect",
    "db_delete",
    "db_execute",
    "db_insert",
    "db_query",
    "db_update",
    "dp_click",
    "dp_close",
    "dp_get_html",
    "dp_get_text",
    "dp_input",
    "dp_open_page",
    "dp_run_js",
    "dp_scroll",
    "dp_wait_element",
    "mongodb_connect",
    "mongodb_delete",
    "mongodb_disconnect",
    "mongodb_find",
    "mongodb_insert",
    "mongodb_update",
    "oracle_connect",
    "oracle_delete",
    "oracle_disconnect",
    "oracle_execute",
    "oracle_insert",
    "oracle_query",
    "oracle_update",
    "postgresql_connect",
    "postgresql_delete",
    "postgresql_disconnect",
    "postgresql_execute",
    "postgresql_insert",
    "postgresql_query",
    "postgresql_update",
    "redis_connect",
    "redis_del",
    "redis_disconnect",
    "redis_get",
    "redis_hget",
    "redis_hset",
    "redis_set",
    "sqlite_connect",
    "sqlite_delete",
    "sqlite_disconnect",
    "sqlite_execute",
    "sqlite_insert",
    "sqlite_query",
    "sqlite_update",
    "sqlserver_connect",
    "sqlserver_delete",
    "sqlserver_disconnect",
    "sqlserver_execute",
    "sqlserver_insert",
    "sqlserver_query",
    "sqlserver_update",
}


def test_runtime_scope_matches_the_227_node_authority() -> None:
    rows = json.loads(CAPABILITIES.read_text(encoding="utf-8"))

    assert APPROVED_NODE_TYPES == frozenset(row["type"] for row in rows)
    assert len(APPROVED_NODE_TYPES) == 227
    assert EXCLUDED_LEGACY_NODE_TYPES == EXPECTED_EXCLUDED
    assert len(EXCLUDED_LEGACY_NODE_TYPES) == 57
    assert APPROVED_NODE_TYPES.isdisjoint(EXCLUDED_LEGACY_NODE_TYPES)


@pytest.mark.parametrize("node_type", sorted(EXPECTED_EXCLUDED))
def test_every_excluded_legacy_type_is_rejected_without_mutating_input(
    node_type: str,
) -> None:
    nodes = [
        {
            "id": "legacy-node",
            "type": "moduleNode",
            "data": {"moduleType": node_type, "legacyConfig": {"keep": True}},
        }
    ]
    original = copy.deepcopy(nodes)

    issues = validate_workflow_scope(nodes, runnable_node_types=APPROVED_NODE_TYPES)

    assert [issue.as_dict() for issue in issues] == [
        {
            "nodeId": "legacy-node",
            "path": "nodes.0.data.moduleType",
            "code": "UNSUPPORTED_NODE_TYPE",
            "message": f"节点类型 {node_type} 不在 AutoFlow Studio 当前批准范围内",
            "nodeType": node_type,
        }
    ]
    assert nodes == original


def test_nested_custom_module_is_checked_and_preserved() -> None:
    nodes = [
        {
            "id": "call-outer",
            "type": "moduleNode",
            "data": {"moduleType": "custom_module", "customModuleId": "outer"},
        }
    ]
    modules = {
        "outer": {
            "nodes": [
                {
                    "id": "call-inner",
                    "data": {
                        "moduleType": "custom_module",
                        "customModuleId": "inner",
                    },
                }
            ]
        },
        "inner": {
            "nodes": [
                {
                    "id": "excluded",
                    "data": {"moduleType": "dp_click", "selector": "#keep"},
                }
            ]
        },
    }
    original_nodes = copy.deepcopy(nodes)
    original_modules = copy.deepcopy(modules)

    issues = validate_workflow_scope(
        nodes,
        runnable_node_types=APPROVED_NODE_TYPES,
        resolve_custom_module=lambda module_id: modules.get(module_id),
    )

    assert len(issues) == 1
    assert issues[0].as_dict() == {
        "nodeId": "excluded",
        "path": "customModules.inner.nodes.0.data.moduleType",
        "code": "UNSUPPORTED_NODE_TYPE",
        "message": "节点类型 dp_click 不在 AutoFlow Studio 当前批准范围内",
        "nodeType": "dp_click",
    }
    assert nodes == original_nodes
    assert modules == original_modules


def test_approved_but_not_yet_migrated_type_is_rejected_before_execution() -> None:
    issues = validate_workflow_scope(
        [{"id": "click", "data": {"moduleType": "click_element"}}],
        runnable_node_types={"open_page"},
    )

    assert issues[0].code == "UNSUPPORTED_NODE_TYPE"
    assert issues[0].path == "nodes.0.data.moduleType"
    assert issues[0].message == "节点类型 click_element 的真实执行器尚未迁入"
