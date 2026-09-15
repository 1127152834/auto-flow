from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import func, select

from autoflow.application.project_data.capabilities import ProjectDataCapabilityService
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_data import capabilities as capability_domain
from autoflow.domain.project_data.capabilities import (
    CreateProjectRecordCommand,
    DeleteProjectRecordCommand,
    SetRecordStatusCommand,
    TaskCapabilityScope,
    UpdateProjectRecordCommand,
)
from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_capabilities import (
    SqlAlchemyProjectDataCapabilities,
)
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.workflow_runtime_models import WorkflowRunRow
from tests.integration.test_project_run_data_start import _setup, uid

PROJECT_ID = "11111111-1111-4111-8111-111111111111"
TASK_ID = "22222222-2222-4222-8222-222222222222"
RUN_ID = "33333333-3333-4333-8333-333333333333"
PEOPLE_TABLE_ID = "44444444-4444-4444-8444-444444444444"
EMAIL_TABLE_ID = "55555555-5555-4555-8555-555555555555"
ACCOUNT_TABLE_ID = "66666666-6666-4666-8666-666666666666"
PEOPLE_GENERATION = "77777777-7777-4777-8777-777777777777"
EMAIL_GENERATION = "88888888-8888-4888-8888-888888888888"
ACCOUNT_GENERATION = "99999999-9999-4999-8999-999999999999"
STATUS_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SET_OPERATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CREATE_OPERATION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
UPDATE_OPERATION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
DELETE_OPERATION_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
FIELD_OPERATION_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"
EMAIL_FIELD_ID = "12121212-1212-4121-8121-121212121212"
RESULT_FIELD_ID = "13131313-1313-4131-8131-131313131313"


def _record(
    table_id: str = EMAIL_TABLE_ID,
    generation: str = EMAIL_GENERATION,
    key: RecordKey | None = None,
) -> RecordRef:
    return RecordRef(PROJECT_ID, table_id, generation, key or RecordKey("text", "001"))


def _scope() -> TaskCapabilityScope:
    return TaskCapabilityScope(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        run_id=RUN_ID,
        execution_generation=3,
        status_record_refs=frozenset({_record()}),
        create_record_targets=frozenset({(ACCOUNT_TABLE_ID, ACCOUNT_GENERATION)}),
    )


def test_set_status_command_has_stable_canonical_payload_and_identity() -> None:
    command = SetRecordStatusCommand(
        operation_id=SET_OPERATION_ID,
        execution_generation=3,
        record_ref=_record(),
        status_id=STATUS_ID,
        expected_status_revision=2,
    )

    assert command.request_payload == {
        "kind": "setRecordStatus",
        "executionGeneration": 3,
        "recordRef": {
            "projectId": PROJECT_ID,
            "tableId": EMAIL_TABLE_ID,
            "datasetGeneration": EMAIL_GENERATION,
            "recordKey": {"type": "text", "value": "001"},
        },
        "statusId": STATUS_ID,
        "expectedStatusRevision": 2,
    }
    canonical = (
        '{"executionGeneration":3,"expectedStatusRevision":2,'
        '"kind":"setRecordStatus","recordRef":{'
        '"datasetGeneration":"88888888-8888-4888-8888-888888888888",'
        '"projectId":"11111111-1111-4111-8111-111111111111",'
        '"recordKey":{"type":"text","value":"001"},'
        '"tableId":"55555555-5555-4555-8555-555555555555"},'
        '"statusId":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}'
    )
    expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert command.request_digest == expected_digest
    assert command.idempotency_identity == (SET_OPERATION_ID, expected_digest)


def test_set_status_command_preserves_derived_content_fence_and_explicit_null_from() -> (
    None
):
    command = SetRecordStatusCommand(
        SET_OPERATION_ID,
        3,
        _record(),
        STATUS_ID,
        2,
        expected_content_revision_when_derived=5,
        allowed_from=(None,),
    )

    assert command.request_payload["expectedContentRevisionWhenDerived"] == 5
    assert command.request_payload["allowedFrom"] == [None]

    unconstrained = SetRecordStatusCommand(SET_OPERATION_ID, 3, _record(), STATUS_ID, 2)
    assert "expectedContentRevisionWhenDerived" not in unconstrained.request_payload
    assert "allowedFrom" not in unconstrained.request_payload


