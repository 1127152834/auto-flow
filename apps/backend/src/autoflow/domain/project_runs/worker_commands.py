"""Stable identities for one capability command per committed node visit."""
from uuid import UUID, uuid5


def project_command_id(run_id: str, generation: int, visit_id: str) -> str:
    return str(uuid5(UUID(run_id), f'project-node:{generation}:{visit_id}:1'))
