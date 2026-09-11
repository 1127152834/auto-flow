from collections.abc import Callable, Iterator
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from platform import python_version
from sqlite3 import sqlite_version
from threading import RLock
from typing import Protocol

from autoflow.domain.settings.models import DashboardSnapshot, RuntimeSnapshot


class RuntimeRepository(Protocol):
    def dashboard(self, installed_kernels: int) -> DashboardSnapshot: ...
    def blockers(self) -> list[str]: ...


class QuiesceGate:
    def __init__(self) -> None:
        self._lock = RLock()
        self._paused = False
        self._active_mutations = 0

    @contextmanager
    def mutation(self) -> Iterator[bool]:
        with self._lock:
            admitted = not self._paused
            if admitted:
                self._active_mutations += 1
        try:
            yield admitted
        finally:
            if admitted:
                with self._lock:
                    self._active_mutations -= 1

    def pause(self, external_blockers: Callable[[], list[str]]) -> list[str]:
        with self._lock:
            blockers = external_blockers()
            if self._active_mutations:
                blockers.append("api_mutation_in_progress")
            if not blockers:
                self._paused = True
            return sorted(set(blockers))

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def blockers(self) -> list[str]:
        with self._lock:
            blockers = []
            if self._active_mutations:
                blockers.append("api_mutation_in_progress")
            if self._paused:
                blockers.append("api_mutations_paused")
            return blockers


class SettingsRuntimeService:
    def __init__(
        self,
        repository: RuntimeRepository,
        paths: dict[str, str],
        api_version: str,
        installed_kernel_count: Callable[[], int],
        process_blockers: Callable[[], list[str]],
        gate: QuiesceGate,
    ) -> None:
        self._repository = repository
        self._paths = paths
        self._api_version = api_version
        self._installed_kernel_count = installed_kernel_count
        self._process_blockers = process_blockers
        self.gate = gate

    def dashboard(self) -> DashboardSnapshot:
        return self._repository.dashboard(self._installed_kernel_count())

    def blockers(self) -> list[str]:
        return sorted(set(self._repository.blockers() + self._process_blockers() + self.gate.blockers()))

    def runtime(self) -> RuntimeSnapshot:
        try:
            backend_version = version("autoflow-backend")
        except PackageNotFoundError:
            backend_version = "unavailable"
        return RuntimeSnapshot(
            api_version=self._api_version,
            backend_version=backend_version,
            python_version=python_version(),
            sqlite_version=sqlite_version,
            paths=self._paths,
            blockers=tuple(self.blockers()),
        )

    def quiesce(self) -> list[str]:
        return self.gate.pause(lambda: self._repository.blockers() + self._process_blockers())

    def resume(self) -> None:
        self.gate.resume()
