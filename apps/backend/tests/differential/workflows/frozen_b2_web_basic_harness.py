from __future__ import annotations

import asyncio
import io
import json
import sys
from contextlib import redirect_stdout

from app.executors.basic import (
    ClosePageExecutor,
    GoBackExecutor,
    GoForwardExecutor,
    HandleDialogExecutor,
    HoverElementExecutor,
    InjectJavaScriptExecutor,
    RefreshPageExecutor,
    SwitchIframeExecutor,
    SwitchToMainExecutor,
    UseOpenedPageExecutor,
    WaitElementExecutor,
)
from b2_web_basic_cases import run_case

EXECUTORS = {
    "use_opened_page": UseOpenedPageExecutor,
    "close_page": ClosePageExecutor,
    "refresh_page": RefreshPageExecutor,
    "go_back": GoBackExecutor,
    "go_forward": GoForwardExecutor,
    "switch_iframe": SwitchIframeExecutor,
    "switch_to_main": SwitchToMainExecutor,
    "hover_element": HoverElementExecutor,
    "handle_dialog": HandleDialogExecutor,
    "inject_javascript": InjectJavaScriptExecutor,
    "wait_element": WaitElementExecutor,
}


if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        result = asyncio.run(run_case(sys.argv[1], EXECUTORS))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str))
