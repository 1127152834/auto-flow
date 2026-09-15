from uuid import uuid4

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database import project_claims
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
)
from autoflow.infrastructure.database.project_data_models import (
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.project_data_records import (
    SqlAlchemyProjectDataRecords,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def uid() -> str:
    return str(uuid4())


def _table_with_record(factory, project_id: str, name: str, value: str):
    table = DataTableService(SqlAlchemyProjectData(factory)).create(project_id, uid(), {"name": name})[0]
    field = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        table["tableId"],
        uid(),
        {
            "definition": {"key": "value", "name": "值", "type": "string", "required": True, "validation": {}},
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    record = DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
        project_id,
        table["tableId"],
        uid(),
        {"datasetGeneration": table["datasetGeneration"], "values": [{"fieldId": field["ref"]["fieldId"], "value": value}]},
    )[0]
    return table, field, record


def _empty_table(factory, project_id: str, name: str):
    table = DataTableService(SqlAlchemyProjectData(factory)).create(
        project_id, uid(), {"name": name}
    )[0]
    field = DataCatalogService(SqlAlchemyProjectDataCatalog(factory)).create_field(
        project_id,
        table["tableId"],
        uid(),
        {
            "definition": {
                "key": "value",
                "name": "值",
                "type": "string",
                "required": True,
                "validation": {},
            },
            "expectedTableRevision": 1,
            "sourceColumnPolicy": "localOnly",
        },
    )[0]["field"]
    return table, field


def _add_record(factory, project_id: str, table: dict, field: dict, value: str):
    return DataRecordService(SqlAlchemyProjectDataRecords(factory)).create(
        project_id,
        table["tableId"],
        uid(),
        {
            "datasetGeneration": table["datasetGeneration"],
            "values": [{"fieldId": field["ref"]["fieldId"], "value": value}],
        },
    )[0]


def _input(project_id: str, table: dict, field: dict, alias: str) -> dict:
    return {
        "inputId": uid(),
        "alias": alias,
        "tableId": table["tableId"],
        "datasetGeneration": table["datasetGeneration"],
        "mode": "independent",
        "required": True,
        "fieldBindings": [{
            "inputFieldId": uid(),
            "inputFieldAlias": "值",
            "fieldRef": {
                "projectId": project_id,
                "tableId": table["tableId"],
                "datasetGeneration": table["datasetGeneration"],
                "fieldId": field["ref"]["fieldId"],
            },
        }],
        "filter": {"type": "all", "items": []},
        "orderBy": [{"systemField": "recordKey", "direction": "asc"}],
    }


def test_selects_two_real_records_and_freezes_typed_refs(tmp_path):
    path = tmp_path / "input-groups.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(uid(), {"name": "PM4"})[0].project_id
    people, people_field, person = _table_with_record(factory, project_id, "人员", "张三")
    emails, email_field, email = _table_with_record(factory, project_id, "邮箱", "pm4@example.test")
    plan = {"inputs": [_input(project_id, people, people_field, "人员"), _input(project_id, emails, email_field, "邮箱")]}

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan)

    assert result.status == "ready"
    assert [item.value["alias"] for item in result.inputs] == ["人员", "邮箱"]
    assert [item.record_ref.record_key.type for item in result.inputs] == ["uuid", "uuid"]
    assert result.inputs[0].record_ref.record_key.value == person["ref"]["recordKey"]["value"]
    assert result.inputs[1].record_ref.record_key.value == email["ref"]["recordKey"]["value"]
    assert result.inputs[0].value["contentRevision"] == 1
    factory.dispose()


def test_stale_generation_is_configuration_error_not_no_match(tmp_path):
    path = tmp_path / "stale-input.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(uid(), {"name": "PM4"})[0].project_id
    people, field, _record = _table_with_record(factory, project_id, "人员", "张三")
    first = _input(project_id, people, field, "人员")
    second = {**_input(project_id, people, field, "邮箱"), "datasetGeneration": uid()}
    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(project_id, {"inputs": [first, second]})
    assert result.status == "configurationError"
    assert result.inputs == ()
    factory.dispose()


def test_fixed_record_and_optional_empty_are_resolved_without_inventing_data(tmp_path):
    path = tmp_path / "fixed-optional.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    people, people_field, first = _table_with_record(
        factory, project_id, "人员", "甲"
    )
    second = _add_record(factory, project_id, people, people_field, "乙")
    empty, empty_field = _empty_table(factory, project_id, "可选资料")
    fixed = {
        **_input(project_id, people, people_field, "指定人员"),
        "mode": "fixedRecord",
        "fixedRecord": second["ref"],
    }
    optional = {
        **_input(project_id, empty, empty_field, "可选资料"),
        "required": False,
    }

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [fixed, optional]}
        )

    assert result.status == "ready"
    assert [item.record_ref for item in result.inputs] == [
        result.inputs[0].record_ref
    ]
    assert result.inputs[0].record_ref.record_key.value == second["ref"]["recordKey"]["value"]
    assert result.inputs[0].record_ref.record_key.value != first["ref"]["recordKey"]["value"]
    assert [(item.input_id, item.reason) for item in result.unavailable_inputs] == [
        (optional["inputId"], "no_match")
    ]
    factory.dispose()


