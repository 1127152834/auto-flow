from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.profiles.errors import ProfileNameConflict
from autoflow.domain.profiles.models import Profile, ProfileSpec
from autoflow.domain.profiles.ports import ProfileRepository

from .models import ProfileRow


class SqlAlchemyProfileRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, profile: Profile) -> None:
        self.session.add(ProfileRow(id=profile.id, name=profile.spec.name, spec=asdict(profile.spec),
                                    fingerprint_seed=profile.fingerprint_seed, created_at=profile.created_at, updated_at=profile.updated_at))

    def get(self, profile_id: str) -> Profile | None:
        row = self.session.get(ProfileRow, profile_id)
        if row is None:
            return None
        return self._to_profile(row)

    def get_by_name(self, name: str) -> Profile | None:
        row = self.session.scalar(select(ProfileRow).where(ProfileRow.name == name))
        return self.get(row.id) if row else None

    def list(self) -> list[Profile]:
        rows = self.session.scalars(select(ProfileRow).order_by(ProfileRow.created_at.desc())).all()
        return [self._to_profile(row) for row in rows]

    def update(self, profile: Profile) -> None:
        row = self.session.get(ProfileRow, profile.id)
        if row is None:
            return
        row.name = profile.spec.name
        row.spec = asdict(profile.spec)
        row.fingerprint_seed = profile.fingerprint_seed
        row.updated_at = profile.updated_at

    def remove(self, profile_id: str) -> None:
        row = self.session.get(ProfileRow, profile_id)
        if row is not None:
            self.session.delete(row)

    @staticmethod
    def _to_profile(row: ProfileRow) -> Profile:
        created_at = row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
        updated_at = row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at
        return Profile(row.id, ProfileSpec.from_values(row.spec), row.fingerprint_seed, created_at, updated_at)


@contextmanager
def profile_repository_transaction(
    session_factory: sessionmaker[Session],
) -> Iterator[ProfileRepository]:
    try:
        with session_factory.begin() as session:
            yield SqlAlchemyProfileRepository(session)
    except IntegrityError as error:
        raise ProfileNameConflict from error
