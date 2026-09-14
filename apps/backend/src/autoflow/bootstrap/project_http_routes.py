"""Project route registration shared by runtime and schema export."""
from dataclasses import dataclass

from fastapi import FastAPI

from autoflow.adapters.http.project_data import project_data_router
from autoflow.adapters.http.project_data_deletions import project_data_deletion_router
from autoflow.adapters.http.project_data_impacts import project_data_impact_router
from autoflow.adapters.http.project_data_records import project_records_router
from autoflow.adapters.http.project_data_schema import project_data_schema_router
from autoflow.adapters.http.project_data_status_batches import (
    record_status_batches_router,
)
from autoflow.adapters.http.project_excel import (
    internal_project_files_router,
    project_excel_inspection_router,
)
from autoflow.adapters.http.project_excel_exports import project_excel_exports_router
from autoflow.adapters.http.project_excel_imports import project_excel_import_router
from autoflow.adapters.http.projects import projects_router
from autoflow.application.project_data.catalog import DataCatalogService
from autoflow.application.project_data.deletions import DataDeletionService
from autoflow.application.project_data.excel import ProjectExcelService
from autoflow.application.project_data.excel_export import ProjectExcelExportService
from autoflow.application.project_data.excel_import import ExcelImportService
from autoflow.application.project_data.queries import DataRecordQueryService
from autoflow.application.project_data.records import DataRecordService
from autoflow.application.project_data.schema import DataSchemaService
from autoflow.application.project_data.status_batches import RecordStatusBatchService
from autoflow.application.project_data.tables import DataTableService
from autoflow.application.projects.service import ProjectService


@dataclass(frozen=True)
class ProjectHttpServices:
    projects: ProjectService
    tables: DataTableService
    catalog: DataCatalogService
    records: DataRecordService
    queries: DataRecordQueryService
    deletions: DataDeletionService
    schema: DataSchemaService
    status_batches: RecordStatusBatchService
    excel: ProjectExcelService
    imports: ExcelImportService
    exports: ProjectExcelExportService


def register_project_routes(app: FastAPI, services: ProjectHttpServices) -> None:
    app.include_router(projects_router(services.projects))
    app.include_router(project_records_router(services.records, services.queries))
    app.include_router(project_data_router(services.tables, services.catalog))
    app.include_router(project_data_impact_router(services.catalog, services.deletions))
    app.include_router(project_data_schema_router(services.schema))
    app.include_router(project_data_deletion_router(services.deletions))
    app.include_router(record_status_batches_router(services.status_batches))
    app.include_router(project_excel_exports_router(services.exports))
    app.include_router(project_excel_import_router(services.imports))
    app.include_router(internal_project_files_router(services.excel))
    app.include_router(project_excel_inspection_router(services.excel))