def test_fixed_record_still_has_to_match_the_current_filter(tmp_path):
    path = tmp_path / "fixed-filter.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    people, field, first = _table_with_record(factory, project_id, "人员", "甲")
    second = _add_record(factory, project_id, people, field, "乙")
    fixed = {
        **_input(project_id, people, field, "指定人员"),
        "mode": "fixedRecord",
        "fixedRecord": second["ref"],
        "filter": {
            "type": "compare",
            "fieldId": field["ref"]["fieldId"],
            "operator": "eq",
            "value": "甲",
        },
    }

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [fixed]}
        )

    assert result.status == "noMatch"
    assert result.inputs == ()
    assert first["ref"] != second["ref"]
    factory.dispose()


def test_invalid_optional_input_is_a_configuration_error(tmp_path):
    path = tmp_path / "optional-configuration.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    people, field, _record = _table_with_record(factory, project_id, "人员", "甲")
    optional = {
        **_input(project_id, people, field, "可选人员"),
        "required": False,
        "datasetGeneration": uid(),
    }

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [optional]}
        )

    assert result.status == "configurationError"
    assert result.inputs == ()
    factory.dispose()


def test_same_table_independent_roles_backtrack_while_same_record_relation_aliases(tmp_path):
    path = tmp_path / "same-table-roles.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    records, field, first = _table_with_record(factory, project_id, "角色", "R01")
    second = _add_record(factory, project_id, records, field, "R02")
    x = _input(project_id, records, field, "X")
    y = {
        **_input(project_id, records, field, "Y"),
        "filter": {
            "type": "compare",
            "fieldId": field["ref"]["fieldId"],
            "operator": "eq",
            "value": "R01",
        },
    }
    alias = {
        **_input(project_id, records, field, "同一记录别名"),
        "mode": "related",
        "relation": {"type": "sameRecord", "sourceInputId": x["inputId"]},
    }

    with factory() as session:
        distinct = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [x, y]}
        )
        shared = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [x, alias]}
        )

    assert distinct.status == "ready"
    assert [item.record_ref.record_key.value for item in distinct.inputs] == [
        second["ref"]["recordKey"]["value"],
        first["ref"]["recordKey"]["value"],
    ]
    assert shared.status == "ready"
    assert shared.inputs[0].record_ref == shared.inputs[1].record_ref
    assert len(shared.lease_keys) == 1
    factory.dispose()


def test_field_equals_is_exact_and_reports_ambiguous_real_rows(tmp_path):
    path = tmp_path / "field-equals.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    people, people_field, _person = _table_with_record(
        factory, project_id, "人员", "account-1"
    )
    accounts, account_field, account = _table_with_record(
        factory, project_id, "账号", "account-1"
    )
    source = _input(project_id, people, people_field, "人员")
    target = {
        **_input(project_id, accounts, account_field, "账号"),
        "mode": "related",
        "relation": {
            "type": "fieldEquals",
            "sourceInputId": source["inputId"],
            "sourceFieldRef": people_field["ref"],
            "targetFieldRef": account_field["ref"],
        },
    }
    with factory() as session:
        ready = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [source, target]}
        )
    assert ready.status == "ready"
    assert ready.inputs[1].record_ref.record_key.value == account["ref"]["recordKey"]["value"]

    _add_record(factory, project_id, accounts, account_field, "account-1")
    with factory() as session:
        ambiguous = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [source, target]}
        )
    assert ambiguous.status == "ambiguous"
    assert ambiguous.inputs == ()
    factory.dispose()


def test_record_slot_resolves_the_declared_target_record(tmp_path):
    path = tmp_path / "record-slot.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    people, people_field, person = _table_with_record(factory, project_id, "人员", "甲")
    managers, manager_field, manager = _table_with_record(
        factory, project_id, "经理", "乙"
    )
    slot_id = uid()
    with factory() as session:
        table_row = session.get(DataTableRow, people["tableId"])
        record_row = session.get(
            DataRecordRow,
            (
                people["datasetGeneration"],
                person["ref"]["recordKey"]["type"],
                person["ref"]["recordKey"]["value"],
            ),
        )
        assert table_row is not None and record_row is not None
        table_row.slot_definitions = [
            {
                "slotId": slot_id,
                "name": "经理",
                "targetTableId": managers["tableId"],
                "required": False,
            }
        ]
        record_row.record_slots = [{"slotId": slot_id, "target": manager["ref"]}]
        session.commit()
    source = _input(project_id, people, people_field, "人员")
    target = {
        **_input(project_id, managers, manager_field, "经理"),
        "mode": "related",
        "relation": {
            "type": "recordSlot",
            "sourceInputId": source["inputId"],
            "slotId": slot_id,
        },
    }
    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [source, target]}
        )
    assert result.status == "ready"
    assert result.inputs[1].record_ref.record_key.value == manager["ref"]["recordKey"]["value"]
    factory.dispose()


def test_repository_bounds_each_physical_scan_before_materializing_candidates(
    tmp_path, monkeypatch
):
    path = tmp_path / "scan-budget.sqlite3"
    migrate_database(path)
    factory = create_session_factory(path)
    project_id = ProjectService(SqlAlchemyProjects(factory)).create(
        uid(), {"name": "PM4"}
    )[0].project_id
    records, field, _first = _table_with_record(factory, project_id, "资料", "R1")
    _add_record(factory, project_id, records, field, "R2")
    _add_record(factory, project_id, records, field, "R3")
    monkeypatch.setattr(project_claims, "MAX_CANDIDATE_EVALUATIONS", 2)

    with factory() as session:
        result = SqlAlchemyProjectInputGroups(session).select_required(
            project_id, {"inputs": [_input(project_id, records, field, "资料")]}
        )

    assert result.status == "scanBudgetExceeded"
    assert result.issue_input_ids
    factory.dispose()
