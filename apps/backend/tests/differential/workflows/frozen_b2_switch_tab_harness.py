from __future__ import annotations

import asyncio
import io
import json
import sys
from contextlib import redirect_stdout

from app.executors.switch_tab import SwitchTabExecutor
from b2_switch_tab_cases import run_case

if __name__ == "__main__":
    output = io.StringIO()
    with redirect_stdout(output):
        result = asyncio.run(run_case(sys.argv[1], SwitchTabExecutor))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
