from dataclasses import asdict
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from autoflow.domain.profiles.models import Profile, ProfileSpec

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
        spec = ProfileSpec.from_values(row.spec)
        return Profile(row.id, spec, row.fingerprint_seed, row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
                       row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at)

    def get_by_name(self, name: str) -> Profile | None:
        row = self.session.scalar(select(ProfileRow).where(ProfileRow.name == name))
        return self.get(row.id) if row else None
