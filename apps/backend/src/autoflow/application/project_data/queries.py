from __future__ import annotations

from typing import Any, Protocol

from autoflow.application.project_data.tables import _canonical_uuid, _validation
from autoflow.domain.project_data.identity import MAX_SAFE_INTEGER


class ProjectDataQueries(Protocol):
    def query(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        filter_value: Any,
        order_value: Any,
        page: int,
        page_size: int,
    ) -> dict[str, Any]: ...


class DataRecordQueryService:
    def __init__(self, queries: ProjectDataQueries):
        self.queries = queries

    def query(
        self,
        project_id: str,
        table_id: str,
        generation: str,
        filter_value: str,
        order_value: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        from autoflow.domain.project_data.query import decode_query

        for value, name in (
            (project_id, "projectId"),
            (table_id, "tableId"),
            (generation, "datasetGeneration"),
        ):
            _canonical_uuid(value, name)
        if type(page) is not int or not 1 <= page <= MAX_SAFE_INTEGER:
            raise _validation("page", "Must be a positive JSON-safe integer")
        if type(page_size) is not int or not 1 <= page_size <= 200:
            raise _validation("pageSize", "Must be between 1 and 200")
        return self.queries.query(
            project_id,
            table_id,
            generation,
            decode_query(filter_value, "filter"),
            decode_query(order_value, "orderBy"),
            page,
            page_size,
        )
