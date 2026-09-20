from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from autoflow.domain.workflows.errors import WorkflowDocumentError
from autoflow.domain.workflows.modules import CustomModuleDraft, SavedCustomModule
from autoflow.domain.workflows.ports import CustomModuleRepository


def _digest(
    operation: str,
    module_id: str,
    payload: Mapping[str, object],
    expected_revision: int | None,
) -> str:
    encoded = json.dumps(
        {
            "operation": operation,
            "moduleId": module_id,
            "expectedRevision": expected_revision,
            "payload": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class CustomModuleService:
    def __init__(
        self,
        repository: CustomModuleRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        workflow_dependents: Callable[[str], tuple[str, ...]] = lambda _module_id: (),
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._workflow_dependents = workflow_dependents

    def bind_workflow_dependents(
        self, resolver: Callable[[str], tuple[str, ...]]
    ) -> None:
        self._workflow_dependents = resolver

    def list(
        self, *, category: str | None = None, search: str | None = None
    ) -> tuple[SavedCustomModule, ...]:
        modules = list(self._repository.list_all())
        if category:
            modules = [
                module
                for module in modules
                if module.definition.get("category") == category
            ]
        if search:
            needle = search.casefold()

            def matches(module: SavedCustomModule) -> bool:
                definition = module.definition
                values = (
                    definition.get("display_name"),
                    definition.get("name"),
                    definition.get("description"),
                )
                tags = definition.get("tags", [])
                return any(
                    needle in str(value or "").casefold() for value in values
                ) or (
                    isinstance(tags, list)
                    and any(needle in str(value).casefold() for value in tags)
                )

            modules = [module for module in modules if matches(module)]
        modules.sort(key=lambda module: module.updated_at, reverse=True)
        return tuple(modules)

    def get(self, module_id: str) -> SavedCustomModule:
        module = self._repository.get(module_id)
        if module is None:
            raise WorkflowDocumentError(
                "CUSTOM_MODULE_NOT_FOUND", "模块不存在", 404, {"moduleId": module_id}
            )
        return module

    def exists(self, module_id: str) -> bool:
        return self._repository.get(module_id) is not None

    def create(
        self, payload: Mapping[str, object], *, client_request_id: str
    ) -> SavedCustomModule:
        self._require_request_id(client_request_id)
        draft = CustomModuleDraft.from_payload(payload)
        suffix = uuid5(
            NAMESPACE_URL, f"autoflow-custom-module:{client_request_id}"
        ).hex[:8]
        module_id = CustomModuleDraft.generated_id(draft.name, suffix)
        self._validate_dependencies(module_id, draft.dependencies)
        return self._repository.create(
            module_id,
            draft,
            client_request_id=client_request_id,
            request_digest=_digest("create", module_id, draft.definition, None),
            now=self._clock(),
        )

    def update(
        self,
        module_id: str,
        payload: Mapping[str, object],
        *,
        expected_revision: int,
        client_request_id: str,
    ) -> SavedCustomModule:
        self._require_request_id(client_request_id)
        current = self.get(module_id)
        draft = CustomModuleDraft.from_payload(payload, base=current.definition)
        self._validate_dependencies(module_id, draft.dependencies)
        return self._repository.update(
            module_id,
            draft,
            expected_revision=expected_revision,
            client_request_id=client_request_id,
            request_digest=_digest(
                "update", module_id, draft.definition, expected_revision
            ),
            now=self._clock(),
        )

    def delete(
        self,
        module_id: str,
        *,
        expected_revision: int,
        client_request_id: str,
    ) -> None:
        self._require_request_id(client_request_id)
        dependents = [
            module.id
            for module in self._repository.list_all()
            if module.id != module_id and module_id in module.dependencies
        ]
        workflow_ids = list(self._workflow_dependents(module_id))
        if dependents or workflow_ids:
            raise WorkflowDocumentError(
                "CUSTOM_MODULE_IN_USE",
                "模块仍被工作流或其他自定义模块引用",
                409,
                {
                    "moduleId": module_id,
                    "dependentModuleIds": dependents,
                    "dependentWorkflowIds": workflow_ids,
                },
            )
        self._repository.delete(
            module_id,
            expected_revision=expected_revision,
            client_request_id=client_request_id,
            request_digest=_digest(
                "delete", module_id, {"moduleId": module_id}, expected_revision
            ),
            now=self._clock(),
        )

    def duplicate(
        self,
        module_id: str,
        *,
        new_name: str | None,
        client_request_id: str,
    ) -> SavedCustomModule:
        source = self.get(module_id)
        names = {module.name for module in self._repository.list_all()}
        candidate = (new_name or "").strip()
        if not candidate:
            base = source.name
            candidate = f"{base}_copy"
            index = 2
            while candidate in names:
                candidate = f"{base}_copy{index}"
                index += 1
        payload = dict(source.definition)
        payload.update(
            {
                "name": candidate,
                "display_name": f"{source.definition.get('display_name', source.name)} (副本)",
            }
        )
        return self.create(payload, client_request_id=client_request_id)

    def import_module(
        self, payload: Mapping[str, object], *, client_request_id: str
    ) -> SavedCustomModule:
        name = str(payload.get("name") or "imported_module").strip()
        names = {module.name for module in self._repository.list_all()}
        if name in names:
            base = name
            index = 1
            while f"{base}_imported{index}" in names:
                index += 1
            name = f"{base}_imported{index}"
        imported = dict(payload)
        imported["name"] = name
        imported["usage_count"] = 0
        imported["download_count"] = 0
        return self.create(imported, client_request_id=client_request_id)

    def increment_usage(self, module_id: str) -> SavedCustomModule:
        self.get(module_id)
        return self._repository.increment_usage(module_id)

    def freeze_closure(
        self, module_ids: tuple[str, ...]
    ) -> dict[str, dict[str, object]]:
        frozen: dict[str, dict[str, object]] = {}
        visiting: list[str] = []

        def visit(module_id: str) -> None:
            if module_id in frozen:
                return
            if module_id in visiting:
                cycle = " -> ".join((*visiting, module_id))
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_CYCLE", f"检测到自定义模块循环引用: {cycle}", 422
                )
            module = self.get(module_id)
            visiting.append(module_id)
            for dependency in module.dependencies:
                visit(dependency)
            visiting.pop()
            payload = module.to_payload()
            payload["dependencyIds"] = list(module.dependencies)
            payload["snapshotDigest"] = hashlib.sha256(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            frozen[module_id] = payload

        for module_id in module_ids:
            visit(module_id)
        return frozen

    def _validate_dependencies(
        self, candidate_id: str, dependencies: tuple[str, ...]
    ) -> None:
        modules = {module.id: module for module in self._repository.list_all()}
        graph = {module.id: module.dependencies for module in modules.values()}
        graph[candidate_id] = dependencies
        for dependency in dependencies:
            if dependency not in graph:
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_DEPENDENCY_MISSING",
                    f"自定义模块依赖不存在: {dependency}",
                    422,
                    {"moduleId": candidate_id, "dependencyId": dependency},
                )

        visiting: list[str] = []
        visited: set[str] = set()

        def visit(module_id: str) -> None:
            if module_id in visiting:
                cycle = " -> ".join((*visiting, module_id))
                raise WorkflowDocumentError(
                    "CUSTOM_MODULE_CYCLE",
                    f"检测到自定义模块循环引用: {cycle}",
                    422,
                    {"moduleId": candidate_id},
                )
            if module_id in visited:
                return
            visiting.append(module_id)
            for dependency in graph.get(module_id, ()):
                visit(dependency)
            visiting.pop()
            visited.add(module_id)

        visit(candidate_id)

    @staticmethod
    def _require_request_id(client_request_id: str) -> None:
        if not client_request_id:
            raise WorkflowDocumentError(
                "INVALID_REQUEST_ID", "请求 ID 不能为空", 422
            )
