"""Which nodes may change something outside the run (remediation M2 R2-10).

The default is ``possible``: a node is treated as side-effect free only when it is
listed here as pure computation, flow control, waiting or reading. Containers
(subflows, custom modules, loops, groups) are free themselves because the nodes
inside them report their own declaration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

SideEffect = Literal["none", "possible"]

_PURE_PREFIXES = ("string_", "list_", "dict_", "math_", "stat_", "rgb_to_", "table_")
_READ_ONLY = frozenset({
    # flow control and containers
    "condition", "switch", "loop", "foreach", "foreach_dict", "infinite_loop", "break_loop",
    "continue_loop", "group", "note", "subflow", "custom_module", "run_workflow_file", "stop_workflow",
    "wait", "print_log", "assert_checkpoint",
    # local computation
    "set_variable", "increment_decrement", "random_number", "random_password_generator",
    "uuid_generator", "get_time", "timestamp_converter", "url_encode_decode", "md5_encrypt",
    "sha_encrypt", "hex_to_cmyk", "json_parse", "csv_parse", "csv_generate", "regex_extract", "base64",
    "export_log", "list_export", "save_image", "image_ocr", "ocr_captcha", "face_recognition",
    # browser navigation, waiting and reading
    "open_page", "use_opened_page", "wait_element", "wait_page_load", "page_load_complete",
    "element_exists", "element_visible", "get_element_info", "get_child_elements",
    "get_sibling_elements", "extract_table_data", "screenshot", "scroll_page", "hover_element",
    "switch_tab", "switch_iframe", "switch_to_main", "go_back", "go_forward", "element_change_trigger",
    "network_capture", "network_monitor_start", "network_monitor_stop", "network_monitor_wait",
    "download_file", "firecrawl_scrape", "firecrawl_map", "firecrawl_crawl",
    # local browser state only (remediation M2 R2-28)
    "web_cookie", "web_storage", "web_intercept",
})
_PROJECT_DATA_READS = frozenset({"inputs", "readRecord", "queryRecords", "queryTableSchema"})


def node_side_effect(module_type: object, config: Mapping[str, Any]) -> SideEffect:
    if not isinstance(module_type, str):
        return "possible"
    if module_type == "project_data":
        return "none" if config.get("operation") in _PROJECT_DATA_READS else "possible"
    if module_type in _READ_ONLY or module_type.startswith(_PURE_PREFIXES):
        return "none"
    return "possible"