def test_create_command_copies_values_and_normalizes_mapping_order() -> None:
    mutable = {"email": "one@example.test", "active": True}
    command = CreateProjectRecordCommand(
        operation_id=CREATE_OPERATION_ID,
        execution_generation=3,
        project_id=PROJECT_ID,
        table_id=ACCOUNT_TABLE_ID,
        dataset_generation=ACCOUNT_GENERATION,
        values=mutable,
    )
    same_payload = CreateProjectRecordCommand(
        operation_id=CREATE_OPERATION_ID,
        execution_generation=3,
        project_id=PROJECT_ID,
        table_id=ACCOUNT_TABLE_ID,
        dataset_generation=ACCOUNT_GENERATION,
        values={"active": True, "email": "one@example.test"},
    )

    mutable["email"] = "changed@example.test"

    assert command.request_payload == {
        "kind": "createRecord",
        "executionGeneration": 3,
        "projectId": PROJECT_ID,
        "tableId": ACCOUNT_TABLE_ID,
        "datasetGeneration": ACCOUNT_GENERATION,
        "values": {"email": "one@example.test", "active": True},
    }
    assert command.idempotency_identity == same_payload.idempotency_identity


def test_scope_authorizes_only_declared_status_record_and_create_target() -> None:
    scope = _scope()
    set_status = SetRecordStatusCommand(SET_OPERATION_ID, 3, _record(), STATUS_ID, 2)
    create = CreateProjectRecordCommand(
        CREATE_OPERATION_ID,
        3,
        PROJECT_ID,
        ACCOUNT_TABLE_ID,
        ACCOUNT_GENERATION,
        {"email": "one@example.test"},
    )

    scope.authorize_set_status(set_status, current_execution_generation=3)
    scope.authorize_create_record(create, current_execution_generation=3)


def test_create_target_does_not_grant_record_update_delete_or_status() -> None:
    scope = _scope()
    created_ref = _record(ACCOUNT_TABLE_ID, ACCOUNT_GENERATION)
    commands = (
        UpdateProjectRecordCommand(
            UPDATE_OPERATION_ID, 3, created_ref, {RESULT_FIELD_ID: "changed"}, 1
        ),
        DeleteProjectRecordCommand(
            DELETE_OPERATION_ID, 3, created_ref, 1, 1, 1
        ),
        SetRecordStatusCommand(SET_OPERATION_ID, 3, created_ref, STATUS_ID, 1),
    )

    for command in commands:
        with pytest.raises(ProjectError) as caught:
            if isinstance(command, UpdateProjectRecordCommand):
                scope.authorize_update_record(command, current_execution_generation=3)
            elif isinstance(command, DeleteProjectRecordCommand):
                scope.authorize_delete_record(command, current_execution_generation=3)
            else:
                scope.authorize_set_status(command, current_execution_generation=3)
        assert caught.value.code == "CAPABILITY_SCOPE_DENIED"


def test_typed_record_identity_cannot_cross_scope() -> None:
    scope = _scope()
    integer_identity = SetRecordStatusCommand(
        SET_OPERATION_ID,
        3,
        _record(key=RecordKey("integer", "1")),
        STATUS_ID,
        2,
    )

    with pytest.raises(ProjectError) as caught:
        scope.authorize_set_status(integer_identity, current_execution_generation=3)

    assert caught.value.code == "CAPABILITY_SCOPE_DENIED"


