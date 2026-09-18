from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from autoflow.application.workflows.modules import CustomModuleService
from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.modules import CustomModuleDraft, SavedCustomModule
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflow_modules import SqlAlchemyWorkflowModules


def _node(node_id: str = "value") -> dict[str, object]:
    return {
        "id": node_id,
        "type": "set_variable",
        "position": {"x": 10, "y": 20},
        "data": {"moduleType": "set_variable", "variableName": "result"},
    }


def _dependency_node(node_id: str, module_id: str) -> dict[str, object]:
    return {
        "id": node_id,
        "type": "custom_module",
        "position": {"x": 30, "y": 40},
        "data": {"moduleType": "custom_module", "customModuleId": module_id},
    }


def _payload(
    name: str,
    *,
    category: str = "custom",
    display_name: str | None = None,
    description: str = "",
    tags: list[str] | None = None,
    dependencies: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "name": name,
        "display_name": display_name or name,
        "description": description,
        "icon": "📦",
        "color": "#8B5CF6",
        "category": category,
        "parameters": [],
        "outputs": [],
        "workflow": {
            "nodes": [
                _node(),
                *(
                    _dependency_node(f"dependency-{index}", dependency)
                    for index, dependency in enumerate(dependencies)
                ),
            ],
            "edges": [],
            "variables": [],
        },
        "tags": tags or [],
    }


def _generated_id(name: str, client_request_id: str) -> str:
    suffix = uuid5(NAMESPACE_URL, f"autoflow-custom-module:{client_request_id}").hex[:8]
    return CustomModuleDraft.generated_id(name, suffix)


@pytest.fixture
def module_service(tmp_path: Path) -> CustomModuleService:
    database = tmp_path / "workflow-modules.sqlite3"
    migrate_database(database)
    repository = SqlAlchemyWorkflowModules(create_session_factory(database))
    ticks = count()
    return CustomModuleService(
        repository,
        clock=lambda: (
            datetime(2026, 9, 16, tzinfo=UTC) + timedelta(minutes=next(ticks))
        ),
    )


def test_crud_roundtrip_preserves_partial_update_and_usage(
    module_service: CustomModuleService,
) -> None:
    created = module_service.create(
        _payload("normalize_html", display_name="整理 HTML", tags=["网页"]),
        client_request_id="create-normalizer",
    )
    assert isinstance(created, SavedCustomModule)
    assert created.revision == 1
    assert created.usage_count == 0
    assert module_service.get(created.id) == created

    updated = module_service.update(
        created.id,
        {"description": "删除多余空白"},
        expected_revision=1,
        client_request_id="update-normalizer",
    )
    assert updated.revision == 2
    assert updated.name == "normalize_html"
    assert updated.definition["display_name"] == "整理 HTML"
    assert updated.definition["description"] == "删除多余空白"

    used = module_service.increment_usage(created.id)
    assert used.revision == 2
    assert used.usage_count == 1

    module_service.delete(
        created.id,
        expected_revision=2,
        client_request_id="delete-normalizer",
    )
    with pytest.raises(WorkflowDocumentError) as missing:
        module_service.get(created.id)
    assert missing.value.code == "CUSTOM_MODULE_NOT_FOUND"


def test_names_are_unique_after_trimming(
    module_service: CustomModuleService,
) -> None:
    first = module_service.create(
        _payload("Normalize_HTML"), client_request_id="create-first"
    )

    with pytest.raises(WorkflowDocumentError) as duplicate:
        module_service.create(
            _payload(" Normalize_HTML "), client_request_id="create-duplicate"
        )
    assert duplicate.value.code == "CUSTOM_MODULE_NAME_CONFLICT"

    second = module_service.create(
        _payload("extract_title"), client_request_id="create-second"
    )
    with pytest.raises(WorkflowDocumentError) as renamed:
        module_service.update(
            second.id,
            {"name": first.name},
            expected_revision=1,
            client_request_id="rename-second",
        )
    assert renamed.value.code == "CUSTOM_MODULE_NAME_CONFLICT"


