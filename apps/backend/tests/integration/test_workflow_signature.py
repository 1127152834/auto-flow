"""Remediation M2 R2-18..22 / AC2-07/08: signature workflows, bindings, reuse and re-entrant migration."""

from copy import deepcopy

import pytest

from autoflow.application.project_automations.service import ProjectAutomationService
from autoflow.application.workflows.signature_migration import SignatureMigration
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.project_automation_models import (
    ProjectAutomationRow,
)
from autoflow.infrastructure.database.project_automations import (
    SqlAlchemyProjectAutomations,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from tests.integration.test_project_run_data_start import _input, _setup, _table, uid

SIGNATURE = {
    "inputs": [{"key": "person", "name": "人员", "fields": [{"key": "name", "name": "姓名", "type": "string", "required": True}]}],
    "outputs": [],
}


def _write_document(factory, workflow_id, *, signature=SIGNATURE, text="{input.person.name}"):
    with factory.begin() as session:
        row = session.get(WorkflowDocumentRow, workflow_id)
        document = deepcopy(row.document)
        node = document["content"]["nodes"][0]
        document["content"]["nodes"] = [{**node, "id": "use", "type": "set_variable", "data": {
            "moduleType": "set_variable", "label": "取值", "variableName": "who", "variableValue": text}}]
        document["content"]["edges"] = []
        if signature is None:
            document["content"].pop("signature", None)
        else:
            document["content"]["signature"] = signature
        row.document = document
        row.revision += 1


def _bind(item, group="person", field="name"):
    bound = deepcopy(item)
    bound["signatureInput"] = group
    if field is not None:
        bound["fieldBindings"][0]["signatureField"] = field
    return bound


def _service(factory):
    return ProjectAutomationService(SqlAlchemyProjects(factory), SqlAlchemyProjectAutomations(factory))


def _update_plan(factory, project_id, automation, inputs):
    view = _service(factory).update(project_id, automation.automation_id, uid(), {
        "name": automation.name, "description": "", "workflowId": automation.workflow_id,
        "inputPlan": {"inputs": inputs, "processingInputId": inputs[0]["inputId"]},
        "parameterSchema": [], "environmentPolicy": automation.environment_policy, "runPolicy": automation.run_policy,
        "expectedManagementRevision": automation.management_revision,
    })[0]
    return view


def _start(coordinator, project_id, automation):
    return coordinator.start(project_id, automation.automation_id, uid(), {
        "expectedAutomationRevision": automation.management_revision, "parameters": {}, "maxTasks": 1, "concurrency": 1,
    })


@pytest.fixture
def world(tmp_path):
    factory, project_id, automation, coordinator = _setup(tmp_path)
    yield factory, project_id, automation, coordinator
    factory.dispose()


def test_a_bound_signature_workflow_starts_and_missing_bindings_name_the_field(world):
    factory, project_id, automation, coordinator = world
    _write_document(factory, automation.workflow_id)
    people, emails = automation.input_plan["inputs"]
    unbound = _update_plan(factory, project_id, automation, [_bind(people, field=None), emails])
    with pytest.raises(ProjectRunError) as missing:
        _start(coordinator, project_id, unbound)
    assert (missing.value.code, missing.value.message) == ("PROJECT_SIGNATURE_UNBOUND", "流程输入「人员」缺少字段「姓名」的绑定")
    bound = _update_plan(factory, project_id, unbound, [_bind(people), emails])
    assert _start(coordinator, project_id, bound)[0].batch_id


def test_renaming_display_names_keeps_references_and_unknown_keys_are_rejected(world):
    factory, project_id, automation, coordinator = world
    renamed = {"inputs": [{**SIGNATURE["inputs"][0], "name": "办理人", "fields": [{**SIGNATURE["inputs"][0]["fields"][0], "name": "全名"}]}], "outputs": []}
    _write_document(factory, automation.workflow_id, signature=renamed)
    people, emails = automation.input_plan["inputs"]
    bound = _update_plan(factory, project_id, automation, [_bind(people), emails])
    assert _start(coordinator, project_id, bound)[0].batch_id
    _write_document(factory, automation.workflow_id, signature=renamed, text="{input.person.age}")
    with pytest.raises(ProjectRunError) as unknown:
        _start(coordinator, project_id, bound)
    assert unknown.value.code == "PROJECT_INPUT_REFERENCE_INVALID"
    assert unknown.value.message == "流程输入「办理人」没有字段「age」"


def test_two_automations_reuse_one_signature_workflow_with_different_tables(world):
    factory, project_id, automation, coordinator = world
    _write_document(factory, automation.workflow_id)
    people, emails = automation.input_plan["inputs"]
    first = _update_plan(factory, project_id, automation, [_bind(people), emails])
    staff, staff_field = _table(factory, project_id, "员工", "李四")
    second = _service(factory).create(project_id, uid(), {
        "name": "复用同一流程", "description": "", "workflowId": automation.workflow_id,
        "inputPlan": {"inputs": [_bind(_input(project_id, staff, staff_field, "员工"))]},
        "parameterSchema": [], "environmentPolicy": {"source": "newFromProfile"}, "runPolicy": automation.run_policy,
    })[0]
    assert second.workflow_id == first.workflow_id
    assert _start(coordinator, project_id, first)[0].batch_id
    assert _start(coordinator, project_id, second)[0].batch_id


def test_a_signature_field_type_must_match_the_bound_data_field(world):
    factory, project_id, automation, coordinator = world
    numeric = {"inputs": [{**SIGNATURE["inputs"][0], "fields": [{**SIGNATURE["inputs"][0]["fields"][0], "type": "number"}]}], "outputs": []}
    _write_document(factory, automation.workflow_id, signature=numeric)
    people, emails = automation.input_plan["inputs"]
    bound = _update_plan(factory, project_id, automation, [_bind(people), emails])
    with pytest.raises(ProjectRunError) as mismatch:
        _start(coordinator, project_id, bound)
    assert mismatch.value.message == "流程输入「人员」的字段「姓名」需要数字，绑定的数据字段是文本"


def test_migration_rewrites_value_references_reports_the_rest_and_is_reentrant(world):
    factory, project_id, automation, coordinator = world
    people, _emails = automation.input_plan["inputs"]
    value_ref = f"{{PROJECT_INPUTS['{people['inputId']}']['values']['{people['fieldBindings'][0]['inputFieldId']}']}}"
    record_ref = f"{{PROJECT_INPUTS['{people['inputId']}']['recordRef']}}"
    _write_document(factory, automation.workflow_id, signature=None, text=f"{value_ref} / {record_ref}")
    migration = SignatureMigration(factory)
    [before] = migration.report()
    assert (before["status"], before["legacyReferences"], before["remaining"]) == ("partial", 2, 1)
    with factory() as session:
        untouched = session.get(WorkflowDocumentRow, automation.workflow_id).revision
    [after] = migration.apply()
    assert after["status"] == "migrated" and after["remaining"] == 1
    with factory() as session:
        row = session.get(WorkflowDocumentRow, automation.workflow_id)
        node = row.document["content"]["nodes"][0]
        assert node["data"]["variableValue"] == f"{{input.人员.值}} / {record_ref}"
        assert [item["key"] for item in row.document["content"]["signature"]["inputs"]] == ["人员", "邮箱"]
        assert row.revision == untouched + 1
        stored = session.get(ProjectAutomationRow, automation.automation_id)
        assert [item["signatureInput"] for item in stored.input_plan["inputs"]] == ["人员", "邮箱"]
        assert stored.input_plan["inputs"][0]["fieldBindings"][0]["signatureField"] == "值"
    assert migration.apply() == [after]  # nothing left to change
    with factory() as session:
        assert session.get(WorkflowDocumentRow, automation.workflow_id).revision == untouched + 1
        current = session.get(ProjectAutomationRow, automation.automation_id)
    migrated = _service(factory).get(project_id, current.id)
    assert _start(coordinator, project_id, migrated)[0].batch_id  # old record reference still runs


def test_shared_workflows_with_old_references_are_reported_not_rewritten(world):
    factory, project_id, automation, _coordinator = world
    people, _emails = automation.input_plan["inputs"]
    _write_document(factory, automation.workflow_id, signature=None,
                    text=f"{{PROJECT_INPUTS['{people['inputId']}']['values']['{people['fieldBindings'][0]['inputFieldId']}']}}")
    staff, staff_field = _table(factory, project_id, "员工", "李四")
    _service(factory).create(project_id, uid(), {
        "name": "第二个", "description": "", "workflowId": automation.workflow_id,
        "inputPlan": {"inputs": [_input(project_id, staff, staff_field, "员工")]},
        "parameterSchema": [], "environmentPolicy": {"source": "newFromProfile"}, "runPolicy": automation.run_policy,
    })
    [item] = SignatureMigration(factory).apply()
    assert item["status"] == "ambiguous"
    with factory() as session:
        assert "signature" not in session.get(WorkflowDocumentRow, automation.workflow_id).document["content"]


def test_migration_also_handles_documents_saved_by_the_studio(world):
    """The Studio stores the graph at the top level instead of under "content"."""
    factory, project_id, automation, coordinator = world
    people, _emails = automation.input_plan["inputs"]
    value_ref = f"{{PROJECT_INPUTS['{people['inputId']}']['values']['{people['fieldBindings'][0]['inputFieldId']}']}}"
    _write_document(factory, automation.workflow_id, signature=None, text=value_ref)
    with factory.begin() as session:
        row = session.get(WorkflowDocumentRow, automation.workflow_id)
        content = deepcopy(row.document["content"])
        content.pop("schemaVersion", None)
        row.document = content
    [item] = SignatureMigration(factory).apply()
    assert (item["status"], item.get("remaining")) == ("migrated", None)
    with factory() as session:
        stored = session.get(WorkflowDocumentRow, automation.workflow_id).document
    assert "content" not in stored and stored["nodes"][0]["data"]["variableValue"] == "{input.人员.值}"
    assert stored["signature"]["inputs"][0]["key"] == "人员"
    migrated = _service(factory).get(project_id, automation.automation_id)
    assert _start(coordinator, project_id, migrated)[0].batch_id
    people_bound, emails_bound = migrated.input_plan["inputs"]
    people_unbound = deepcopy(people_bound)
    people_unbound["fieldBindings"][0].pop("signatureField")
    broken = _update_plan(factory, project_id, migrated, [people_unbound, emails_bound])
    with pytest.raises(ProjectRunError) as missing:
        _start(coordinator, project_id, broken)
    assert missing.value.code == "PROJECT_SIGNATURE_UNBOUND"


def test_saving_from_an_editor_without_signatures_keeps_it_and_null_removes_it(tmp_path):
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.infrastructure.database.session import (
        create_session_factory,
        migrate_database,
    )
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments

    path = tmp_path / "docs.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    service = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory))
    payload = {"name": "签名流程", "nodes": [], "edges": [], "variables": [], "signature": SIGNATURE}
    saved = service.create(payload, client_request_id=uid())
    old_editor = {key: value for key, value in payload.items() if key != "signature"}
    kept = service.update(saved.id, old_editor, expected_revision=1, client_request_id=uid())
    assert service.get(kept.id).document["signature"] == SIGNATURE
    service.update(saved.id, {**old_editor, "signature": None}, expected_revision=2, client_request_id=uid())
    assert "signature" not in service.get(saved.id).document
    factory.dispose()
