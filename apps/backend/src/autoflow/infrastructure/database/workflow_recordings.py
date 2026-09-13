from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.models import WorkflowRecordingCommandRow as Command
from autoflow.infrastructure.database.models import WorkflowRecordingRow as Recording
from autoflow.infrastructure.database.models import WorkflowRecordingStepRow as Step


class RecordingRepository:
    def __init__(self, factory: sessionmaker[Session]):
        self.factory = factory

    def get(self, identifier: str) -> dict[str, Any]:
        with self.factory() as session:
            row = session.get(Recording, identifier)
            if row is None:
                raise WorkflowError('RECORDING_NOT_FOUND', '录制草稿不存在', 404)
            return deepcopy(row.payload)

    def list_records(self, offset: int, limit: int) -> list[dict[str, Any]]:
        with self.factory() as session:
            rows = session.scalars(select(Recording).order_by(Recording.payload['updatedAt'].desc(), Recording.id).offset(offset).limit(limit))
            return [deepcopy(row.payload) for row in rows]

    def create(self, record: dict[str, Any]) -> None:
        with self.factory.begin() as session:
            session.add(Recording(id=record['recordingId'], payload=record))

    def update(self, identifier: str, patch: dict[str, Any], steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with self.factory.begin() as session:
            row = session.get(Recording, identifier)
            assert row is not None
            value = {**row.payload, **deepcopy(patch), 'updatedAt': datetime.now(UTC).isoformat()}
            for step in steps or []:
                if session.get(Step, (identifier, step['seq'])) is not None:
                    continue
                if step['seq'] != value['lastSeq'] + 1:
                    raise WorkflowError('RECORDING_SEQUENCE_GAP', '录制步骤序号不连续', 409)
                session.add(Step(recording_id=identifier, seq=step['seq'], id=step['stepId'], position=step['seq'], payload=step))
                value['lastSeq'] = step['seq']
            row.payload = value
            return deepcopy(value)

    def steps(self, identifier: str, after: int = 0, limit: int = 50, *, ordered: bool = False) -> list[dict[str, Any]]:
        with self.factory() as session:
            column = Step.position if ordered else Step.seq
            rows = session.scalars(select(Step).where(Step.recording_id == identifier, column > after).order_by(column).limit(limit))
            return [{**deepcopy(row.payload), 'position': row.position} for row in rows]

    def step(self, identifier: str, step_id: str) -> dict[str, Any]:
        with self.factory() as session:
            row = session.scalar(select(Step).where(Step.recording_id == identifier, Step.id == step_id))
            if row is None:
                raise WorkflowError('RECORDING_STEP_NOT_FOUND', '录制步骤不存在', 404)
            return deepcopy(row.payload)

    def edit(self, identifier: str, revision: int, changes: list[dict[str, Any]], order: list[str] | None) -> dict[str, Any]:
        with self.factory.begin() as session:
            row = session.get(Recording, identifier)
            assert row is not None
            if row.payload['revision'] != revision:
                raise WorkflowError('RECORDING_REVISION_CONFLICT', '录制已修改，请重新加载审查结果', 409)
            steps = {s.id: s for s in session.scalars(select(Step).where(Step.recording_id == identifier))}
            if order is not None and (len(order) != len(steps) or set(order) != set(steps)):
                raise WorkflowError('RECORDING_ORDER_INVALID', '排序必须包含每个步骤一次', 422)
            for change in changes:
                target = steps.get(change['stepId'])
                if target is None:
                    raise WorkflowError('RECORDING_STEP_NOT_FOUND', '录制步骤不存在', 404)
                target.payload = {**target.payload, **{k: v for k, v in change.items() if k != 'stepId'}}
            for i, key in enumerate(order or []):
                steps[key].position = i + 1
            row.payload = {**row.payload, 'revision': revision + 1, 'updatedAt': datetime.now(UTC).isoformat()}
            return deepcopy(row.payload)

    def command(self, identifier: str, command_id: str, request_hash: str | None = None, value: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self.factory.begin() as session:
            row = session.get(Command, (identifier, command_id))
            if row is not None and request_hash is not None and row.request_hash != request_hash:
                raise WorkflowError('RECORDING_COMMAND_CONFLICT', '此标识已用于不同请求', 409)
            if value is not None:
                if row is None:
                    row = Command(recording_id=identifier, id=command_id, request_hash=request_hash, payload=value)
                    session.add(row)
                else:
                    row.payload = value
            return deepcopy(row.payload) if row else None

    def delete(self, identifier: str) -> None:
        with self.factory.begin() as session:
            row = session.get(Recording, identifier)
            if row:
                session.delete(row)

    def recover(self) -> None:
        with self.factory.begin() as session:
            for row in session.scalars(select(Recording)):
                if row.payload['browserState'] in {'starting', 'ready', 'closing'}:
                    row.payload = {**row.payload, 'browserState': 'closed', 'captureState': 'interrupted', 'pages': [], 'targetPageId': None,
                                   'error': '服务已重启，仅恢复已确认步骤；临时浏览器不恢复'}
            for command in session.scalars(select(Command)):
                if command.payload['state'] == 'accepted':
                    command.payload = {**command.payload, 'state': 'unknown', 'error': '服务中断，命令未能确认'}
