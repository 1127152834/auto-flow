from uuid import uuid4

from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService
from autoflow.infrastructure.database.project_claims import SqlAlchemyProjectInputGroups
from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData
from autoflow.infrastructure.database.project_data_catalog import (
    SqlAlchemyProjectDataCatalog,
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
