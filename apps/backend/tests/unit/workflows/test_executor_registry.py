from __future__ import annotations

import json
from typing import Any

import pytest

from autoflow.application.workflows.executors.base import (
    ModuleExecutor,
    ModuleResult,
)
from autoflow.application.workflows.executors.production import (
    build_production_executor_registry,
)
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.domain.workflows.scope import WorkflowScopeIssue


def _executor(name: str, source: str, calls: list[str]) -> type[ModuleExecutor]:
    async def execute(
        self: ModuleExecutor, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        calls.append(name)
        return ModuleResult(success=True, data=config)

    return type(
        name,
        (ModuleExecutor,),
        {
            "__module__": source,
            "module_type": property(lambda self: "open_page"),
            "execute": execute,
        },
    )


def test_registry_preserves_last_registration_wins_and_reports_cross_module_duplicate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []
    registry = ExecutorRegistry()
    first = _executor("First", "webrpa.first", calls)
    second = _executor("Second", "webrpa.second", calls)

    registry.register(first)
    registry.register(second)

    assert isinstance(registry.get("open_page"), second)
    assert "重复注册" in caplog.text


def test_registry_strict_mode_rejects_duplicate_from_another_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    registry = ExecutorRegistry()
    registry.register(_executor("First", "webrpa.first", calls))
    monkeypatch.setenv("AUTOFLOW_STRICT_WORKFLOW_REGISTRY", "1")

    with pytest.raises(RuntimeError, match="重复注册"):
        registry.register(_executor("Second", "webrpa.second", calls))


def test_production_registry_contains_every_migrated_executor() -> None:
    production = build_production_executor_registry()

    assert set(production.get_all_types()) == {
        "open_page",
        "click_element",
        "input_text",
        "get_element_info",
        "screenshot",
        "wait_page_load",
        "page_load_complete",
        "list_operation",
        "list_get",
        "list_length",
        "list_export",
        "dict_operation",
        "dict_get",
        "dict_keys",
        "regex_extract",
        "string_replace",
        "string_split",
        "string_join",
        "string_concat",
        "string_trim",
        "string_case",
        "string_substring",
        "list_sum",
        "list_average",
        "list_max",
        "list_min",
        "list_sort",
        "list_unique",
        "list_slice",
        "math_round",
        "math_base_convert",
        "math_floor",
        "math_modulo",
        "math_abs",
        "math_sqrt",
        "math_power",
        "math_log",
        "math_trig",
        "math_exp",
        "math_gcd",
        "math_lcm",
        "math_factorial",
        "math_permutation",
        "math_percentage",
        "math_clamp",
        "math_random_advanced",
        "stat_median",
        "stat_mode",
        "stat_variance",
        "stat_stdev",
        "stat_percentile",
        "stat_normalize",
        "stat_standardize",
        "random_password_generator",
        "url_encode_decode",
        "md5_encrypt",
        "sha_encrypt",
        "timestamp_converter",
        "rgb_to_hsv",
        "rgb_to_cmyk",
        "hex_to_cmyk",
        "uuid_generator",
        "list_reverse",
        "list_find",
        "list_count",
        "list_filter",
        "list_map",
        "list_merge",
        "list_flatten",
        "list_chunk",
        "list_remove_empty",
        "list_intersection",
        "list_union",
        "list_difference",
        "list_cartesian_product",
        "list_shuffle",
        "list_sample",
        "dict_merge",
        "dict_filter",
        "dict_map_values",
        "dict_invert",
        "dict_sort",
        "dict_deep_copy",
        "dict_get_path",
        "dict_flatten",
        "csv_parse",
        "csv_generate",
        "list_to_string_advanced",
        "table_add_row",
        "table_add_column",
        "table_set_cell",
        "table_get_cell",
        "table_delete_row",
        "table_clear",
        "table_export",
        "network_monitor_start",
        "network_monitor_wait",
        "network_monitor_stop",
        "switch_tab",
        "extract_table_data",
        "network_capture",
        "use_opened_page",
        "close_page",
        "refresh_page",
        "go_back",
        "go_forward",
        "switch_iframe",
        "switch_to_main",
        "hover_element",
        "handle_dialog",
        "inject_javascript",
        "wait_element",
        "select_dropdown",
        "set_checkbox",
        "drag_element",
        "scroll_page",
        "upload_file",
        "download_file",
        "get_child_elements",
        "get_sibling_elements",
        "element_exists",
        "element_visible",
        "save_image",
        "condition",
        "loop",
        "foreach",
        "infinite_loop",
        "foreach_dict",
        "break_loop",
        "continue_loop",
        "set_variable",
        "increment_decrement",
        "json_parse",
        "base64",
        "random_number",
        "get_time",
        "wait",
        "stop_workflow",
        "assert_checkpoint",
        "group",
        "note",
        "input_prompt",
        "run_workflow_file",
        "subflow",
    }


@pytest.mark.asyncio
async def test_runtime_propagates_sensitive_values_without_persisting_them_in_events() -> (
    None
):
    class Sink:
        def __init__(self) -> None:
            self.events: list[dict[str, Any]] = []

        async def publish(self, event: dict[str, Any]) -> None:
            self.events.append(event)

    sink = Sink()
    context = ExecutionContext(
        variables={"secret": '{"password":"S3CRET"}'},
        sensitive_variables={"secret"},
        events=sink,
    )
    document = {
        "nodes": [
            {
                "id": "derive",
                "type": "moduleNode",
                "data": {
                    "moduleType": "string_trim",
                    "config": {
                        "inputText": "{secret}",
                        "trimMode": "both",
                        "variableName": "derived",
                    },
                },
            },
            {
                "id": "row",
                "type": "moduleNode",
                "data": {
                    "moduleType": "table_add_row",
                    "config": {"rowData": "{derived}"},
                },
            },
            {
                "id": "export",
                "type": "moduleNode",
                "data": {
                    "moduleType": "table_export",
                    "config": {"exportFormat": "csv"},
                },
            },
        ],
        "edges": [
            {"id": "edge-1", "source": "derive", "target": "row"},
            {"id": "edge-2", "source": "row", "target": "export"},
        ],
    }

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        document, context
    )

    assert result.success is False
    assert result.failed_node_id == "export"
    assert context.variables["derived"] == '{"password":"S3CRET"}'
    assert "derived" in context.sensitive_variables
    assert context.data_rows == [{"password": "S3CRET"}]
    assert "S3CRET" not in json.dumps(sink.events, ensure_ascii=False)


