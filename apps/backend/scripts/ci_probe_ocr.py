"""Diagnostic only: times the EasyOCR phases on a CI runner and reports a stack when one hangs."""

import sys
import threading
import time
import traceback
from pathlib import Path

START = time.monotonic()


def say(level: str, title: str, text: str) -> None:
    text = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::{level} title={title}::{text}", flush=True)


def watchdog() -> None:
    main_id = threading.main_thread().ident
    for _ in range(6):
        time.sleep(40)
        frame = sys._current_frames().get(main_id)
        stack = "".join(traceback.format_stack(frame)[-12:]) if frame else "no frame"
        say("warning", "ocr-stack", f"t={time.monotonic() - START:.0f}s\n{stack[-3000:]}")


threading.Thread(target=watchdog, daemon=True).start()


def phase(name: str, call):
    began = time.monotonic()
    try:
        result = call()
    except BaseException as error:  # noqa: BLE001 - diagnostic
        say("error", "ocr-phase", f"{name} failed after {time.monotonic() - began:.1f}s: {error!r}")
        raise
    say("notice", "ocr-phase", f"{name} took {time.monotonic() - began:.1f}s")
    return result


root = Path("ocr-probe")
root.mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.integration.test_b5_media_recognition_worker import _write_fixtures  # noqa: E402

_, text = _write_fixtures(root)
phase("import torch", lambda: __import__("torch"))
phase("import easyocr", lambda: __import__("easyocr"))
from autoflow.application.workflows.executors import media_recognition as module  # noqa: E402

reader = phase("Reader()", module._reader)
from PIL import Image  # noqa: E402

image = Image.open(text)
for attempt in (1, 2):
    value = phase(f"readtext #{attempt}", lambda: module._general_text(image))
    say("notice", "ocr-text", repr(value))
say("notice", "ocr-total", f"{time.monotonic() - START:.1f}s")
