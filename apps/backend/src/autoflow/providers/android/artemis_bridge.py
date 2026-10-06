"""Bridge between AutoFlow and ARTEMIS. Runs inside the ARTEMIS venv (Python 3.12) as a subprocess.

Speaks the JSON-line protocol on stdout (one object per line, nothing else):
  {"type": "step", "index": 1, "summary": "...", "screenshot": "step-001.jpg"}
  {"type": "result", "succeeded": true, "error": null, "traceId": "...", "artifacts": [...]}
  {"type": "helper", "installed": true}

ARTEMIS is only touched through its CLI (`artemis run --standalone`, `artemis helper ...`) plus the
local IPC event stream and the files it writes, so this module imports no ARTEMIS code.
Facts: .ai/knowledge/2026-10-04-artemis-interface.md. Success is judged from run_outcome.json /
the sessions table, never from the exit code (a blocked task exits 0).
"""

import argparse
import json
import os
import queue
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

# AutoFlow provider_kind -> (ARTEMIS provider, API-key env var ARTEMIS reads)
_PROVIDERS = {
    "openai": ("openai", "OPENAI_API_KEY"),
    "openai-compatible": ("openai", "OPENAI_API_KEY"),
    "gemini": ("google", "GOOGLE_API_KEY"),
    "anthropic": ("anthropic", "ANTHROPIC_API_KEY"),
}
# Every node needs credentials for its provider at startup, so all of them are pinned to one model.
_AGENT_NODES = (
    "summarizer", "operator", "operator_summarizer", "log_reader_sub_agent", "log_analyzer",
    "diagnoser", "checker", "planner_avatar", "history_analyzer_expert", "diagnoser_expert",
    "explorer", "history_analyzer", "validator_pixel_safety_net", "planner_validation",
    "output_analyzer",
)
_UTIL_NODES = ("outputter", "hopper", "video_analyzer", "object_detector")
_STDERR_LINES = 50
_DRAIN_SECONDS = 2


def _emit(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _redact(text: str, secret: str) -> str:
    return text.replace(secret, "***") if len(secret) >= 4 else text


def _artemis_command() -> list[str]:
    """The ARTEMIS CLI entry point living next to this interpreter (the venv's Scripts/bin)."""
    exe = Path(sys.executable).parent / ("artemis.exe" if sys.platform == "win32" else "artemis")
    if exe.exists():
        return [str(exe)]
    return [sys.executable, "-c", "from artemis.interfaces.cli.main import cli; cli()"]


def _llm_config(provider: str, model: str, max_steps: int) -> dict[str, Any]:
    node = {"provider": provider, "model": model, "fallback": {"provider": provider, "model": model}}
    config: dict[str, Any] = {name: dict(node) for name in ("planner", *_AGENT_NODES)}
    config["utils"] = {name: dict(node) for name in _UTIL_NODES}
    config["agent"] = {"flash": {"max_turns": max_steps, "step_summarizer": {"model": model}}}
    return config


class _IpcListener:
    """Collects ARTEMIS' newline-delimited JSON events on an OS-assigned 127.0.0.1 port."""

    def __init__(self) -> None:
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen()
        self.port: int = self._sock.getsockname()[1]
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self._readers: list[threading.Thread] = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            reader = threading.Thread(target=self._read, args=(conn,), daemon=True)
            self._readers.append(reader)
            reader.start()

    def _read(self, conn: socket.socket) -> None:
        try:
            with conn, conn.makefile("rb") as lines:
                for raw in lines:
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(event, dict):
                        self.events.put(event)
        except OSError:
            pass  # peer was killed mid-stream; whatever arrived is enough

    def finish(self) -> None:
        deadline = time.monotonic() + _DRAIN_SECONDS
        for reader in list(self._readers):
            reader.join(max(0.0, deadline - time.monotonic()))
        self._sock.close()


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        import signal

        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) if value else ""


