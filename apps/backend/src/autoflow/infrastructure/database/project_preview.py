"""Run-private preview overlay for project data writes (remediation M2 R2-30).

A preview run writes here instead of the real rows. Its own later reads and
queries see the overlay; real records, versions, processing records, Sheets
outbound intents and environments never change. A record created in preview
gets a fresh key that only this run's overlay can resolve.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.project_data.identity import RecordKey
from autoflow.domain.project_runs.input_selection import RecordRef

from .preview_models import PreviewRecordRow
from .project_data_models import DataRecordRow


class PreviewOverlay:
    def __init__(self, session: Session, run_id: str) -> None:
        self.session, self.run_id = session, run_id

    def get(self, ref: RecordRef) -> PreviewRecordRow | None:
        return self.session.scalar(
            select(PreviewRecordRow).where(
                PreviewRecordRow.run_id == self.run_id,
                PreviewRecordRow.table_id == ref.table_id,
                PreviewRecordRow.dataset_generation == ref.dataset_generation,
                PreviewRecordRow.key_type == ref.record_key.type,
                PreviewRecordRow.key_value == ref.record_key.value,
            )
        )

    def view(self, ref: RecordRef, real: DataRecordRow | None) -> DataRecordRow | None:
        """The record as this preview sees it, as a detached row (never added to the session)."""
        overlay = self.get(ref)
        if overlay is None:
            return real
        if overlay.deleted:
            return None
        base = real
        now = overlay.updated_at
        return DataRecordRow(
            project_id=overlay.project_id,
            table_id=overlay.table_id,
            dataset_generation=overlay.dataset_generation,
            key_type=overlay.key_type,
            key_value=overlay.key_value,
            values_json=dict(overlay.values_json),
            record_slots=list(base.record_slots) if base is not None else [],
            status_id=overlay.status_id,
            current_environment_id=base.current_environment_id if base is not None else None,
            content_revision=(base.content_revision if base is not None else 0) + overlay.revision,
            status_revision=base.status_revision if base is not None else 1,
            link_revision=base.link_revision if base is not None else 1,
            deleted=False,
            created_at=base.created_at if base is not None else now,
            updated_at=now,
        )

    def write(
        self, ref: RecordRef, real: DataRecordRow | None, *, values: dict[str, Any] | None = None,
        status_id: Any = ..., deleted: bool = False,
    ) -> None:
        now = datetime.now(UTC)
        overlay = self.get(ref)
        if overlay is None:
            overlay = PreviewRecordRow(
                id=str(uuid4()), run_id=self.run_id, project_id=ref.project_id, table_id=ref.table_id,
                dataset_generation=ref.dataset_generation, key_type=ref.record_key.type,
                key_value=ref.record_key.value,
                values_json=dict(real.values_json) if real is not None else {},
                status_id=real.status_id if real is not None else None,
                created=real is None, deleted=False, revision=0, updated_at=now,
            )
            self.session.add(overlay)
        if values is not None:
            overlay.values_json = {**overlay.values_json, **values}
        if status_id is not ...:
            overlay.status_id = status_id
        overlay.deleted = deleted or overlay.deleted
        overlay.revision += 1
        overlay.updated_at = now
        self.session.flush()

    def create(self, project_id: str, table_id: str, generation: str, values: dict[str, Any]) -> RecordRef:
        ref = RecordRef(project_id, table_id, generation, RecordKey("uuid", str(uuid4())))
        self.write(ref, None, values=values)
        return ref

    def created_rows(self, table_id: str, generation: str) -> list[DataRecordRow]:
        rows = self.session.scalars(
            select(PreviewRecordRow).where(
                PreviewRecordRow.run_id == self.run_id,
                PreviewRecordRow.table_id == table_id,
                PreviewRecordRow.dataset_generation == generation,
                PreviewRecordRow.created.is_(True),
                PreviewRecordRow.deleted.is_(False),
            ).order_by(PreviewRecordRow.updated_at, PreviewRecordRow.id)
        )
        views = []
        for row in rows:
            ref = RecordRef(row.project_id, row.table_id, row.dataset_generation, RecordKey(row.key_type, row.key_value))  # type: ignore[arg-type]
            view = self.view(ref, None)
            if view is not None:
                views.append(view)
        return views
