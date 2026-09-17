from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from autoflow.infrastructure.database.workflow_models import WorkflowDocumentRow
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)

NOW = datetime(2026, 9, 15, 8, 0, tzinfo=UTC)


def create_queued_run(factory, *, node_ids=("open",), resource_request=None):
    with factory() as session:
        repository = SqlAlchemyWorkflowRuntimeRepository(session)
        workflow_id = str(uuid4())
        session.add(
            WorkflowDocumentRow(
                id=workflow_id,
                name="dispatcher fixture",
                document={},
                layout={},
                revision=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
        content = repository.prepare_content(
            prepared_content_id=str(uuid4()),
            prepare_operation_id=str(uuid4()),
            request_digest="a" * 64,
            workflow_id=workflow_id,
            source_revision=1,
            checksum="b" * 64,
            document={
                "frozen": True,
                "content": {
                    "variables": [
                        {"name": "fromDocument", "value": "frozen"},
                        {"name": "count", "value": 99},
                    ]
                },
            },
            execution_plan={"orderedNodeIds": list(node_ids), "frozen": True},
            adapter_version="webrpa-chain/v1",
            capability_requirements=["browser.cloakbrowser"],
            provenance={"kind": "test"},
            created_at=NOW,
        )
        run = repository.prepare_run(
            run_id=str(uuid4()),
            run_request_id=str(uuid4()),
            request_digest="c" * 64,
            prepared_content_id=content.prepared_content_id,
            parameters={"count": 0, "enabled": False, "name": "测试"},
            input_snapshot_ref=None,
            resource_request=resource_request or {"frozen": "request"},
            capability_bindings=[],
            created_at=NOW,
        )
        session.commit()
        return run, content


class SyntheticLease:
    def __init__(self) -> None:
        self.executable = Path(__file__).resolve()
        self.browser = {"token": "resolved"}
        self.released = False

    def release(self) -> None:
        self.released = True


class SyntheticResources:
    def __init__(
        self, *, blocked=None, cleanup_failure: Exception | None = None
    ) -> None:
        self.blocked = blocked
        self.cleanup_failure = cleanup_failure
        self.requests: list[tuple[dict, str]] = []
        self.lease = SyntheticLease()

    async def acquire(self, request, run_request_id):
        self.requests.append((dict(request), run_request_id))
        if self.blocked is not None:
            try:
                await self.blocked.wait()
            except BaseException:
                if self.cleanup_failure is not None:
                    raise self.cleanup_failure
                self.lease.release()
                raise
        return self.lease
