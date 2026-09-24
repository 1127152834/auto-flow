"""Versioned node browser declarations contain resource references, never paths or secrets."""
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .models import WorkflowError, WorkflowIssue


def node_browser_environments(document: Mapping[str, Any]) -> dict[str, dict[str, Any]] | None:
    content = document.get('content', document)
    version = content.get('browserEnvironmentVersion')
    enabled = type(version) is int and version == 1
    issues: list[WorkflowIssue] = []
    if 'browserEnvironmentVersion' in content and not enabled:
        issues.append(WorkflowIssue(None, ['browserEnvironmentVersion'], 'BROWSER_ENVIRONMENT_VERSION_UNSUPPORTED', '浏览器节点配置版本不支持'))
    if enabled and content.get("schemaVersion") != 3:
        issues.append(WorkflowIssue(None, ["schemaVersion"], "BROWSER_ENVIRONMENT_VERSION_UNSUPPORTED", "节点浏览器配置需要 Studio 图执行版本"))
    result = {}
    for index, node in enumerate(content.get('nodes', ())):
        data = node.get('data', {})
        config = data.get('config', data)
        value = config.get('browserEnvironment')
        if data.get('moduleType') != 'open_page':
            if value is not None:
                issues.append(WorkflowIssue(node['id'], ['nodes', str(index), 'browserEnvironment'], 'BROWSER_ENVIRONMENT_INVALID', '只有打开网页节点可以声明浏览器环境'))
            continue
        if not enabled and value is None:
            continue
        if not enabled or not _valid(value):
            issues.append(WorkflowIssue(node['id'], ['nodes', str(index), 'browserEnvironment'], 'BROWSER_ENVIRONMENT_INVALID', '请选择合法环境来源及其适用配置，并明确启用节点浏览器版本'))
        else:
            result[node['id']] = deepcopy(value)
    if enabled and result and any('parallel' in node.get('data', {}).get('config', node.get('data', {})) for node in content.get('nodes', ())):
        issues.append(WorkflowIssue(None, ['nodes'], 'BROWSER_PARALLEL_UNSUPPORTED', '节点浏览器模式尚不支持并行分支共享实例，请改为顺序执行'))
    if issues:
        raise WorkflowError('WORKFLOW_NOT_RUNNABLE', '浏览器节点配置无效', 422, issues)
    return result if enabled else None


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and '{{' not in value


def _valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    source = value.get('source')
    if source == 'current':
        return set(value) == {'source'}
    if source == 'fixedEnvironment':
        return set(value) == {'source', 'environmentId'} and _text(value['environmentId'])
    if source == 'inputEnvironment':
        return set(value) == {'source', 'inputId'} and _text(value['inputId'])
    if source != 'newFromProfile' or set(value) - {'source', 'profileId', 'proxy', 'kernel'}:
        return False
    if value.get('profileId') is not None and not _text(value['profileId']):
        return False
    proxy = value.get('proxy', {'mode': 'projectDefault'})
    if not isinstance(proxy, dict):
        return False
    mode = proxy.get('mode')
    allowed = {'projectDefault': {'mode'}, 'sourceDefault': {'mode'}, 'none': {'mode'}, 'fixed': {'mode', 'proxyId'}, 'pool': {'mode', 'proxyPoolId'}}
    if not isinstance(mode, str) or set(proxy) != allowed.get(mode):
        return False
    if any(not _text(proxy[key]) for key in set(proxy) - {'mode'}):
        return False
    kernel = value.get('kernel')
    return kernel is None or (isinstance(kernel, dict) and set(kernel) == {'edition', 'version'} and kernel['edition'] in ('public', 'licensed') and _text(kernel['version']))
