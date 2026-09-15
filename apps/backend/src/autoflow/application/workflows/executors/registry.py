from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Mapping
from typing import TypeVar

from .base import ModuleExecutor

LOGGER = logging.getLogger(__name__)
ExecutorType = TypeVar("ExecutorType", bound=type[ModuleExecutor])


def _strict_registry_enabled() -> bool:
    return os.environ.get("AUTOFLOW_STRICT_WORKFLOW_REGISTRY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[str, ModuleExecutor] = {}
        self._lazy: dict[str, str] = {}
        self._package: str | None = None
        self._registration_source: dict[str, str] = {}
        self._registration_sources: dict[str, set[str]] = {}

    def register(self, executor_class: type[ModuleExecutor]) -> None:
        executor = executor_class()
        module_type = executor.module_type
        source = getattr(executor_class, "__module__", "") or ""
        previous = self._registration_source.get(module_type)
        if previous is not None and previous != source:
            message = (
                f"重复注册 module_type={module_type!r}：已由 {previous} 注册，"
                f"又被 {source} 注册（后者覆盖前者）"
            )
            if _strict_registry_enabled():
                raise RuntimeError(message)
            LOGGER.warning(message)
        self._executors[module_type] = executor
        self._registration_source[module_type] = source
        self._registration_sources.setdefault(module_type, set()).add(source)
        self._lazy.pop(module_type, None)

    def enable_lazy(self, type_to_submodule: Mapping[str, str], package: str) -> None:
        self._package = package
        for module_type, submodule in type_to_submodule.items():
            if module_type not in self._executors:
                self._lazy[module_type] = submodule

    def _ensure_loaded(self, module_type: str) -> None:
        submodule = self._lazy.get(module_type)
        if not submodule or not self._package:
            return
        try:
            importlib.import_module(f".{submodule}", self._package)
        except Exception:
            LOGGER.exception("懒加载执行器子模块 %s 失败", submodule)
        finally:
            self._lazy.pop(module_type, None)

    def get(self, module_type: str) -> ModuleExecutor | None:
        if module_type in self._executors:
            return self._executors[module_type]
        if module_type in self._lazy:
            self._ensure_loaded(module_type)
        return self._executors.get(module_type)

    def get_all_types(self) -> list[str]:
        result = list(self._executors)
        result.extend(module_type for module_type in self._lazy if module_type not in self._executors)
        return result

    def clear(self) -> None:
        self._executors.clear()
        self._lazy.clear()
        self._registration_source.clear()
        self._registration_sources.clear()
        self._package = None


registry = ExecutorRegistry()


def register_executor(cls: ExecutorType) -> ExecutorType:
    registry.register(cls)
    return cls
