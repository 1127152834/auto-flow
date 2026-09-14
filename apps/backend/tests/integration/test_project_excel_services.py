from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from openpyxl import Workbook

from autoflow.application.project_data.excel import ProjectExcelService
from autoflow.application.projects.service import ProjectService
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.models import Base
from autoflow.infrastructure.database.projects import SqlAlchemyProjects
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def _id():
    return str(uuid4())


def _xlsx(path: Path, rows):
    book = Workbook()
    sheet = book.active
    sheet.append(["Code", "Amount"])
    for row in rows:
        sheet.append(row)
    book.save(path)


@pytest.fixture
def context(tmp_path):
    database = tmp_path / "excel.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    # Root migration integration is intentionally separate; exercise the dedicated ORM now.
    Base.metadata.create_all(factory.kw["bind"])
    project = ProjectService(SqlAlchemyProjects(factory)).create(_id(), {"name": "P"})[
        0
    ]
    service = ProjectExcelService(factory, workspace_id="ws", instance_id="instance")
    yield service, factory, project.project_id, tmp_path
    factory.dispose()


def _register(service, project, path, *, purpose="import"):
    token = _id()
    service.register_selection(
        {
            "selectionToken": token,
            "path": str(path),
            "purpose": "inspectExcel" if purpose == "import" else "exportXlsx",
            "projectId": project,
            "windowId": 7,
            "expiresAt": datetime.now(UTC) + timedelta(minutes=5),
        },
        "w" * 32,
    )
    return token


def test_inspection_consumes_bound_selection_once_and_survives_token_replay(context):
    service, _, project, root = context
    source = root / "source.xlsx"
    _xlsx(source, [("001", 2)])
    token = _register(service, project, source)
    key = _id()

    first = service.inspect(project, key, token, 7, "w" * 32)
    replay = service.inspect(project, key, token, 7, "w" * 32)

    assert first == replay
    assert first["operation"]["status"] == "succeeded"
    assert first["inspection"]["sheets"][0]["headers"] == ["Code", "Amount"]
    with pytest.raises(ProjectError) as caught:
        service.inspect(project, _id(), token, 7, "w" * 32)
    assert caught.value.code == "FILE_SELECTION_CONSUMED"


def test_inspection_rejects_other_window_proof_without_consuming_selection(context):
    service, _, project, root = context
    source = root / "source.xlsx"
    _xlsx(source, [("001", 2)])
    token = _register(service, project, source)
    with pytest.raises(ProjectError) as caught:
        service.inspect(project, _id(), token, 8, "x" * 32)
    assert caught.value.code == "FILE_WINDOW_MISMATCH"
    assert (
        service.inspect(project, _id(), token, 7, "w" * 32)["inspection"]["filename"]
        == "source.xlsx"
    )


# Import/reimport/export assertions live in the real HTTP contract suites
# test_pm2_excel_imports.py / test_pm2_excel_exports.py and durable export tests.
# The never-delivered synchronous prototype has been replaced by accepted operations.