@pytest.mark.parametrize(
    "command",
    [
        lambda: SetRecordStatusCommand(
            SET_OPERATION_ID, 3, _record(key=RecordKey("integer", "01")), STATUS_ID, 2
        ),
        lambda: SetRecordStatusCommand(SET_OPERATION_ID, 3, _record(), STATUS_ID, True),
        lambda: SetRecordStatusCommand(
            SET_OPERATION_ID.upper(), 3, _record(), STATUS_ID, 2
        ),
        lambda: SetRecordStatusCommand(SET_OPERATION_ID, 0, _record(), STATUS_ID, 2),
        lambda: CreateProjectRecordCommand(
            CREATE_OPERATION_ID,
            3,
            PROJECT_ID,
            ACCOUNT_TABLE_ID,
            ACCOUNT_GENERATION,
            {"invalid": float("nan")},
        ),
    ],
)
def test_commands_reject_noncanonical_identity_revision_or_payload(command) -> None:
    with pytest.raises(ProjectError) as caught:
        command()

    assert caught.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("command_generation,current_generation", [(2, 3), (3, 4)])
def test_stale_execution_generation_is_revoked(
    command_generation: int, current_generation: int
) -> None:
    scope = _scope()
    command = SetRecordStatusCommand(
        SET_OPERATION_ID, command_generation, _record(), STATUS_ID, 2
    )

    with pytest.raises(ProjectError) as caught:
        scope.authorize_set_status(
            command, current_execution_generation=current_generation
        )

    assert caught.value.code == "LEASE_REVOKED"


def test_cross_project_or_undeclared_target_is_denied() -> None:
    scope = _scope()
    other_project = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    wrong_record = SetRecordStatusCommand(
        SET_OPERATION_ID,
        3,
        RecordRef(
            other_project,
            EMAIL_TABLE_ID,
            EMAIL_GENERATION,
            RecordKey("text", "001"),
        ),
        STATUS_ID,
        2,
    )
    wrong_target = CreateProjectRecordCommand(
        CREATE_OPERATION_ID,
        3,
        PROJECT_ID,
        PEOPLE_TABLE_ID,
        PEOPLE_GENERATION,
        {"name": "Ada"},
    )

    with pytest.raises(ProjectError) as record_error:
        scope.authorize_set_status(wrong_record, current_execution_generation=3)
    with pytest.raises(ProjectError) as table_error:
        scope.authorize_create_record(wrong_target, current_execution_generation=3)

    assert record_error.value.code == "CAPABILITY_SCOPE_DENIED"
    assert table_error.value.code == "CAPABILITY_SCOPE_DENIED"


def test_scope_rejects_invalid_members_before_authorization() -> None:
    with pytest.raises(ProjectError) as caught:
        TaskCapabilityScope(
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            run_id=RUN_ID,
            execution_generation=3,
            status_record_refs=frozenset(
                {
                    RecordRef(
                        "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                        EMAIL_TABLE_ID,
                        EMAIL_GENERATION,
                        RecordKey("text", "001"),
                    )
                }
            ),
            create_record_targets=frozenset({(ACCOUNT_TABLE_ID, ACCOUNT_GENERATION)}),
        )

    assert caught.value.code == "VALIDATION_ERROR"


def test_read_request_is_immutable_and_exact_record_scope_checks_fields_and_purpose() -> (
    None
):
    request_type = capability_domain.ReadProjectRecordRequest
    grant_type = capability_domain.RecordReadGrant
    fields = [EMAIL_FIELD_ID]
    request = request_type(3, _record(), fields, "lookup-account")
    scope = TaskCapabilityScope(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        run_id=RUN_ID,
        execution_generation=3,
        status_record_refs=frozenset(),
        create_record_targets=frozenset(),
        record_read_grants=frozenset(
            {grant_type(_record(), frozenset(fields), frozenset({"lookup-account"}))}
        ),
    )

    fields.append(RESULT_FIELD_ID)

    assert request.request_payload == {
        "kind": "readProjectRecord",
        "executionGeneration": 3,
        "recordRef": {
            "projectId": PROJECT_ID,
            "tableId": EMAIL_TABLE_ID,
            "datasetGeneration": EMAIL_GENERATION,
            "recordKey": {"type": "text", "value": "001"},
        },
        "fieldIds": [EMAIL_FIELD_ID],
        "readPurpose": "lookup-account",
    }
    scope.authorize_read_record(request, current_execution_generation=3)

    forbidden_field = request_type(3, _record(), [RESULT_FIELD_ID], "lookup-account")
    forbidden_purpose = request_type(3, _record(), [EMAIL_FIELD_ID], "export")
    with pytest.raises(ProjectError, match="does not allow"):
        scope.authorize_read_record(forbidden_field, current_execution_generation=3)
    with pytest.raises(ProjectError, match="does not allow"):
        scope.authorize_read_record(forbidden_purpose, current_execution_generation=3)


