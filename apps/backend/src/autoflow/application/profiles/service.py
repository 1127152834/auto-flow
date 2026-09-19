import logging
import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

from autoflow.domain.profiles.errors import (
    KernelNotInstalled,
    ProfileDataPathInvalid,
    ProfileNotFound,
    ProxyUnavailable,
)
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.profiles.ports import (
    InstalledKernelLookup,
    ProfileDataStore,
    ProfileRepository,
    ProfileUsageGuard,
    ProxyOptionsLookup,
)
from autoflow.domain.projects.ports import ProjectResourceReferences

RepositoryTransaction = Callable[[], AbstractContextManager[ProfileRepository]]
logger = logging.getLogger(__name__)


def new_seed(previous: int | None = None) -> int:
    seed = secrets.randbelow(90000) + 10000
    while seed == previous:
        seed = secrets.randbelow(90000) + 10000
    return seed


class ProfileService:
    def __init__(
        self,
        transaction: RepositoryTransaction,
        installed_kernels: InstalledKernelLookup,
        proxy_options: ProxyOptionsLookup,
        profile_usage: ProfileUsageGuard,
        data_store: ProfileDataStore,
        references: ProjectResourceReferences | None = None,
    ) -> None:
        self.transaction = transaction
        self.installed_kernels = installed_kernels
        self.proxy_options = proxy_options
        self.profile_usage = profile_usage
        self.data_store = data_store
        self.references = references

    def list(self) -> list[Profile]:
        with self.transaction() as repository:
            return repository.list()

    def get(self, profile_id: str) -> Profile:
        with self.transaction() as repository:
            return self._require(repository, profile_id)

    def create(self, spec: ProfileSpec) -> Profile:
        self._validate_resources(spec)
        now = datetime.now(UTC)
        profile = Profile(str(uuid4()), spec, new_seed(), now, now)
        with self.transaction() as repository:
            repository.add(profile)
        return profile

    def update(self, profile_id: str, spec: ProfileSpec) -> Profile:
        with self.transaction() as repository:
            current = self._require(repository, profile_id)
            self._validate_resources(spec)
            updated = replace(current, spec=spec, updated_at=datetime.now(UTC))
            repository.update(updated)
        return updated

    def duplicate(self, profile_id: str, name: str) -> Profile:
        with self.transaction() as repository:
            source = self._require(repository, profile_id)
            spec = ProfileSpec.from_values({**asdict(source.spec), "name": name})
            self._validate_resources(spec)
            now = datetime.now(UTC)
            copied = Profile(str(uuid4()), spec, new_seed(source.fingerprint_seed), now, now)
            repository.add(copied)
        return copied

    def regenerate(self, profile_id: str) -> Profile:
        with self.transaction() as repository:
            current = self._require(repository, profile_id)
            updated = replace(
                current,
                fingerprint_seed=new_seed(current.fingerprint_seed),
                updated_at=datetime.now(UTC),
            )
            repository.update(updated)
        return updated

    def remove(self, profile_id: str) -> None:
        with self.profile_usage.guard(profile_id):
            staged: str | None = None
            try:
                with self.transaction() as repository:
                    self._require(repository, profile_id)
                    if self.references is not None:
                        self.references.ensure_unreferenced("profile", profile_id)
                    staged = self.data_store.stage(profile_id)
                    repository.remove(profile_id)
            except Exception:
                if staged is not None:
                    self.data_store.restore(profile_id, staged)
                raise
            if staged is not None:
                try:
                    self.data_store.purge(staged)
                except (OSError, ProfileDataPathInvalid):
                    logger.warning("profile data cleanup remains pending for profile_id=%s", profile_id)

    @staticmethod
    def _require(repository: ProfileRepository, profile_id: str) -> Profile:
        profile = repository.get(profile_id)
        if profile is None:
            raise ProfileNotFound
        return profile

    def _validate_resources(self, spec: ProfileSpec) -> None:
        if not self.installed_kernels.is_installed(spec.browser_edition, spec.browser_version):
            raise KernelNotInstalled
        if spec.proxy_mode == "proxy" and (
            spec.proxy_id is None or not self.proxy_options.proxy_is_available(spec.proxy_id)
        ):
            raise ProxyUnavailable
        if spec.proxy_mode == "pool" and (
            spec.proxy_pool_id is None or not self.proxy_options.pool_exists(spec.proxy_pool_id)
        ):
            raise ProxyUnavailable