def test_runtime_reports_whether_a_document_needs_a_browser() -> None:
    runtime = WorkflowRuntime(build_production_executor_registry())

    assert (
        runtime.requires_browser(
            {
                "nodes": [
                    {
                        "id": "open",
                        "data": {"moduleType": "open_page", "config": {}},
                    }
                ]
            }
        )
        is True
    )
    assert (
        runtime.requires_browser(
            {
                "nodes": [
                    {
                        "id": "concat",
                        "data": {"moduleType": "string_concat", "config": {}},
                    }
                ]
            }
        )
        is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module_type", "config"),
    [
        (
            "math_sqrt",
            {"numberValue": -8, "root": 3, "resultVariable": "result"},
        ),
        ("math_abs", {"numberValue": "NaN", "resultVariable": "result"}),
    ],
)
async def test_runtime_rejects_results_that_cannot_cross_the_json_event_boundary(
    module_type: str, config: dict[str, Any]
) -> None:
    events: list[dict[str, Any]] = []

    class Sink:
        async def publish(self, event: dict[str, Any]) -> None:
            events.append(event)

    result = await WorkflowRuntime(build_production_executor_registry()).execute(
        {
            "nodes": [
                {
                    "id": "unsafe",
                    "type": "moduleNode",
                    "data": {"moduleType": module_type, "config": config},
                }
            ],
            "edges": [],
            "variables": [],
        },
        ExecutionContext(events=Sink()),
    )

    assert result.success is False
    assert result.failed_node_id == "unsafe"
    assert result.node_result is not None
    assert result.node_result.error == "节点结果包含无法序列化的数据"
    assert events[-1]["success"] is False
    assert events[-1]["data"] is None


def test_lazy_registry_exposes_type_before_import_and_loads_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ExecutorRegistry()
    imports: list[str] = []
    calls: list[str] = []

    def fake_import(name: str, package: str) -> None:
        imports.append(f"{package}:{name}")
        registry.register(_executor("Lazy", "autoflow.lazy", calls))

    monkeypatch.setattr("importlib.import_module", fake_import)
    registry.enable_lazy({"open_page": "web.open_page"}, "autoflow.executors")

    assert registry.get_all_types() == ["open_page"]
    assert registry.get("open_page") is not None
    assert registry.get("open_page") is not None
    assert imports == ["autoflow.executors:.web.open_page"]