def test_query_request_has_stable_payload_and_table_scope_is_generation_bound() -> None:
    request_type = capability_domain.QueryProjectRecordsRequest
    grant_type = capability_domain.TableCapabilityGrant
    raw_filter = {
        "type": "compare",
        "fieldId": EMAIL_FIELD_ID,
        "operator": "contains",
        "value": "@example.test",
    }
    request = request_type(
        execution_generation=3,
        project_id=PROJECT_ID,
        table_id=EMAIL_TABLE_ID,
        dataset_generation=EMAIL_GENERATION,
        field_ids=[EMAIL_FIELD_ID],
        read_purpose="lookup-account",
        filter=raw_filter,
        order_by=[{"fieldId": EMAIL_FIELD_ID, "direction": "asc"}],
        cursor=None,
        limit=50,
    )
    same = request_type(
        3,
        PROJECT_ID,
        EMAIL_TABLE_ID,
        EMAIL_GENERATION,
        [EMAIL_FIELD_ID],
        "lookup-account",
        {
            "operator": "contains",
            "value": "@example.test",
            "fieldId": EMAIL_FIELD_ID,
            "type": "compare",
        },
        [{"direction": "asc", "fieldId": EMAIL_FIELD_ID}],
        None,
        50,
    )
    scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                grant_type(
                    EMAIL_TABLE_ID,
                    EMAIL_GENERATION,
                    frozenset({"queryRecords"}),
                    frozenset({EMAIL_FIELD_ID}),
                    frozenset({"lookup-account"}),
                )
            }
        ),
    )

    raw_filter["value"] = "changed"

    assert request.request_payload["filter"]["value"] == "@example.test"
    assert request.request_digest == same.request_digest
    scope.authorize_query_records(request, current_execution_generation=3)

    stale = request_type(
        3,
        PROJECT_ID,
        EMAIL_TABLE_ID,
        PEOPLE_GENERATION,
        [EMAIL_FIELD_ID],
        "lookup-account",
        None,
        [],
        None,
        50,
    )
    with pytest.raises(ProjectError) as caught:
        scope.authorize_query_records(stale, current_execution_generation=3)
    assert caught.value.code == "CAPABILITY_SCOPE_DENIED"


def test_table_read_grant_allows_exact_read_without_granting_a_write() -> None:
    request = capability_domain.ReadProjectRecordRequest(
        execution_generation=3,
        record_ref=_record(),
        field_ids=[EMAIL_FIELD_ID],
        read_purpose="lookup-account",
    )
    scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                capability_domain.TableCapabilityGrant(
                    EMAIL_TABLE_ID,
                    EMAIL_GENERATION,
                    frozenset({"readRecord"}),
                    frozenset({EMAIL_FIELD_ID}),
                    frozenset({"lookup-account"}),
                )
            }
        ),
    )

    scope.authorize_read_record(request, current_execution_generation=3)
    with pytest.raises(ProjectError) as caught:
        scope.authorize_update_record(
            capability_domain.UpdateProjectRecordCommand(
                UPDATE_OPERATION_ID,
                3,
                _record(),
                {EMAIL_FIELD_ID: "changed@example.test"},
                5,
            ),
            current_execution_generation=3,
        )
    assert caught.value.code == "CAPABILITY_SCOPE_DENIED"


