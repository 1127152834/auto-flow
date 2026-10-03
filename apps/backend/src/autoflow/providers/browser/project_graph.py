"""Adapt the shared graph scheduler to the durable project event contract."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from itertools import pairwise
from time import monotonic
from typing import Any

from autoflow.application.workflows.config_schema import (
    describe_unknown_keys,
    unknown_config_keys,
)
from autoflow.application.workflows.event_translation import node_failure_message
from autoflow.application.workflows.executors.base import ModuleExecutor, ModuleResult
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import (
    WorkflowRuntime,
    execution_context_snapshot,
)
from autoflow.domain.workflows.error_semantics import document_error_semantics
from autoflow.domain.workflows.execution import (
    ArtifactWriter,
    ExecutionContext,
    ExternalIntegrationGateway,
)
from autoflow.domain.workflows.inert_settings import describe_inert_keys, inert_keys
from autoflow.domain.workflows.project_end import normalize_project_end
from autoflow.domain.workflows.side_effects import node_side_effect
from autoflow.domain.workflows.signature import (
    document_signature,
    parse_signature,
    sensitive_references,
)
from autoflow.domain.workflows.variables import CredentialReader, references_variable
from autoflow.infrastructure.filesystem.workflow_table_workbook import (
    OpenpyxlTableWorkbookRenderer,
)
from autoflow.infrastructure.process.workflow_subprocess import terminate_subprocess
from autoflow.providers.model import WorkflowModelGateway

from .workflow_session import CloakBrowserWorkflowSession
from .workflow_worker import (
    _CredentialDeadlineExceeded,
    _WorkerCanvasSubflows,
    _WorkerCommandBus,
    _WorkerCredentialReader,
    _WorkerCustomModules,
    _WorkerNestedWorkflows,
)

_visit: ContextVar[tuple[str, str]] = ContextVar('project_node_visit')


class _ProjectDataNode(ModuleExecutor):
    module_type = 'project_data'

    def __init__(self, request: Callable[..., Awaitable[Any]]) -> None:
        self.request = request

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        node_id, visit = _visit.get()
        reply = await self.request(node_id, visit, config['operation'], context.resolve_value(config.get('arguments', {}), preserve_types=True))
        if 'error' in reply:
            return ModuleResult(False, error=reply['error']['code'], data={'projectErrorCode': reply['error']['code']})
        value = reply['result']
        if name := config.get('variableName'):
            context.set_variable(name, value)
        return ModuleResult(True, data=value)


class _ProjectEndNode(ModuleExecutor):
    module_type = 'project_end'

    def __init__(self, request: Callable[..., Awaitable[Any]]) -> None:
        self.request = request

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        node_id, visit = _visit.get()
        try:
            frozen = normalize_project_end(config)
            targets = context.resolve_value(
                frozen.get('recordTargets', []), preserve_types=True
            )
            if not isinstance(targets, list) or len(targets) > 100:
                raise ValueError('End 记录目标必须是最多100项的列表')
        except (TypeError, ValueError) as error:
            return ModuleResult(False, error=str(error))
        arguments = {'recordTargets': targets}
        if references_variable(frozen.get('name', '保留环境')):
            arguments['name'] = context.resolve_value(frozen['name'], preserve_types=True)
        reply = await self.request(node_id, visit, 'end', arguments)
        if 'error' in reply:
            return ModuleResult(False, error=reply['error']['code'], data={'projectErrorCode': reply['error']['code']})
        value = reply['result']
        if not isinstance(value, dict) or not isinstance(value.get('endOperationId'), str):
            return ModuleResult(False, error='ENVIRONMENT_END_INCOMPLETE')
        context.project_end.accepted = True
        return ModuleResult(True, data=value)


class _ProjectManualNode(ModuleExecutor):
    module_type = 'project_manual'

    def __init__(self, request: Callable[..., Awaitable[Any]]) -> None:
        self.request = request

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        node_id, visit = _visit.get()
        reply = await self.request(node_id, visit, 'manual', {
            'reason': context.resolve_value(config.get('reason', '等待人工处理')),
            'timeoutSeconds': config.get('timeoutSeconds', 1800),
            'availableVariables': sorted(context.variables),
        })
        if 'error' in reply:
            return ModuleResult(False, error=reply['error']['code'], data={'projectErrorCode': reply['error']['code']})
        result = reply['result']
        if result['action'] == 'resume':
            if name := config.get('variableName'):
                context.set_variable(name, result.get('inputs', {}))
            declared = {field['name'] for field in config.get('inputSchema', [])}
            for name, value in result.get('inputs', {}).items():
                if name in declared:
                    context.set_variable(name, value)
            return ModuleResult(True, data=result.get('inputs', {}), target_node_id=result.get('targetNodeId'))
        context.stop_workflow = True
        return ModuleResult(result.get('complete') is True and result.get('outcome') == 'succeeded', data=result, error='MANUAL_FINISHED')


class _Cancellation:
    def __init__(self, stopped: Callable[[], bool]) -> None:
        self.stopped = stopped

    @property
    def cancelled(self) -> bool:
        return self.stopped()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError


class _TimedNode(ModuleExecutor):
    def __init__(self, executor: ModuleExecutor) -> None:
        self.executor = executor

    @property
    def module_type(self) -> str:
        return self.executor.module_type

    def requires_browser_for(self, config: dict[str, Any]) -> bool:
        return self.executor.requires_browser_for(config)

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        # Preserve the project's whole-node timeout, including fractional seconds.
        timeout = config.get('timeout', 0)
        reader = context.credentials
        deadline_token = reader.deadline.set(monotonic() + timeout if timeout else None) if isinstance(reader, _WorkerCredentialReader) else None
        try:
            async with asyncio.timeout(timeout or None):
                return await self.executor.execute(config, context)
        except (TimeoutError, _CredentialDeadlineExceeded):
            # R1-03: the reason names the whole-node limit; the code stays WORKFLOW_NODE_TIMEOUT.
            return ModuleResult(False, error=f'节点在 {timeout:g} 秒内未完成', is_timeout=True)
        finally:
            if isinstance(reader, _WorkerCredentialReader) and deadline_token is not None:
                reader.deadline.reset(deadline_token)


class _ProjectRegistry(ExecutorRegistry):
    def __init__(self, capability: Callable[..., Awaitable[Any]] | None) -> None:
        super().__init__()
        self.source = build_production_executor_registry()
        self.capability = capability

    def get_all_types(self) -> list[str]:
        return [*self.source.get_all_types(), *(['project_data', 'project_end', 'project_manual'] if self.capability else [])]

    def get(self, module_type: str) -> ModuleExecutor | None:
        executor: ModuleExecutor | None
        if module_type == 'project_manual' and self.capability is not None:
            executor = _ProjectManualNode(self.capability)
        elif module_type == 'project_end' and self.capability is not None:
            executor = _ProjectEndNode(self.capability)
        elif module_type == 'project_data' and self.capability is not None:
            executor = _ProjectDataNode(self.capability)
        else:
            executor = self.source.get(module_type)
        return _TimedNode(executor) if executor is not None else None


class _ProjectEventSink:
    def __init__(self, owner: ProjectGraphExecutor, context: ExecutionContext) -> None:
        self.owner, self.context = owner, context

    def for_context(self, context: ExecutionContext) -> _ProjectEventSink:
        return _ProjectEventSink(self.owner, context)

    async def publish(self, event: Mapping[str, Any]) -> None:
        await self.owner.publish(event, context=self.context)


class ProjectGraphExecutor:
    def __init__(
        self, browser_context: Any, variables: Mapping[str, Any],
        emit: Callable[[str, str, str, dict[str, object]], Awaitable[None]],
        should_stop: Callable[[], bool],
        capture_failure: Callable[[Any, str, str], Awaitable[dict[str, object]]] | None = None,
        artifact_writer: Callable[[str, str, str], ArtifactWriter] | None = None,
        *, credentials: CredentialReader | None = None,
        models: WorkflowModelGateway | None = None,
        external_integrations: ExternalIntegrationGateway | None = None,
        command_bus: _WorkerCommandBus | None = None,
        proxy_probe: Callable[[bool], Awaitable[dict[str, Any]]] | None = None,
        capability: Callable[..., Awaitable[Any]] | None = None,
        browser_initializer: Callable[..., Awaitable[Any]] | None = None,
        project_input_context: dict[str, Any] | None = None,
    ) -> None:
        self.browser = CloakBrowserWorkflowSession(browser_context) if browser_context is not None else None
        self.cancellation = _Cancellation(should_stop)
        self.context = ExecutionContext(project_input_context=project_input_context or {}, proxy_control=command_bus.proxy_call if command_bus else None, proxy_probe=proxy_probe, process_cleanup=terminate_subprocess, variables=dict(variables), browser=self.browser, browser_initializer=browser_initializer, cancellation=self.cancellation, events=self, credentials=credentials, models=models, external_integrations=external_integrations, table_workbooks=OpenpyxlTableWorkbookRenderer())
        self.command_bus = command_bus
        if command_bus is not None:
            interactive = command_bus.for_context(self.context)
            self.context.input_prompts = interactive
            self.context.browser_scripts = interactive
            self.context.webhook_triggers = interactive
        self.emit = emit
        self.capture_failure = capture_failure
        self.capability = capability
        self.artifact_writer = artifact_writer
        self.graph_adapter = False
        self.nodes: dict[str, Any] = {}
        self.module_nodes: dict[str, dict[str, Any]] = {}
        self.workflow_nodes: dict[str, dict[str, Any]] = {}
        self.started: dict[str, float] = {}
        self.error: dict[str, str] | None = None
        self.end_completed = False
        self.manual_outcome: str | None = None
        self.inert_reported: set[str] = set()
        self.unknown_reported: set[str] = set()

    async def run(self, plan: Mapping[str, Any]) -> dict[str, object]:
        document = plan.get('document')
        self.graph_adapter = isinstance(document, dict)
        if not isinstance(document, dict):
            # Previously frozen chain/v1 content remains executable without a migration.
            identities = plan['orderedNodeIds']
            document = {
                'nodes': [{'id': node['nodeId'], 'data': {**node['data'], 'moduleType': node['moduleType']}} for node in plan['nodes']],
                'edges': [{'id': f'edge-{index}', 'source': source, 'target': target} for index, (source, target) in enumerate(pairwise(identities))],
            }
        self.nodes = {node['id']: node['data'] for node in document['nodes']}
        signature, _ = parse_signature(document_signature(document))
        if signature is not None:
            # Remediation M2 R2-21: the signature decides which input values stay masked.
            record_group = self.context.project_input_context.get('$recordInput')
            self.context.sensitive_variables |= sensitive_references(signature, record_group if isinstance(record_group, str) else None)
        registry = _ProjectRegistry(self.capability)
        workflows = plan.get('workflowDependencies')
        nested = _WorkerNestedWorkflows(
            workflows, registry=registry, parent=self.context, sink=self,  # type: ignore[arg-type]
            command_bus=self.command_bus,
        )
        self.context.nested_workflows = nested
        if isinstance(workflows, Mapping):
            self.workflow_nodes = {
                str(snapshot.get('id') or reference): {
                    node['id']: node['data'] for node in snapshot.get('nodes', ())
                    if isinstance(node, dict) and isinstance(node.get('data'), dict)
                }
                for reference, snapshot in workflows.items() if isinstance(snapshot, dict)
            }
        modules = plan.get('customModuleDependencies')
        if isinstance(modules, Mapping):
            self.module_nodes = {
                str(module_id): {
                    node['id']: node['data'] for node in snapshot['workflow']['nodes']
                    if isinstance(node, dict) and isinstance(node.get('data'), dict)
                }
                for module_id, snapshot in modules.items()
                if isinstance(snapshot, dict) and isinstance(snapshot.get('workflow'), dict)
                and isinstance(snapshot['workflow'].get('nodes'), list)
            }
            self.context.custom_modules = _WorkerCustomModules(
                modules, registry=registry, parent=self.context, sink=self,  # type: ignore[arg-type]
                command_bus=self.command_bus, nested_workflows=nested,
            )
            nested.custom_modules = self.context.custom_modules
        # Read the rule before canvas subflows rewrite the document, then pass it explicitly.
        semantics = document_error_semantics(document)
        if self.graph_adapter:
            canvas_subflows = _WorkerCanvasSubflows(
                document, registry=registry, parent=self.context, sink=self,
                command_bus=self.command_bus, nested_workflows=nested,
            )
            self.context.canvas_subflows = canvas_subflows
            document = canvas_subflows.top_level_document()
        result = await WorkflowRuntime(registry).execute(document, self.context, error_semantics=semantics)
        await nested.drain()
        if result.success:
            # A child may fail while run_workflow_file explicitly continues.
            self.error = None
        if result.success and not self.context.stop_workflow and any(node.get('moduleType') == 'project_end' for node in self.nodes.values()) and not self.end_completed:
            return {'status': 'failed', 'error': {'code': 'WORKFLOW_END_NOT_REACHED', 'message': '执行分支未到达 End，环境收尾未完成'}}
        if not result.success and self.error is None:
            issue = result.issues[0] if result.issues else None
            # Remediation rule 2: keep the preflight's own reason instead of a generic headline.
            self.error = (
                {'code': issue.code, 'message': issue.message, 'nodeId': issue.node_id}
                if issue is not None and issue.code == 'NODE_OUTPUT_REFERENCE_INVALID'
                else {'code': 'WORKFLOW_NODE_INVALID', 'message': f'工作流包含不可执行的节点：{issue.message}' if issue is not None and issue.message else '工作流包含不可执行的节点'}
            )
        return {'status': self.manual_outcome or ('succeeded' if result.success else 'failed'), 'error': self.error}

    def for_context(self, context: ExecutionContext) -> _ProjectEventSink:
        return _ProjectEventSink(self, context)

    async def publish(self, event: Mapping[str, Any], *, context: ExecutionContext | None = None) -> None:
        if event['type'] in {'subflow:started', 'subflow:completed'}:
            return
        current = context or self.context
        node_id, visit = event['nodeId'], event['executionId']
        execution_context = execution_context_snapshot(current)

        async def emit(kind: str, payload: dict[str, object]) -> None:
            if execution_context['scopes'] or execution_context['loops']:
                payload = {**payload, 'executionContext': execution_context}
            await self.emit(kind, node_id, visit, payload)

        if event['type'] == 'execution:log':
            await emit('log', {'level': event.get('level', 'info'), 'message': event.get('message', '')})
            return
        if event['type'] in {
            'execution:input_prompt', 'execution:input_prompt_closed',
            'execution:js_script', 'execution:js_script_closed',
            'execution:webhook_waiting', 'execution:webhook_closed',
        }:
            await emit('interaction', dict(event))
            return

        node_data = None
        for scope in reversed(current.execution_scopes):
            collection = self.module_nodes if scope.get('kind') == 'customModule' else self.workflow_nodes
            node_data = collection.get(str(scope.get('id')), {}).get(node_id)
            if node_data is not None:
                break
        if node_data is None:
            node_data = self.nodes[node_id]
        if event['type'] == 'execution:node_start':
            _visit.set((node_id, visit))
            self.started[visit] = monotonic()
            module_type = node_data.get("moduleType")
            if self.artifact_writer is not None and module_type in {"screenshot", "download_file", "save_image", "list_export", "export_log", "table_export", "extract_table_data", "allure_generate_report", "ssh_connect", "ssh_upload_file", "ssh_download_file", "base64", "firecrawl_scrape", "face_recognition", "image_ocr"}:
                current.artifacts = self.artifact_writer(node_id, visit, module_type)
            # R2-10: the acknowledged start fact carries whether the node may act outside the run.
            await emit('nodeAttempt', {'status': 'started', 'executionContext': execution_context, 'sideEffect': node_side_effect(module_type, node_data)})
            self.cancellation.raise_if_cancelled()
            await emit('log', {'level': 'info', 'message': '开始执行节点'})
            inert = inert_keys(node_data, str(module_type or '')) if node_id not in self.inert_reported else []
            if inert:
                # Spec M1 R1-02: say once per node that saved retry / timeout settings are ignored.
                self.inert_reported.add(node_id)
                await emit('log', {'level': 'warning', 'message': describe_inert_keys(str(node_data.get('label') or module_type or node_id), inert)})
            unknown = unknown_config_keys(node_data, str(module_type or '')) if node_id not in self.unknown_reported else []
            if unknown:
                # Spec M2 R2-11: settings no part of this node reads are reported once, never silently kept.
                self.unknown_reported.add(node_id)
                await emit('log', {'level': 'warning', 'message': describe_unknown_keys(str(node_data.get('label') or module_type or node_id), unknown)})
            self.cancellation.raise_if_cancelled()
            return
        if event['type'] != 'execution:node_complete':
            return
        duration = round((monotonic() - self.started.pop(visit)) * 1000)
        success = bool(event['success'])
        if node_data.get('moduleType') == 'project_manual' and isinstance(event.get('data'), dict) and event['data'].get('action') == 'finish':
            self.manual_outcome = event['data'].get('outcome') if event['data'].get('complete') else 'failed'
        level = event.get('logLevel') or ('info' if success else 'error')
        if level not in {'debug', 'info', 'success', 'warning', 'error'}:
            level = 'info' if success else 'error'
        message = str(event.get('message') or event.get('error') or '')
        current.log_records.append({
            'timestamp': current.clock.now().isoformat(), 'level': level,
            'message': message, 'duration': event.get('duration') or 0,
            'nodeId': node_id,
        })
        payload: dict[str, object] = {'status': 'succeeded' if success else 'failed', 'durationMs': duration}
        if success:
            data = node_data
            if data.get('moduleType') == 'project_end':
                self.end_completed = True
            config = data.get('config', data)
            if data['moduleType'] == 'switch_tab':
                for key in ('saveIndexVariable', 'saveTitleVariable', 'saveUrlVariable'):
                    output_name = config.get(key)
                    if isinstance(output_name, str) and output_name and output_name in current.variables and output_name not in current.sensitive_variables:
                        await emit('output', {'name': output_name, 'value': current.variables[output_name]})
            if data['moduleType'] == 'webhook_request':
                for enabled, key, default in (
                    ('saveResponse', 'responseVariable', 'webhook_response'),
                    ('saveStatus', 'statusVariable', 'webhook_status'),
                    ('saveHeaders', 'headersVariable', 'webhook_headers'),
                    ('saveCookies', 'cookiesVariable', 'webhook_cookies'),
                ):
                    if config.get(enabled):
                        output_name = config.get(key) or default
                        if isinstance(output_name, str) and output_name in current.variables and output_name not in current.sensitive_variables:
                            await emit('output', {'name': output_name, 'value': current.variables[output_name]})
            if data['moduleType'] in {'ssh_execute_command', 'python_script'}:
                fields = (
                    ('outputVariable', 'ssh_output'),
                    ('errorVariable', 'ssh_error'),
                    ('exitCodeVariable', 'ssh_exit_code'),
                ) if data['moduleType'] == 'ssh_execute_command' else (
                    ('stdoutVariable', ''), ('stderrVariable', ''), ('returnCodeVariable', ''),
                )
                for key, default in fields:
                    output_name = config.get(key) or default
                    if isinstance(output_name, str) and output_name in current.variables and output_name not in current.sensitive_variables:
                        await emit('output', {'name': output_name, 'value': current.variables[output_name]})
            if data['moduleType'] == 'element_change_trigger':
                for key, default in (
                    ('saveNewElementSelector', 'new_element_selector'),
                    ('saveChangeInfo', 'element_change_info'),
                ):
                    # This executor treats an explicit empty field as disabled.
                    output_name = config.get(key, default)
                    if isinstance(output_name, str) and output_name and output_name in current.variables and output_name not in current.sensitive_variables:
                        await emit('output', {'name': output_name, 'value': current.variables[output_name]})
            name = (config.get('resultVariable') or config.get('variableName')
                    or config.get('saveResult') or config.get('saveMessage'))
            if data['moduleType'] in {'json_parse', 'base64', 'run_command', 'table_get_cell', 'table_export', 'extract_table_data', 'api_request', 'network_capture'}:
                name = config.get('variableName')
            if data['moduleType'] == 'webhook_trigger':
                name = str(config.get('saveToVariable', 'webhook_data'))
            if data['moduleType'] == 'api_trigger':
                name = config.get('saveToVariable', 'api_request')
            if data['moduleType'] == 'file_watcher_trigger':
                name = config.get('saveToVariable', 'file_event')
            if data['moduleType'] == 'webhook_request':
                name = None
            if data['moduleType'] == 'page_load_complete':
                name = config.get('saveToVariable', 'page_loaded')
            if data['moduleType'] in {'face_recognition', 'image_ocr'}:
                default = 'face_match_result' if data['moduleType'] == 'face_recognition' else 'ocr_text'
                name = str(config.get('resultVariable', default))
            if data['moduleType'] == 'ocr_captcha':
                name = str(config.get('variableName') or config.get('resultVariable') or '').strip()
            if isinstance(name, str) and name and name not in current.sensitive_variables:
                if data['moduleType'] in {'run_command', 'python_script', 'inject_javascript', 'handle_dialog', 'page_load_complete', 'random_number', 'get_time', 'input_prompt', 'js_script', 'table_export', 'extract_table_data', 'api_request', 'api_trigger', 'assert_checkpoint', 'network_capture', 'network_monitor_wait', 'network_monitor_stop', 'ocr_captcha', 'face_recognition', 'image_ocr', 'webhook_trigger'}:
                    if name in current.variables:
                        await emit('output', {'name': name, 'value': current.variables[name]})
                elif event.get('data') is not None or (
                    data['moduleType'] == 'dict_get_path' and name in current.variables
                ):
                    await emit('output', {'name': name, 'value': event['data']})
            visible_message = message[:1000] + '…' if len(message.encode('utf-8')) > 4096 else message
            await emit('log', {'level': level, 'message': visible_message if event.get('isUserLog') else '节点执行完成', 'isUserLog': event.get('isUserLog') is True})
        else:
            timeout = event.get('isTimeout') is True or event.get('error') == 'WORKFLOW_NODE_TIMEOUT'
            message = node_failure_message(event.get('error') or event.get('message'), timeout=timeout)
            self.error = {'code': 'WORKFLOW_NODE_TIMEOUT' if timeout else 'WORKFLOW_NODE_FAILED', 'message': message}
            details = event.get('data')
            if isinstance(details, dict) and isinstance(details.get('projectErrorCode'), str):
                self.error = {**self.error, 'code': details['projectErrorCode']}
            payload['error'] = self.error
            await emit('log', {'level': 'error', 'message': self.error['message']})
        await emit('nodeAttempt', payload)
        if not success and self.capture_failure is not None:
            try:
                page = getattr(current.browser.current_page(), '_raw', None) if current.browser is not None else None
            except Exception:  # noqa: BLE001 -- absence of a page is valid failure evidence.
                page = None
            await emit('artifact', await self.capture_failure(page, node_id, visit))