def test_revision_conflicts_do_not_change_or_delete_the_current_module(
    module_service: CustomModuleService,
) -> None:
    created = module_service.create(
        _payload("revisioned"), client_request_id="create-revisioned"
    )

    with pytest.raises(WorkflowDocumentError) as update_conflict:
        module_service.update(
            created.id,
            {"description": "stale"},
            expected_revision=9,
            client_request_id="stale-update",
        )
    assert update_conflict.value.code == "CUSTOM_MODULE_REVISION_CONFLICT"
    assert update_conflict.value.details == {
        "expectedRevision": 9,
        "currentRevision": 1,
    }

    with pytest.raises(WorkflowDocumentError) as delete_conflict:
        module_service.delete(
            created.id,
            expected_revision=9,
            client_request_id="stale-delete",
        )
    assert delete_conflict.value.code == "CUSTOM_MODULE_REVISION_CONFLICT"
    assert module_service.get(created.id).revision == 1


def test_write_request_ids_are_idempotent_and_reject_conflicting_reuse(
    module_service: CustomModuleService,
) -> None:
    payload = _payload("idempotent")
    first = module_service.create(payload, client_request_id="stable-create")
    assert module_service.create(payload, client_request_id="stable-create") == first

    with pytest.raises(WorkflowDocumentError) as create_reuse:
        module_service.create(_payload("different"), client_request_id="stable-create")
    assert create_reuse.value.code == "IDEMPOTENCY_CONFLICT"

    updated = module_service.update(
        first.id,
        {"description": "updated"},
        expected_revision=1,
        client_request_id="stable-update",
    )
    assert (
        module_service.update(
            first.id,
            {"description": "updated"},
            expected_revision=1,
            client_request_id="stable-update",
        )
        == updated
    )

    with pytest.raises(WorkflowDocumentError) as update_reuse:
        module_service.update(
            first.id,
            {"description": "different"},
            expected_revision=1,
            client_request_id="stable-update",
        )
    assert update_reuse.value.code == "IDEMPOTENCY_CONFLICT"

    module_service.delete(
        first.id,
        expected_revision=2,
        client_request_id="stable-delete",
    )
    module_service.delete(
        first.id,
        expected_revision=2,
        client_request_id="stable-delete",
    )


def test_direct_missing_and_self_dependencies_are_rejected(
    module_service: CustomModuleService,
) -> None:
    with pytest.raises(WorkflowDocumentError) as missing:
        module_service.create(
            _payload("missing", dependencies=("not-installed",)),
            client_request_id="create-missing",
        )
    assert missing.value.code == "CUSTOM_MODULE_DEPENDENCY_MISSING"
    assert missing.value.details["dependencyId"] == "not-installed"

    request_id = "create-self"
    self_id = _generated_id("self", request_id)
    with pytest.raises(WorkflowDocumentError) as self_reference:
        module_service.create(
            _payload("self", dependencies=(self_id,)),
            client_request_id=request_id,
        )
    assert self_reference.value.code == "CUSTOM_MODULE_CYCLE"


def test_indirect_a_b_a_cycle_is_rejected_without_changing_a(
    module_service: CustomModuleService,
) -> None:
    module_a = module_service.create(_payload("module_a"), client_request_id="create-a")
    module_b = module_service.create(
        _payload("module_b", dependencies=(module_a.id,)),
        client_request_id="create-b",
    )

    with pytest.raises(WorkflowDocumentError) as cycle:
        module_service.update(
            module_a.id,
            {"workflow": _payload("ignored", dependencies=(module_b.id,))["workflow"]},
            expected_revision=1,
            client_request_id="make-cycle",
        )
    assert cycle.value.code == "CUSTOM_MODULE_CYCLE"
    assert module_service.get(module_a.id).dependencies == ()


def test_list_filters_searches_and_sorts_by_latest_update(
    module_service: CustomModuleService,
) -> None:
    oldest = module_service.create(
        _payload(
            "html_cleaner",
            category="web",
            display_name="清理页面",
            tags=["sanitize"],
        ),
        client_request_id="create-oldest",
    )
    module_service.create(
        _payload("csv_cleaner", category="data", description="Sanitize rows"),
        client_request_id="create-middle",
    )
    newest = module_service.create(
        _payload("html_extract", category="web", display_name="抽取 HTML"),
        client_request_id="create-newest",
    )

    assert [item.id for item in module_service.list(category="web")] == [
        newest.id,
        oldest.id,
    ]
    assert [item.name for item in module_service.list(search="SANITIZE")] == [
        "csv_cleaner",
        "html_cleaner",
    ]

    refreshed = module_service.update(
        oldest.id,
        {"description": "latest"},
        expected_revision=1,
        client_request_id="refresh-oldest",
    )
    assert [item.id for item in module_service.list(category="web")] == [
        refreshed.id,
        newest.id,
    ]