class _Steps:
    """Turns ARTEMIS step records into protocol `step` lines, copying screenshots to --artifacts."""

    def __init__(self, traces: Path, artifacts: Path) -> None:
        self._images = traces / "images"
        self._artifacts = artifacts
        self._seen: set[str] = set()
        self.count = 0

    def _id(self, step: dict[str, Any]) -> str:
        return str(step.get("step_id") or f"n{step.get('step_number', self.count + 1)}")

    def is_new(self, step: dict[str, Any]) -> bool:
        return self._id(step) not in self._seen

    def emit(self, step: dict[str, Any]) -> None:
        if not self.is_new(step):
            return
        self._seen.add(self._id(step))
        self.count += 1
        image = step.get("post_image_name") or step.get("pre_image_name")
        screenshot = None
        # Only a bare hash-like name is trusted; anything with separators or ".." is ignored.
        safe = isinstance(image, str) and re.fullmatch(r"[\w-]+", image) is not None
        source = self._images / f"{image}.jpg" if safe else None
        if source is not None and source.is_file():
            screenshot = f"step-{self.count:03d}.jpg"
            shutil.copyfile(source, self._artifacts / screenshot)
        summary = _text(step.get("summary")) or _text(step.get("action_taken")) or f"步骤 {self.count}"
        _emit({"type": "step", "index": self.count, "summary": summary[:500], "screenshot": screenshot})


def _db_rows(db: Path, sql: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
    if not db.is_file():
        return []
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql, args)]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def _judge(traces: Path, session_id: str) -> tuple[bool | None, str | None]:
    """(succeeded, error) from run_outcome.json, else sessions.status; (None, None) if neither."""
    try:
        outcome = json.loads((traces / session_id / "run_outcome.json").read_text("utf-8"))
        status = outcome["task_status"]
        failed = int((outcome.get("tests") or {}).get("failed") or 0)
        if status == "completed":
            return (True, None) if failed == 0 else (False, f"{failed} 项检查未通过")
        return False, "任务仅部分完成" if status == "partial" else "任务被阻塞，未能完成"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    rows = _db_rows(traces / "data_engine.db", "SELECT status FROM sessions WHERE session_id=?", (session_id,))
    status = rows[0]["status"] if rows else None
    if status == "completed":
        return True, None
    if status == "failed":
        return False, "ARTEMIS 报告任务失败"
    if status == "cancelled":
        return False, "任务被取消"
    return None, None