def test_update_command_digest_and_scope_distinguish_existing_and_dynamic_lease() -> (
    None
):
    command_type = capability_domain.UpdateProjectRecordCommand
    record_grant_type = capability_domain.RecordWriteGrant
    table_grant_type = capability_domain.TableCapabilityGrant
    values = {EMAIL_FIELD_ID: "used@example.test"}
    command = command_type(UPDATE_OPERATION_ID, 3, _record(), values, 5)
    same = command_type(
        UPDATE_OPERATION_ID, 3, _record(), {EMAIL_FIELD_ID: "used@example.test"}, 5
    )
    exact_scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        record_write_grants=frozenset(
            {
                record_grant_type(
                    _record(),
                    frozenset({"updateRecord"}),
                    frozenset({EMAIL_FIELD_ID}),
                )
            }
        ),
    )
    dynamic_scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                table_grant_type(
                    EMAIL_TABLE_ID,
                    EMAIL_GENERATION,
                    frozenset({"updateRecord"}),
                    frozenset({EMAIL_FIELD_ID}),
                )
            }
        ),
    )

    values[EMAIL_FIELD_ID] = "mutated@example.test"

    assert command.request_payload["changes"] == {EMAIL_FIELD_ID: "used@example.test"}
    assert command.idempotency_identity == same.idempotency_identity
    assert (
        exact_scope.authorize_update_record(command, current_execution_generation=3)
        == "existing"
    )
    assert (
        dynamic_scope.authorize_update_record(command, current_execution_generation=3)
        == "dynamic"
    )

    forbidden = command_type(
        UPDATE_OPERATION_ID, 3, _record(), {RESULT_FIELD_ID: "x"}, 5
    )
    with pytest.raises(ProjectError) as caught:
        dynamic_scope.authorize_update_record(forbidden, current_execution_generation=3)
    assert caught.value.code == "CAPABILITY_SCOPE_DENIED"


def test_delete_command_requires_all_record_revisions_and_explicit_permission() -> None:
    command_type = capability_domain.DeleteProjectRecordCommand
    grant_type = capability_domain.RecordWriteGrant
    command = command_type(DELETE_OPERATION_ID, 3, _record(), 5, 4, 2)
    scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        record_write_grants=frozenset(
            {grant_type(_record(), frozenset({"deleteRecord"}), frozenset())}
        ),
    )

    assert command.request_payload == {
        "kind": "deleteRecord",
        "executionGeneration": 3,
        "recordRef": {
            "projectId": PROJECT_ID,
            "tableId": EMAIL_TABLE_ID,
            "datasetGeneration": EMAIL_GENERATION,
            "recordKey": {"type": "text", "value": "001"},
        },
        "expectedContentRevision": 5,
        "expectedStatusRevision": 4,
        "expectedLinkRevision": 2,
    }
    assert (
        scope.authorize_delete_record(command, current_execution_generation=3)
        == "existing"
    )

    with pytest.raises(ProjectError):
        capability_domain.DeleteProjectRecordCommand(
            DELETE_OPERATION_ID, 3, _record(), 5, 4, True
        )


def test_status_clear_can_use_declared_dynamic_table_target() -> None:
    grant_type = capability_domain.TableCapabilityGrant
    scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                grant_type(
                    EMAIL_TABLE_ID,
                    EMAIL_GENERATION,
                    frozenset({"setRecordStatus"}),
                )
            }
        ),
    )
    clear = SetRecordStatusCommand(SET_OPERATION_ID, 3, _record(), None, 2)

    assert (
        scope.authorize_set_status(clear, current_execution_generation=3) == "dynamic"
    )


