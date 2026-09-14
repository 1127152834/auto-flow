"""Project table commands use real migrations and operation persistence."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update

from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import ProjectOperationRow, ProjectRow
from autoflow.infrastructure.database.project_data_models import (
    DataChangeRow,
    DataRecordRow,
    DataTableRow,
)
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def key():
    return str(uuid4())


@pytest.fixture
def context(tmp_path):
    from autoflow.application.project_data.tables import DataTableService
    from autoflow.infrastructure.database.project_data import SqlAlchemyProjectData

    path = tmp_path / 'tables.sqlite3'
    migrate_database(path)
    factory = create_session_factory(path)
    projects = ProjectService(SqlAlchemyProjects(factory))
    p = projects.create(key(), {'name': 'project'})[0].project_id
    other = projects.create(key(), {'name': 'other'})[0].project_id
    yield DataTableService(SqlAlchemyProjectData(factory)), projects, factory, p, other
    factory.dispose()


def test_create_blank_table_is_atomic_and_replayable_after_edit(context):
    service, projects, factory, project, _ = context
    operation_key = key()
    first, operation, replay = service.create(project, operation_key, {'name':'  Accounts  ', 'sourceKind':'local'})
    assert not replay and first['name'] == 'Accounts'
    assert first['identity'] == {'mode':'system'}
    assert first['recordCount'] == 0 and first['slotDefinitions'] == []
    assert first['tableRevision'] == 1
    assert operation.resource == {'type':'table','projectId':project,'tableId':first['tableId']}
    saved, _, _ = service.update(project, first['tableId'], key(), {'name':'Renamed','expectedTableRevision':1})
    assert saved['tableRevision'] == 2
    again, replayed, replay = service.create(project, operation_key, {'name':'Accounts','sourceKind':'local'})
    assert replay and again == first and replayed.operation_id == operation.operation_id
    found = projects.operation(key=operation_key, project_id=project)
    assert found.result == first
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProjectOperationRow).where(ProjectOperationRow.kind=='createTable')) == 1


def test_table_scope_and_cross_project_operation_identity(context):
    service, _, _, project, other = context
    operation_key = key()
    first, _, _ = service.create(project, operation_key, {'name':'Data','sourceKind':'local'})
    for action in (
        lambda:service.get(other,first['tableId']),
        lambda:service.update(other,first['tableId'],key(),{'name':'Oops','expectedTableRevision':1}),
    ):
        with pytest.raises(ProjectError) as error:
            action()
        assert error.value.status == 404
    with pytest.raises(ProjectError) as error:
        service.create(other,operation_key,{'name':'Data','sourceKind':'local'})
    assert error.value.code == 'OPERATION_PAYLOAD_MISMATCH'


def test_same_name_concurrent_creation_has_single_success(context):
    service, _, _, project, _ = context
    def create(name):
        try:
            return service.create(project,key(),{'name':name,'sourceKind':'local'})[0]['tableId']
        except ProjectError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results=list(workers.map(create,['Accounts',' accounts ']))
    assert results.count('TABLE_NAME_CONFLICT') == 1
    items,total=service.list(project)
    assert total == len(items) == 1


def test_table_edit_cas_noop_and_idempotency_precede_revision(context):
    service, _, _, project, _ = context
    table,_,_=service.create(project,key(),{'name':'Data','sourceKind':'local'})
    table_id=table['tableId']
    noop,_,_=service.update(project,table_id,key(),{'description':'','expectedTableRevision':1})
    assert noop['tableRevision']==1 and noop['updatedAt']==table['updatedAt']
    edit_key=key()
    saved,operation,_=service.update(project,table_id,edit_key,{'description':'new','expectedTableRevision':1})
    replay,op,replayed=service.update(project,table_id,edit_key,{'description':'new','expectedTableRevision':1})
    assert replayed and replay==saved and op.operation_id==operation.operation_id
    with pytest.raises(ProjectError) as error:
        service.update(project,table_id,key(),{'description':'stale','expectedTableRevision':1})
    assert error.value.code=='REVISION_CONFLICT'
    assert error.value.details['current']['description']=='new'
    with pytest.raises(ProjectError) as error:
        service.update(project,table_id,edit_key,{'description':'different','expectedTableRevision':1})
    assert error.value.code=='OPERATION_PAYLOAD_MISMATCH'


def test_cas_error_keeps_revision_from_the_same_snapshot_after_rollback(context):
    service, _, factory, project, _ = context
    table, _, _ = service.create(project, key(), {"name": "Data"})
    service.update(project, table["tableId"], key(), {"description": "v2", "expectedTableRevision": 1})

    def advance_after_rollback(_session):
        with factory.begin() as concurrent:
            concurrent.execute(update(DataTableRow).where(DataTableRow.id == table["tableId"]).values(table_revision=3))

    event.listen(factory.class_, "after_rollback", advance_after_rollback)
    try:
        with pytest.raises(ProjectError) as caught:
            service.update(project, table["tableId"], key(), {"description": "stale", "expectedTableRevision": 1})
    finally:
        event.remove(factory.class_, "after_rollback", advance_after_rollback)
    assert caught.value.details["currentRevision"] == 2
    assert caught.value.details["current"]["tableRevision"] == 2


@pytest.mark.parametrize('state,status',[('closing',423),('archived',409),('deleting',409),('deleted',404)])
def test_table_management_enforces_project_lifecycle(context,state,status):
    service,_,factory,project,_=context
    table,_,_=service.create(project,key(),{'name':'Data','sourceKind':'local'})
    with factory.begin() as session:
        session.get(ProjectRow,project).lifecycle_state=state
    for action in (
        lambda: service.create(project,key(),{'name':'Another','sourceKind':'local'}),
        lambda: service.update(project,table['tableId'],key(),{'description':'new','expectedTableRevision':1}),
    ):
        with pytest.raises(ProjectError) as error:action()
        assert error.value.status==status
    if state!='deleted':
        assert service.get(project,table['tableId'])['name']=='Data'


def test_directory_filters_paginates_and_preserves_literal_search(context):
    service,_,_,project,other=context
    for name,description in [
        ('Alpha','x%_'), ('Beta','middle'), ('中文😀','third'),
        ('Straße','fourth'), ('Résumé','Ärger'),
    ]:
        service.create(project,key(),{'name':name,'description':description,'sourceKind':'local'})
    service.create(other,key(),{'name':'Invisible','sourceKind':'local'})
    items,total=service.list(project,sort='name',page=2,page_size=1)
    assert total==5 and items[0]['name']=='Beta'
    matches,count=service.list(project,q='%_')
    assert count==1 and matches[0]['name']=='Alpha'
    assert service.list(project,q='STRASSE')[0][0]['name']=='Straße'
    assert service.list(project,q='ärger')[0][0]['name']=='Résumé'
    assert service.list(project,q='NONE')[1]==0


@pytest.mark.parametrize('payload',[
    {'name':'','sourceKind':'local'}, {'name':'a'*121,'sourceKind':'local'},
    {'name':'ok','sourceKind':'sheets'}, {'name':'ok','description':'a'*1001},
    {'name':'bad\ud800','sourceKind':'local'},
    {'name':'ok','description':'bad\ud800'},
    {'name':'ok','recordCount':999},
])
def test_table_validation_rejects_unknown_and_invalid_values(context,payload):
    service,_,_,project,_=context
    with pytest.raises(ProjectError) as error:service.create(project,key(),payload)
    assert error.value.status==422


@pytest.mark.parametrize("operation_key", ["not-a-uuid", str(uuid4()).upper(), "  " + str(uuid4()) + "  "])
def test_table_commands_require_canonical_uuid_operation_keys(context, operation_key):
    service, _, _, project, _ = context
    with pytest.raises(ProjectError) as error:
        service.create(project, operation_key, {"name": "Data"})
    assert error.value.status == 422


@pytest.mark.parametrize(
    "query",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 201},
        {"sort": "recordCount"},
        {"source_kind": "unknown"},
        {"q": 1},
    ],
)
def test_table_directory_rejects_invalid_queries(context, query):
    service, _, _, project, _ = context
    with pytest.raises(ProjectError) as error:
        service.list(project, **query)
    assert error.value.status == 422


@pytest.mark.parametrize("query", ["\x00no-match", "line\nbreak", "bad\ud800"])
def test_table_directory_rejects_control_and_surrogate_search(context, query):
    service, _, _, project, _ = context
    service.create(project, key(), {"name": "Visible"})
    with pytest.raises(ProjectError) as error:
        service.list(project, q=query)
    assert error.value.status == 422


def test_table_mutations_write_changes_and_failed_conflict_is_atomic(context):
    service, projects, factory, project, _ = context
    created, create_operation, _ = service.create(project, key(), {"name": "Data"})
    failed_key = key()
    with pytest.raises(ProjectError) as error:
        service.create(project, failed_key, {"name": " data "})
    assert error.value.code == "TABLE_NAME_CONFLICT"
    with pytest.raises(ProjectError):
        projects.operation(key=failed_key, project_id=project)

    updated, update_operation, _ = service.update(
        project,
        created["tableId"],
        key(),
        {"description": "changed", "expectedTableRevision": 1},
    )
    with factory() as session:
        changes = session.scalars(
            select(DataChangeRow).order_by(DataChangeRow.created_at, DataChangeRow.id)
        ).all()
    assert [change.operation_id for change in changes] == [
        create_operation.operation_id,
        update_operation.operation_id,
    ]
    assert changes[0].before is None and changes[0].after == created
    assert changes[1].before == created and changes[1].after == updated


def test_table_directory_source_filter_and_real_record_count(context):
    service, _, factory, project, _ = context
    created, _, _ = service.create(project, key(), {"name": "Data"})
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    with factory.begin() as session:
        session.add(DataRecordRow(
            project_id=project, table_id=created["tableId"],
            dataset_generation=created["datasetGeneration"], key_type="text", key_value="one",
            values_json={}, record_slots=[], status_id=None, current_environment_id=None,
            content_revision=1, status_revision=1, link_revision=1, deleted=False,
            created_at=now, updated_at=now,
        ))
    items, total = service.list(project, source_kind="local")
    assert total == 1 and items[0]["recordCount"] == 1
    assert service.list(project, source_kind=None)[1] == 1