def _collect_logcat(serial: str, artifacts: Path) -> bool:
    try:
        done = subprocess.run(
            ["adb", "-s", serial, "logcat", "-d"], capture_output=True, timeout=20, check=False
        )
        (artifacts / "logcat.txt").write_bytes(done.stdout)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _run(args: argparse.Namespace) -> int:
    kind = os.environ.get("AUTOFLOW_MODEL_PROVIDER_KIND", "")
    if kind not in _PROVIDERS:
        sys.stderr.write(f"unsupported provider: {kind or '(empty)'}\n")
        return 2
    provider, key_env = _PROVIDERS[kind]
    secret = os.environ.get("AUTOFLOW_MODEL_SECRET", "")
    model = os.environ.get("AUTOFLOW_MODEL_KEY", "")
    base_url = os.environ.get("AUTOFLOW_MODEL_BASE_URL", "")
    instruction = sys.stdin.read().strip()
    if not instruction or not model:
        sys.stderr.write("missing instruction or model name\n")
        return 2

    artifacts = Path(args.artifacts).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".work-", dir=artifacts))
    try:
        return _run_in(args, work, artifacts, provider, key_env, kind, secret, model, base_url, instruction)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run_in(
    args: argparse.Namespace, work: Path, artifacts: Path, provider: str, key_env: str,
    kind: str, secret: str, model: str, base_url: str, instruction: str,
) -> int:
    traces = work / "traces"
    session_id = str(uuid.uuid4())
    config = work / "artemis.jsonc"
    config.write_text(json.dumps(_llm_config(provider, model, args.max_steps)), "utf-8")

    env = {k: v for k, v in os.environ.items() if not k.startswith("AUTOFLOW_MODEL_")}
    env.update({
        "ARTEMIS_APP_DIR": str(work / "app"),
        "ARTEMIS_TRACES_DIR": str(traces),
        "ARTEMIS_ARTEMIS_JSONC": str(config),
        "ARTEMIS_HELPER_AUTO_INSTALL": "false",
        "ADB_DEVICE_SERIAL": args.serial,
        "PYTHONIOENCODING": "utf-8",
        key_env: secret,
    })
    if kind == "openai-compatible" and base_url:
        env["OPENAI_BASE_URL"] = base_url
    elif base_url and kind != "openai":
        sys.stderr.write("note: ARTEMIS does not support a custom base URL for this provider\n")

    ipc = _IpcListener()
    env["ARTEMIS_IPC_PORT"] = str(ipc.port)
    steps = _Steps(traces, artifacts)
    stdout_path = artifacts / "artemis-stdout.txt"
    stderr_path = work / "stderr.txt"
    command = [
        *_artemis_command(), "run", "--standalone", "-s", args.serial, "--profile", args.mode,
        "--session-id", session_id, "--without-video-recording-tools", "--", instruction,
    ]
    over_budget = False
    proc: subprocess.Popen[bytes] | None = None
    try:
        with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            proc = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=out, stderr=err, env=env,
                start_new_session=sys.platform != "win32",
            )

            def pump(timeout: float) -> None:
                nonlocal over_budget
                try:
                    event = ipc.events.get(timeout=timeout)
                except queue.Empty:
                    return
                data = event.get("data")
                if event.get("event_type") != "step_recorded" or not isinstance(data, dict):
                    return
                if data.get("session_id") != session_id or not steps.is_new(data):
                    return
                if steps.count >= args.max_steps:
                    over_budget = True
                else:
                    steps.emit(data)

            while proc.poll() is None and not over_budget:
                pump(0.2)
            if over_budget:
                _kill_tree(proc)
            ipc.finish()
            while not ipc.events.empty():
                pump(0)
    finally:
        if proc is not None:
            _kill_tree(proc)
        ipc.finish()

    if steps.count == 0:  # IPC delivered nothing: fall back to what ARTEMIS persisted
        rows = _db_rows(
            traces / "data_engine.db",
            "SELECT * FROM steps WHERE session_id=? ORDER BY step_number", (session_id,),
        )
        for row in rows[: args.max_steps]:
            steps.emit(row)

    succeeded, error = _judge(traces, session_id)
    tail = "\n".join(
        deque(stderr_path.read_text("utf-8", "replace").splitlines(), maxlen=_STDERR_LINES)
    ) if stderr_path.exists() else ""
    if over_budget:
        succeeded, error = False, f"已达到最大步数 {args.max_steps}，测试被终止"
    elif succeeded is None:
        succeeded = False
        error = tail or f"ARTEMIS 未产出结果（退出码 {proc.returncode if proc else '?'}）"
    elif not succeeded and tail and proc is not None and proc.returncode:
        error = f"{error}\n{tail}"

    produced = ["artemis-stdout.txt"]
    session_dir = traces / session_id
    if session_dir.is_dir():
        for item in sorted(session_dir.iterdir()):
            if item.is_file():
                shutil.copyfile(item, artifacts / f"artemis-{item.name}")
                produced.append(f"artemis-{item.name}")
    if _collect_logcat(args.serial, artifacts):
        produced.append("logcat.txt")

    if not succeeded:
        sys.stderr.write(_redact(f"{error}\n", secret))
    _emit({
        "type": "result", "succeeded": bool(succeeded),
        "error": _redact(error, secret) if error else None,
        "traceId": session_id, "artifacts": produced,
    })
    return 0


def _helper(args: argparse.Namespace) -> int:
    env = {**os.environ, "ARTEMIS_HELPER_AUTO_INSTALL": "false", "PYTHONIOENCODING": "utf-8"}
    action = "status" if args.command == "helper-status" else "install"
    cmd = [*_artemis_command(), "helper", action, "-s", args.serial]
    if action == "status":
        cmd.append("--json")
    done = subprocess.run(cmd, capture_output=True, env=env, check=False)
    out = done.stdout.decode("utf-8", "replace")
    if done.returncode != 0:
        sys.stderr.write((done.stderr.decode("utf-8", "replace") + out).strip()[-4000:] + "\n")
        return 1
    if action == "install":
        _emit({"type": "helper", "installed": True})
        return 0
    start = out.find("{")  # ARTEMIS prints banners before the JSON
    try:
        installed = bool(json.loads(out[start:])["installed"])
    except (ValueError, KeyError, TypeError):
        sys.stderr.write(f"unparseable helper status: {out[-1000:]}\n")
        return 1
    _emit({"type": "helper", "installed": installed})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="artemis_bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--serial", required=True)
    run.add_argument("--mode", choices=("flash", "pro"), required=True)
    run.add_argument("--max-steps", type=int, required=True)
    run.add_argument("--artifacts", required=True)
    for name in ("helper-status", "helper-install"):
        sub.add_parser(name).add_argument("--serial", required=True)
    args = parser.parse_args(argv)
    return _run(args) if args.command == "run" else _helper(args)


if __name__ == "__main__":
    sys.exit(main())
