from typing import Protocol

from .models import Profile


class ProfileRepository(Protocol):
    def add(self, profile: Profile) -> None: ...
    def get(self, profile_id: str) -> Profile | None: ...
