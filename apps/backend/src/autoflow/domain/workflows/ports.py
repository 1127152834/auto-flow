from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .document import SavedWorkflow, WorkflowDraft, WorkflowSummaryPage


class WorkflowDocumentRepository(Protocol):
    def create(
        self,
        draft: WorkflowDraft,
        *,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> SavedWorkflow: ...

    def get(self, workflow_id: str) -> SavedWorkflow | None: ...

    def list_summaries(self, cursor: int, limit: int) -> WorkflowSummaryPage: ...

    def update(
        self,
        workflow_id: str,
        draft: WorkflowDraft,
        *,
        expected_revision: int,
        client_request_id: str,
        request_digest: str,
        now: datetime,
    ) -> SavedWorkflow: ...

    def delete(self, workflow_id: str, *, expected_revision: int) -> None: ...
