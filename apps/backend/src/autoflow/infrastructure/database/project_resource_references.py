"""Which saved project facts still name a global resource.

Deleting a Profile, kernel, proxy, pool or model provider is refused while a
project or an automation still names it, because the saved reference would
silently break the next run. Only saved facts are read here: run-time leases
and browser state stay with the existing usage guards.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import ResourceReferenced

from .models import ProfileRow, ProjectRow
from .project_automation_models import ProjectAutomationRow
from .proxy_models import ProxyProjectionRow

# Resource type -> the key that names it, and the proxy selection key it uses.
_PLAIN_KEYS = {"profile": "profileId", "modelProvider": "modelProviderId"}
_PROXY_KEYS = {"proxy": "proxyId", "proxyPool": "proxyPoolId"}


class SqlAlchemyProjectResourceReferences:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def ensure_unreferenced(self, resource_type: str, resource_id: str) -> None:
        """Refuse the delete and name the saved facts that still need it."""
        references = self.references(resource_type, resource_id)
        if references:
            raise ResourceReferenced(resource_type, resource_id, references)

    def ensure_unreferenced_proxy_connection(self, connection_id: str) -> None:
        """Deleting a connection also deletes every proxy it owns."""
        with self._factory() as session:
            proxy_ids = list(
                session.scalars(
                    select(ProxyProjectionRow.proxy_id).where(
                        ProxyProjectionRow.connection_id == connection_id
                    )
                )
            )
        references: list[dict[str, Any]] = []
        for proxy_id in proxy_ids:
            references.extend(self.references("proxy", proxy_id))
        if references:
            raise ResourceReferenced("proxyConnection", connection_id, references)

    def references(self, resource_type: str, resource_id: str) -> list[dict[str, Any]]:
        with self._factory() as session:
            projects = {
                row.id: row
                for row in session.scalars(
                    select(ProjectRow).where(ProjectRow.lifecycle_state != "deleted")
                )
            }
            automations = list(session.scalars(select(ProjectAutomationRow)))
            if resource_type == "kernel":
                return _kernel_references(session, projects, automations, resource_id)
        return _owner_references(projects, automations, resource_type, resource_id)


def _owner_references(
    projects: dict[str, ProjectRow],
    automations: Sequence[ProjectAutomationRow],
    resource_type: str,
    resource_id: str,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for owner in projects.values():
        for path in _fact_paths(
            owner.default_resources or {},
            resource_type,
            resource_id,
            root="defaultResources",
        ):
            found.append(
                {
                    "kind": "project",
                    "projectId": owner.id,
                    "projectName": owner.name,
                    "path": path,
                }
            )
    for automation in automations:
        project = projects.get(automation.project_id)
        if project is None:
            continue
        for path in _fact_paths(
            automation.environment_policy or {},
            resource_type,
            resource_id,
            root="environmentPolicy",
        ):
            found.append(
                {
                    "kind": "automation",
                    "projectId": project.id,
                    "projectName": project.name,
                    "automationId": automation.id,
                    "automationName": automation.name,
                    "path": path,
                }
            )
    return found


def _kernel_references(
    session: Session,
    projects: dict[str, ProjectRow],
    automations: Sequence[ProjectAutomationRow],
    kernel_id: str,
) -> list[dict[str, Any]]:
    """A project only names a kernel through the profile that pins it."""
    found: list[dict[str, Any]] = []
    for profile in session.scalars(select(ProfileRow)):
        spec = profile.spec or {}
        if f"{spec.get('browser_edition')}:{spec.get('browser_version')}" != kernel_id:
            continue
        for owner in _owner_references(projects, automations, "profile", profile.id):
            found.append(
                {
                    **owner,
                    "kind": "profile",
                    "profileId": profile.id,
                    "profileName": profile.name,
                    "usedBy": owner["kind"],
                }
            )
    return found


def _fact_paths(
    facts: dict[str, Any], resource_type: str, resource_id: str, root: str
) -> list[list[str]]:
    """Where inside one saved fact document the resource is named."""
    key = _PLAIN_KEYS.get(resource_type)
    if key is not None:
        return [[root, key]] if facts.get(key) == resource_id else []
    key = _PROXY_KEYS.get(resource_type)
    if key is None:
        return []
    if root == "defaultResources":
        selection, path = facts.get("proxy") or {}, [root, "proxy", key]
    else:
        selection, path = facts.get("proxyOverride") or {}, [root, "proxyOverride", key]
    return [path] if selection.get(key) == resource_id else []
