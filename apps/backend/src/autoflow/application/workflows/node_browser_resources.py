"""Freeze node references identically for project tasks and Studio previews."""
from typing import Any

from autoflow.domain.environments.identity import request_from_identity
from autoflow.domain.workflows.runtime import WorkflowRuntimeError


def freeze_node_browser_resources(browser, environments, project_id, nodes, project_defaults, model_provider_id=None) -> dict[str, Any]:
    frozen = {}
    for node_id, declaration in nodes.items():
        source = declaration['source']
        if source == 'current':
            continue
        if source in {'newFromProfile', 'profile'}:
            profile_id = declaration.get('profileId') or (project_defaults.get('profileId') if source == 'newFromProfile' else None)
            if not profile_id:
                raise _node_error(f'nodes.{node_id}.profileId', '请选择浏览器配置')
            proxy = declaration.get('proxy', {'mode': 'sourceDefault' if source == 'profile' else 'projectDefault'})
            if proxy['mode'] == 'projectDefault':
                proxy = project_defaults.get('proxy', {'mode': 'sourceDefault'})
            request = browser.freeze(profile_id, proxy=None if proxy['mode'] == 'sourceDefault' else proxy, kernel=declaration.get('kernel'), model_provider_id=model_provider_id)
            selected_policy = {'source': 'newFromProfile', 'profileId': profile_id}
        elif source == 'inputEnvironment':
            frozen[node_id] = {'environmentResolution': 'atTaskStart', 'environmentPolicy': dict(declaration)}
            continue
        else:
            if environments is None:
                raise _node_error(f'nodes.{node_id}.environmentId', '环境服务尚未就绪')
            selected = environments.resolve(project_id, declaration)
            request = {**request_from_identity(selected.identity_package), 'identityPackage': selected.identity_package, 'environmentRef': selected.environment_ref.to_dict()}
            selected_policy = dict(declaration)
        frozen[node_id] = {**request, 'environmentPolicy': selected_policy}
    return frozen


def _node_error(field, message):
    return WorkflowRuntimeError('WORKFLOW_RESOURCE_INVALID', message, 422, {'field': field})