def test_field_commands_freeze_definition_and_are_authorized_per_action() -> None:
    add_type = capability_domain.AddProjectFieldCommand
    ensure_type = capability_domain.EnsureProjectFieldCommand
    modify_type = capability_domain.ModifyProjectFieldCommand
    grant_type = capability_domain.TableCapabilityGrant
    definition = {
        "key": "result",
        "name": "运行结果",
        "type": "string",
        "required": False,
        "validation": {"maxLength": 200},
    }
    add = add_type(
        FIELD_OPERATION_ID,
        3,
        PROJECT_ID,
        ACCOUNT_TABLE_ID,
        ACCOUNT_GENERATION,
        RESULT_FIELD_ID,
        definition,
        False,
        None,
        2,
    )
    ensure = ensure_type(
        FIELD_OPERATION_ID,
        3,
        PROJECT_ID,
        ACCOUNT_TABLE_ID,
        ACCOUNT_GENERATION,
        RESULT_FIELD_ID,
        definition,
        False,
        None,
        2,
    )
    modify = modify_type(
        FIELD_OPERATION_ID,
        3,
        PROJECT_ID,
        ACCOUNT_TABLE_ID,
        ACCOUNT_GENERATION,
        RESULT_FIELD_ID,
        definition,
        2,
        1,
        7,
    )
    scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                grant_type(
                    ACCOUNT_TABLE_ID,
                    ACCOUNT_GENERATION,
                    frozenset({"addField", "ensureField", "modifyField"}),
                    frozenset({RESULT_FIELD_ID}),
                )
            }
        ),
    )

    definition["name"] = "已改变"

    assert add.request_payload["definition"]["name"] == "运行结果"
    assert ensure.request_payload["kind"] == "ensureField"
    assert modify.request_payload["impactRevision"] == 7
    scope.authorize_add_field(add, current_execution_generation=3)
    scope.authorize_ensure_field(ensure, current_execution_generation=3)
    scope.authorize_modify_field(modify, current_execution_generation=3)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: capability_domain.ReadProjectRecordRequest(
            3, _record(), ["not-a-uuid"], "lookup"
        ),
        lambda: capability_domain.QueryProjectRecordsRequest(
            3,
            PROJECT_ID,
            EMAIL_TABLE_ID,
            EMAIL_GENERATION,
            [EMAIL_FIELD_ID],
            "lookup",
            {"value": float("nan")},
            [],
            None,
            50,
        ),
        lambda: capability_domain.UpdateProjectRecordCommand(
            UPDATE_OPERATION_ID, 3, _record(), {}, 5
        ),
        lambda: capability_domain.UpdateProjectRecordCommand(
            UPDATE_OPERATION_ID, 3, _record(), {EMAIL_FIELD_ID: "x"}, 0
        ),
        lambda: capability_domain.AddProjectFieldCommand(
            FIELD_OPERATION_ID,
            3,
            PROJECT_ID,
            ACCOUNT_TABLE_ID,
            ACCOUNT_GENERATION,
            RESULT_FIELD_ID,
            {
                "key": "result",
                "name": "Result",
                "type": "unsupported",
                "required": False,
                "validation": {},
            },
            False,
            None,
            2,
        ),
    ],
)
def test_new_capability_requests_reject_invalid_json_identity_or_revision(
    factory,
) -> None:
    with pytest.raises(ProjectError):
        factory()


def test_every_new_capability_authorization_rejects_obsolete_execution_generation() -> (
    None
):
    grant_type = capability_domain.TableCapabilityGrant
    request = capability_domain.QueryProjectRecordsRequest(
        2,
        PROJECT_ID,
        EMAIL_TABLE_ID,
        EMAIL_GENERATION,
        [EMAIL_FIELD_ID],
        "lookup",
        None,
        [],
        None,
        10,
    )
    scope = TaskCapabilityScope(
        PROJECT_ID,
        TASK_ID,
        RUN_ID,
        3,
        frozenset(),
        frozenset(),
        table_grants=frozenset(
            {
                grant_type(
                    EMAIL_TABLE_ID,
                    EMAIL_GENERATION,
                    frozenset({"queryRecords"}),
                    frozenset({EMAIL_FIELD_ID}),
                    frozenset({"lookup"}),
                )
            }
        ),
    )

    with pytest.raises(ProjectError) as caught:
        scope.authorize_query_records(request, current_execution_generation=3)

    assert caught.value.code == "LEASE_REVOKED"


@pytest.mark.parametrize("run_status", ["stopping", "succeeded"])
def test_database_scope_rejects_non_running_run_even_at_current_generation(
    tmp_path, run_status: str
) -> None:
    factory, project_id, automation, coordinator = _setup(tmp_path)
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.execution_generation = 1
        run.status = run_status

    with pytest.raises(ProjectError) as caught:
        SqlAlchemyProjectDataCapabilities(factory).scope(
            project_id, task.task_id, task.run_id
        )

    assert caught.value.code == "LEASE_REVOKED"
    factory.dispose()