@pytest.mark.asyncio
async def test_preflight_rejects_all_nodes_before_any_executor_is_called() -> None:
    calls: list[str] = []
    registry = ExecutorRegistry()
    registry.register(_executor("OpenPage", "autoflow.web", calls))
    runtime = WorkflowRuntime(registry)
    document = {
        "id": "unsupported",
        "name": "含未迁入节点",
        "nodes": [
            {"id": "open", "type": "moduleNode", "data": {"moduleType": "open_page"}},
            {
                "id": "click",
                "type": "moduleNode",
                "data": {"moduleType": "click_element"},
            },
        ],
        "edges": [{"id": "edge", "source": "open", "target": "click"}],
        "variables": [],
    }

    issues = runtime.preflight(document)
    result = await runtime.execute(document, ExecutionContext())

    assert issues == (
        WorkflowScopeIssue(
            node_id="click",
            path="nodes.1.data.moduleType",
            code="UNSUPPORTED_NODE_TYPE",
            message="节点类型 click_element 的真实执行器尚未迁入",
            node_type="click_element",
        ),
    )
    assert result.issues == issues
    assert result.executed_node_ids == ()
    assert calls == []


@pytest.mark.asyncio
async def test_runtime_executes_linear_nodes_in_edge_order_and_stops_on_failure() -> (
    None
):
    execution_order: list[str] = []

    def executor_for(module_type: str, succeeds: bool) -> type[ModuleExecutor]:
        async def execute(
            self: ModuleExecutor, config: dict[str, Any], context: ExecutionContext
        ) -> ModuleResult:
            execution_order.append(module_type)
            return ModuleResult(success=succeeds, error=None if succeeds else "失败")

        return type(
            module_type.title(),
            (ModuleExecutor,),
            {
                "__module__": f"autoflow.{module_type}",
                "module_type": property(lambda self: module_type),
                "execute": execute,
            },
        )

    registry = ExecutorRegistry()
    registry.register(executor_for("open_page", True))
    registry.register(executor_for("input_text", False))
    registry.register(executor_for("screenshot", True))
    runtime = WorkflowRuntime(registry)
    document = {
        "id": "linear",
        "name": "线性失败即停",
        "nodes": [
            {"id": "shot", "type": "moduleNode", "data": {"moduleType": "screenshot"}},
            {"id": "input", "type": "moduleNode", "data": {"moduleType": "input_text"}},
            {"id": "open", "type": "moduleNode", "data": {"moduleType": "open_page"}},
        ],
        "edges": [
            {"id": "second", "source": "input", "target": "shot"},
            {"id": "first", "source": "open", "target": "input"},
        ],
        "variables": [],
    }

    result = await runtime.execute(document, ExecutionContext())

    assert result.success is False
    assert result.executed_node_ids == ("open", "input")
    assert result.failed_node_id == "input"
    assert execution_order == ["open_page", "input_text"]


@pytest.mark.asyncio
async def test_runtime_emits_one_execution_identity_per_node_dispatch() -> None:
    calls: list[str] = []
    registry = ExecutorRegistry()
    registry.register(_executor("OpenPage", "autoflow.web", calls))
    events: list[dict[str, Any]] = []

    class Sink:
        async def publish(self, event: dict[str, Any]) -> None:
            events.append(event)

    result = await WorkflowRuntime(registry).execute(
        {
            "nodes": [
                {
                    "id": "open",
                    "type": "moduleNode",
                    "data": {
                        "moduleType": "open_page",
                        "config": {"url": "about:blank"},
                    },
                }
            ],
            "edges": [],
            "variables": [],
        },
        ExecutionContext(events=Sink()),
    )

    assert result.success is True
    assert [event["type"] for event in events] == [
        "execution:node_start",
        "execution:node_complete",
    ]
    assert events[0]["nodeId"] == events[1]["nodeId"] == "open"
    assert events[0]["executionId"] == events[1]["executionId"]
    assert events[1]["success"] is True


def test_visual_nodes_do_not_require_executors() -> None:
    runtime = WorkflowRuntime(ExecutorRegistry())

    issues = runtime.preflight(
        {
            "nodes": [
                {"id": "group", "type": "group", "data": {"moduleType": "group"}},
                {"id": "note", "type": "note", "data": {"moduleType": "note"}},
            ]
        }
    )

    assert issues == ()
