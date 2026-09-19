"""Project route registration shared by runtime and schema export."""
from dataclasses import dataclass

from fastapi import FastAPI

from autoflow.adapters.http.project_automations import project_automations_router
from autoflow.adapters.http.project_data import project_data_router
from autoflow.adapters.http.project_data_deletions import project_data_deletion_router
from autoflow.adapters.http.project_data_impacts import project_data_impact_router
from autoflow.adapters.http.project_data_records import project_records_router
from autoflow.adapters.http.project_data_schema import project_data_schema_router
from autoflow.adapters.http.project_data_status_batches import (
    record_status_batches_router,
)
from autoflow.adapters.http.project_environments import project_environments_router
from autoflow.adapters.http.project_excel import (
    internal_project_files_router,
    project_excel_inspection_router,
)
from autoflow.adapters.http.project_excel_exports import project_excel_exports_router
from autoflow.adapters.http.project_excel_imports import project_excel_import_router
from autoflow.adapters.http.project_run_events import project_run_events_router
from autoflow.adapters.http.project_run_evidence import project_run_evidence_router
from autoflow.adapters.http.project_runs import project_runs_router
from autoflow.adapters.http.project_sheets import (
    internal_google_authorizations_router,
    project_sheets_binding_router,
    project_sheets_connections_router,
    project_sync_router,
)
from autoflow.adapters.http.project_statistics import project_statistics_router
from autoflow.adapters.http.projects import project_lifecycle_router, projects_router
from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_automations.service import ProjectAutomationService
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
from autoflow.application.project_runs.coordinator import ProjectRunCoordinator
from autoflow.application.project_runs.events import ProjectRunEvents
from autoflow.application.project_runs.evidence import ProjectRunEvidence
from autoflow.application.project_runs.queries import ProjectRunQueries
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.application.project_sync.bindings import SheetsBindingService
from autoflow.application.project_sync.connections import SheetsConnectionService
from autoflow.application.project_sync.impacts import SheetsImpactService
from autoflow.application.project_sync.outbound import SheetsSyncService
from autoflow.application.projects.lifecycle import ProjectLifecycleService
from autoflow.application.projects.overview import ProjectOverviewService
from autoflow.application.projects.service import ProjectService
from autoflow.application.projects.statistics import ProjectStatisticsService
from autoflow.application.settings.runtime import QuiesceGate


@dataclass(frozen=True)
class ProjectHttpServices:
    run_coordinator: ProjectRunCoordinator
    run_events: ProjectRunEvents
    run_evidence: ProjectRunEvidence
    run_queries: ProjectRunQueries
    run_scheduler: ProjectBatchScheduler
    gate: QuiesceGate
    projects: ProjectService
    lifecycle: ProjectLifecycleService
    overview: ProjectOverviewService
    statistics: ProjectStatisticsService
    automations: ProjectAutomationService
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
    environments: EnvironmentService
    sheets_connections: SheetsConnectionService
    sheets_bindings: SheetsBindingService
    sheets_impacts: SheetsImpactService
    sync: SheetsSyncService


def register_project_routes(app: FastAPI, services: ProjectHttpServices) -> None:
    app.include_router(projects_router(services.projects, services.overview))
    app.include_router(project_lifecycle_router(services.lifecycle))
    app.include_router(project_statistics_router(services.statistics))
    app.include_router(project_runs_router(services.run_coordinator, services.run_queries, services.run_scheduler, services.gate))
    app.include_router(project_run_evidence_router(services.run_evidence))
    app.include_router(project_run_events_router(services.run_events))
    app.include_router(project_automations_router(services.automations))
    app.include_router(project_records_router(services.records, services.queries))
    app.include_router(project_data_router(services.tables, services.catalog))
    app.include_router(
        project_data_impact_router(
            services.catalog, services.deletions, services.sheets_impacts
        )
    )
    app.include_router(project_data_schema_router(services.schema))
    app.include_router(project_data_deletion_router(services.deletions))
    app.include_router(record_status_batches_router(services.status_batches))
    app.include_router(project_excel_exports_router(services.exports))
    app.include_router(project_excel_import_router(services.imports))
    app.include_router(internal_project_files_router(services.excel))
    app.include_router(project_excel_inspection_router(services.excel))
    app.include_router(project_environments_router(services.environments))
    app.include_router(internal_google_authorizations_router(services.sheets_connections))
    app.include_router(project_sheets_connections_router(services.sheets_connections))
    app.include_router(project_sheets_binding_router(services.sheets_bindings))
    app.include_router(project_sync_router(services.sync))
