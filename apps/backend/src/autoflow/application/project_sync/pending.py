"""Shared placeholder for PM6 endpoints whose owning package has not landed yet."""

from autoflow.domain.projects.models import ProjectError


def pending(capability: str) -> ProjectError:
    return ProjectError(
        "SYNC_NOT_IMPLEMENTED",
        "This synchronization capability is not implemented yet",
        501,
        {"capability": capability, "domainCode": "sync_not_implemented"},
    )
