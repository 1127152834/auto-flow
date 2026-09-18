"""Approved Studio node scope and non-mutating execution preflight."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

APPROVED_NODE_TYPES: frozenset[str] = frozenset(
    {
        "ai_chat",
        "ai_classify",
        "ai_dedup_semantic",
        "ai_element_selector",
        "ai_extract",
        "ai_generate_image",
        "ai_generate_video",
        "ai_normalize",
        "ai_route",
        "ai_sentiment",
        "ai_smart_scraper",
        "ai_summarize",
        "ai_translate",
        "ai_vision",
        "ai_vision_act",
        "allure_add_attachment",
        "allure_add_step",
        "allure_generate_report",
        "allure_init",
        "allure_start_test",
        "allure_stop_test",
        "api_request",
        "api_trigger",
        "assert_checkpoint",
        "base64",
        "break_loop",
        "click_element",
        "close_page",
        "condition",
        "continue_loop",
        "csv_generate",
        "csv_parse",
        "dict_deep_copy",
        "dict_filter",
        "dict_flatten",
        "dict_get",
        "dict_get_path",
        "dict_invert",
        "dict_keys",
        "dict_map_values",
        "dict_merge",
        "dict_operation",
        "dict_sort",
        "download_file",
        "drag_element",
        "element_change_trigger",
        "element_exists",
        "element_visible",
        "email_trigger",
        "export_log",
        "extract_table_data",
        "face_recognition",
        "face_trigger",
        "file_watcher_trigger",
        "firecrawl_crawl",
        "firecrawl_map",
        "firecrawl_scrape",
        "foreach",
        "foreach_dict",
        "gesture_trigger",
        "get_child_elements",
        "get_clipboard",
        "get_element_info",
        "get_sibling_elements",
        "get_time",
        "go_back",
        "go_forward",
        "group",
        "handle_dialog",
        "hex_to_cmyk",
        "hotkey_trigger",
        "hover_element",
        "image_ocr",
        "image_trigger",
        "increment_decrement",
        "infinite_loop",
        "inject_javascript",
        "input_prompt",
        "input_text",
        "js_script",
        "json_parse",
        "list_average",
        "list_cartesian_product",
        "list_chunk",
        "list_count",
        "list_difference",
        "list_export",
        "list_filter",
        "list_find",
        "list_flatten",
        "list_get",
        "list_intersection",
        "list_length",
        "list_map",
        "list_max",
        "list_merge",
        "list_min",
        "list_operation",
        "list_remove_empty",
        "list_reverse",
        "list_sample",
        "list_shuffle",
        "list_slice",
        "list_sort",
        "list_sum",
        "list_to_string_advanced",
        "list_union",
        "list_unique",
        "lock_screen",
        "loop",
        "math_abs",
        "math_base_convert",
        "math_clamp",
        "math_exp",
        "math_factorial",
        "math_floor",
        "math_gcd",
        "math_lcm",
        "math_log",
        "math_modulo",
        "math_percentage",
        "math_permutation",
        "math_power",
        "math_random_advanced",
        "math_round",
        "math_sqrt",
        "math_trig",
        "md5_encrypt",
        "mouse_trigger",
        "network_capture",
        "network_monitor_start",
        "network_monitor_stop",
        "network_monitor_wait",
        "note",
        "notify_bark",
        "notify_dingtalk",
        "notify_discord",
        "notify_gotify",
        "notify_matrix",
        "notify_msteams",
        "notify_ntfy",
        "notify_pushbullet",
        "notify_pushover",
        "notify_pushplus",
        "notify_rocketchat",
        "notify_serverchan",
        "notify_slack",
        "notify_telegram",
        "notify_webhook",
        "notify_wecom",
        "ocr_captcha",
        "open_page",
        "page_load_complete",
        "play_sound",
        "print_log",
        "printer_call",
        "probability_trigger",
        "python_script",
        "random_number",
        "random_password_generator",
        "refresh_page",
        "regex_extract",
        "rgb_to_cmyk",
        "rgb_to_hsv",
        "run_command",
        "run_workflow_file",
        "save_image",
        "scheduled_task",
        "screenshot",
        "scroll_page",
        "select_dropdown",
        "send_email",
        "set_checkbox",
        "set_clipboard",
        "set_variable",
        "sha_encrypt",
        "share_file",
        "share_folder",
        "shutdown_system",
        "slider_captcha",
        "sound_trigger",
        "ssh_connect",
        "ssh_disconnect",
        "ssh_download_file",
        "ssh_execute_command",
        "ssh_upload_file",
        "start_screen_share",
        "stat_median",
        "stat_mode",
        "stat_normalize",
        "stat_percentile",
        "stat_standardize",
        "stat_stdev",
        "stat_variance",
        "stop_screen_share",
        "stop_share",
        "stop_workflow",
        "string_case",
        "string_concat",
        "string_join",
        "string_replace",
        "string_split",
        "string_substring",
        "string_trim",
        "subflow",
        "switch_iframe",
        "switch_tab",
        "switch_to_main",
        "system_notification",
        "table_add_column",
        "table_add_row",
        "table_clear",
        "table_delete_row",
        "table_export",
        "table_get_cell",
        "table_set_cell",
        "text_to_speech",
        "timestamp_converter",
        "upload_file",
        "url_encode_decode",
        "use_opened_page",
        "uuid_generator",
        "wait",
        "wait_element",
        "wait_page_load",
        "webhook_request",
        "webhook_trigger",
    }
)

EXCLUDED_LEGACY_NODE_TYPES: frozenset[str] = frozenset(
    {
        "db_close",
        "db_connect",
        "db_delete",
        "db_execute",
        "db_insert",
        "db_query",
        "db_update",
        "dp_click",
        "dp_close",
        "dp_get_html",
        "dp_get_text",
        "dp_input",
        "dp_open_page",
        "dp_run_js",
        "dp_scroll",
        "dp_wait_element",
        "mongodb_connect",
        "mongodb_delete",
        "mongodb_disconnect",
        "mongodb_find",
        "mongodb_insert",
        "mongodb_update",
        "oracle_connect",
        "oracle_delete",
        "oracle_disconnect",
        "oracle_execute",
        "oracle_insert",
        "oracle_query",
        "oracle_update",
        "postgresql_connect",
        "postgresql_delete",
        "postgresql_disconnect",
        "postgresql_execute",
        "postgresql_insert",
        "postgresql_query",
        "postgresql_update",
        "redis_connect",
        "redis_del",
        "redis_disconnect",
        "redis_get",
        "redis_hget",
        "redis_hset",
        "redis_set",
        "sqlite_connect",
        "sqlite_delete",
        "sqlite_disconnect",
        "sqlite_execute",
        "sqlite_insert",
        "sqlite_query",
        "sqlite_update",
        "sqlserver_connect",
        "sqlserver_delete",
        "sqlserver_disconnect",
        "sqlserver_execute",
        "sqlserver_insert",
        "sqlserver_query",
        "sqlserver_update",
    }
)


@dataclass(frozen=True, slots=True)
class WorkflowScopeIssue:
    node_id: str
    path: str
    code: str
    message: str
    node_type: str

    def as_dict(self) -> dict[str, str]:
        return {
            "nodeId": self.node_id,
            "path": self.path,
            "code": self.code,
            "message": self.message,
            "nodeType": self.node_type,
        }


def _node_type(node: Mapping[str, Any]) -> tuple[str, str]:
    data = node.get("data")
    if isinstance(data, Mapping) and isinstance(data.get("moduleType"), str):
        return data["moduleType"], "data.moduleType"
    if isinstance(node.get("moduleType"), str):
        return node["moduleType"], "moduleType"
    value = node.get("type")
    return (value if isinstance(value, str) else "", "type")


def _custom_module_id(node: Mapping[str, Any]) -> str | None:
    data = node.get("data")
    config = data.get("config") if isinstance(data, Mapping) else None
    for container in (config, data, node):
        if isinstance(container, Mapping):
            value = container.get("customModuleId")
            if isinstance(value, str) and value:
                return value
    return None


def _module_nodes(module: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_nodes: object = module.get("nodes")
    workflow = module.get("workflow")
    if not isinstance(raw_nodes, list) and isinstance(workflow, Mapping):
        raw_nodes = workflow.get("nodes")
    if not isinstance(raw_nodes, list):
        return []
    return [node for node in raw_nodes if isinstance(node, Mapping)]


def validate_workflow_scope(
    nodes: Iterable[Mapping[str, Any]],
    *,
    runnable_node_types: Iterable[str],
    resolve_custom_module: Callable[[str], Mapping[str, Any] | None] = lambda _id: None,
) -> tuple[WorkflowScopeIssue, ...]:
    """Return scope problems without changing the workflow or module definitions."""

    runnable = frozenset(runnable_node_types)
    issues: list[WorkflowScopeIssue] = []
    visited_modules: set[str] = set()

    def visit(current_nodes: Iterable[Mapping[str, Any]], prefix: str) -> None:
        for index, node in enumerate(current_nodes):
            node_type, type_path = _node_type(node)
            node_id_value = node.get("id")
            node_id = node_id_value if isinstance(node_id_value, str) else ""
            path = f"{prefix}.{index}.{type_path}"
            if node_type == "custom_module":
                module_id = _custom_module_id(node)
                if not module_id or module_id in visited_modules:
                    continue
                visited_modules.add(module_id)
                module = resolve_custom_module(module_id)
                if module is not None:
                    visit(_module_nodes(module), f"customModules.{module_id}.nodes")
                continue
            if node_type not in APPROVED_NODE_TYPES:
                issues.append(
                    WorkflowScopeIssue(
                        node_id=node_id,
                        path=path,
                        code="UNSUPPORTED_NODE_TYPE",
                        message=(
                            f"节点类型 {node_type or '<empty>'} "
                            "不在 AutoFlow Studio 当前批准范围内"
                        ),
                        node_type=node_type,
                    )
                )
                continue
            if node_type not in runnable:
                issues.append(
                    WorkflowScopeIssue(
                        node_id=node_id,
                        path=path,
                        code="UNSUPPORTED_NODE_TYPE",
                        message=f"节点类型 {node_type} 的真实执行器尚未迁入",
                        node_type=node_type,
                    )
                )
                continue
    visit(nodes, "nodes")
    return tuple(issues)
