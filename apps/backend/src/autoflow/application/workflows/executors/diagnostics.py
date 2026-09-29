"""Approved AutoFlow diagnostics; uses the managed browser and existing node result contract."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult


class TraceMarkExecutor(ModuleExecutor):
    module_type = 'trace_mark'

    async def execute(self, config: dict[str, Any], context: ExecutionContext) -> ModuleResult:
        values: dict[str, Any] = {}
        for key in ('diagnosticName', 'description', 'correlation', 'startMarker'):
            value, sensitive = context.resolve_value_with_sensitivity(config.get(key, ''))
            if not isinstance(value, str):
                return ModuleResult(False, error=f'{key}: 必须是文本')
            if len(value) > 4096:
                return ModuleResult(False, error=f'{key}: 超过 4096 字符上限')
            values[key] = '[敏感值]' if sensitive else value
        if not values['diagnosticName'].strip():
            return ModuleResult(False, error='diagnosticName: 诊断名称不能为空')
        for key in ('includeScreenshot', 'includeDom', 'includeConsole'):
            value = config.get(key, True)
            if not isinstance(value, bool):
                return ModuleResult(False, error=f'{key}: 必须是布尔值')
            values[key] = value
        values['target'] = config.get('target', 'page')
        if values['target'] not in {'page', 'frame'}:
            return ModuleResult(False, error='target: 必须是 page 或 frame')
        variable = config.get('variableName', '')
        if not isinstance(variable, str):
            return ModuleResult(False, error='variableName: 必须是变量名称')
        metadata = {'nodeId': context.current_node_id, 'executionId': context.current_execution_id,
                    'executionContext': {'scopes': list(context.execution_scopes), 'loops': list(context.loop_stack)}}
        collect = getattr(context.browser, 'collect_diagnostic', None)
        try:
            if collect is None and self.module_type == 'trace_mark':
                result = {'id': f'mark-{uuid4().hex}', 'kind': 'mark', 'message': values['diagnosticName'],
                          'description': values['description'], 'correlation': values['correlation'],
                          'traceAvailable': False, **metadata}
            elif collect is None:
                return ModuleResult(False, error='TRACE_NOT_AVAILABLE: 当前浏览器不提供诊断采集')
            else:
                result = await collect(self.module_type, values, metadata)
            if variable:
                context.set_variable(variable, result)
            return ModuleResult(True, message=f"已记录诊断：{values['diagnosticName']}", data=result)
        except Exception as error:  # noqa: BLE001 -- explicit nodes use existing error policy, never retry here.
            return ModuleResult(False, error=f'诊断采集失败：{error}')


class CaptureDiagnosticsExecutor(TraceMarkExecutor):
    module_type = 'capture_diagnostics'
    requires_browser = True


class SaveTraceSegmentExecutor(TraceMarkExecutor):
    module_type = 'save_trace_segment'
    requires_browser = True


DIAGNOSTIC_EXECUTORS = (TraceMarkExecutor, CaptureDiagnosticsExecutor, SaveTraceSegmentExecutor)