@pytest.mark.parametrize("run_status", ["stopping", "failed"])
def test_database_write_rechecks_run_status_after_scope_was_granted(
    tmp_path, run_status: str
) -> None:
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_status_input_ids=lambda current: (
            current.input_plan["inputs"][1]["inputId"],
        ),
    )
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    snapshot = coordinator.get_snapshot(project_id, task.task_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.execution_generation = 1
        run.status = "running"
    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    scope = service.scope(project_id, task.task_id, task.run_id)
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.status = run_status
    email = snapshot.inputs[1]
    ref = email["recordRef"]

    with pytest.raises(ProjectError) as caught:
        service.set_record_status(
            scope,
            SetRecordStatusCommand(
                uid(),
                1,
                RecordRef(
                    project_id,
                    ref["tableId"],
                    ref["datasetGeneration"],
                    RecordKey(ref["recordKey"]["type"], ref["recordKey"]["value"]),
                ),
                None,
                email["statusRevision"],
            ),
        )

    assert caught.value.code == "LEASE_REVOKED"
    factory.dispose()


def test_capability_create_uses_field_identity_and_preserves_identity_errors(
    tmp_path,
) -> None:
    targets: list[tuple[str, str]] = []
    factory, project_id, automation, coordinator = _setup(
        tmp_path,
        resolve_create_record_targets=lambda _session, _automation: targets,
    )
    account = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": "业务账号"}
    )[0]
    identity_field = DataCatalogService(
        SqlAlchemyProjectDataCatalog(factory)
    ).create_field(
        project_id,
        account["tableId"],
        uid(),
        {
            "definition": {
                "key": "account",
                "name": "账号",
                "type": "string",
                "required": False,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    field_id = identity_field["ref"]["fieldId"]
    with factory.begin() as session:
        table = session.get(DataTableRow, account["tableId"])
        assert table is not None
        table.identity = {"mode": "field", "fieldId": field_id}
    targets.append((account["tableId"], account["datasetGeneration"]))
    batch = coordinator.start(
        project_id,
        automation.automation_id,
        uid(),
        {
            "expectedAutomationRevision": automation.management_revision,
            "parameters": {},
            "maxTasks": 1,
            "concurrency": 1,
        },
    )[0]
    assert (
        ProjectBatchScheduler.claim_data_task(factory, project_id, batch.batch_id)
        == "ready"
    )
    task = coordinator.list_tasks(project_id, batch.batch_id)[0]
    with factory.begin() as session:
        run = session.get(WorkflowRunRow, task.run_id)
        assert run is not None
        run.execution_generation = 1
        run.status = "running"
    service = ProjectDataCapabilityService(SqlAlchemyProjectDataCapabilities(factory))
    scope = service.scope(project_id, task.task_id, task.run_id)

    created, replayed = service.create_record(
        scope,
        CreateProjectRecordCommand(
            uid(),
            1,
            project_id,
            account["tableId"],
            account["datasetGeneration"],
            {field_id: "001"},
        ),
    )

    assert replayed is False
    assert created["ref"]["recordKey"] == {"type": "text", "value": "001"}
    with pytest.raises(ProjectError) as duplicate:
        service.create_record(
            scope,
            CreateProjectRecordCommand(
                uid(),
                1,
                project_id,
                account["tableId"],
                account["datasetGeneration"],
                {field_id: "001"},
            ),
        )
    assert duplicate.value.code == "RECORD_ALREADY_EXISTS"
    with pytest.raises(ProjectError) as invalid:
        service.create_record(
            scope,
            CreateProjectRecordCommand(
                uid(),
                1,
                project_id,
                account["tableId"],
                account["datasetGeneration"],
                {field_id: ""},
            ),
        )
    assert invalid.value.code == "INVALID_PROJECT_DATA"
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DataRecordRow)
                .where(DataRecordRow.table_id == account["tableId"])
            )
            == 1
        )
    factory.dispose()
