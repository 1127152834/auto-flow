import io
import json
import sys
import textwrap

import pytest

from autoflow.providers.android import artemis_bridge

SECRET = "sk-super-secret-123"

FAKE_CLI = textwrap.dedent(
    '''
    import json, os, socket, sqlite3, sys, time
    from pathlib import Path

    mode = os.environ["FAKE_MODE"]
    argv = sys.argv[1:]
    sid = argv[argv.index("--session-id") + 1]
    traces = Path(os.environ["ARTEMIS_TRACES_DIR"])
    Path(os.environ["FAKE_DUMP"]).write_text(json.dumps({
        "argv": argv,
        "jsonc": json.loads(Path(os.environ["ARTEMIS_ARTEMIS_JSONC"]).read_text("utf-8")),
        "env": {k: os.environ.get(k) for k in (
            "OPENAI_API_KEY", "OPENAI_BASE_URL", "GOOGLE_API_KEY", "ARTEMIS_HELPER_AUTO_INSTALL",
            "AUTOFLOW_MODEL_SECRET", "ADB_DEVICE_SERIAL")},
    }), "utf-8")
    print("banner: Activated local ADB server endpoint")
    if mode == "crash":
        print("Traceback: DeviceNotFoundError " + os.environ.get("OPENAI_API_KEY", ""), file=sys.stderr)
        sys.exit(1)
    (traces / "images").mkdir(parents=True, exist_ok=True)
    for name in ("aaa", "bbb", "ccc"):
        (traces / "images" / f"{name}.jpg").write_bytes(b"img-" + name.encode())

    def step(n, pre, post=""):
        return {"event_type": "step_recorded", "data": {
            "step_id": f"s{n}", "step_number": n, "session_id": sid, "summary": f"step {n}",
            "action_taken": {}, "pre_image_name": pre, "post_image_name": post}}

    steps = [step(1, "aaa", "bbb"), step(2, "bbb", ""), step(3, "ccc")]
    if mode in ("ok", "blocked", "slow"):
        s = socket.create_connection(("127.0.0.1", int(os.environ["ARTEMIS_IPC_PORT"])))
        send = [{"event_type": "session_started", "data": {}}, steps[0], steps[0], steps[1]]
        if mode == "slow":
            send.append(steps[2])
        s.sendall("".join(json.dumps(e) + "\\n" for e in send).encode())
        if mode == "slow":
            time.sleep(60)
        s.close()
    if mode == "noipc":
        db = sqlite3.connect(traces / "data_engine.db")
        db.execute("create table sessions (session_id text, status text)")
        db.execute("insert into sessions values (?, 'completed')", (sid,))
        db.execute("create table steps (step_id text, session_id text, step_number int, summary text,"
                   " pre_image_name text, post_image_name text, action_taken text)")
        for n, pre, post in ((1, "aaa", "bbb"), (2, "bbb", "")):
            db.execute("insert into steps values (?,?,?,?,?,?,?)", (f"s{n}", sid, n, f"db step {n}", pre, post, ""))
        db.commit()
        db.close()
    else:
        d = traces / sid
        d.mkdir(parents=True, exist_ok=True)
        status = "blocked" if mode == "blocked" else "completed"
        (d / "run_outcome.json").write_text(json.dumps({"task_status": status, "tests": {"failed": 0}}))
    '''
)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    cli = tmp_path / "fake_cli.py"
    cli.write_text(FAKE_CLI, "utf-8")
    dump = tmp_path / "dump.json"
    monkeypatch.setattr(artemis_bridge, "_artemis_command", lambda: [sys.executable, str(cli)])
    monkeypatch.setattr(
        artemis_bridge,
        "_collect_logcat",
        lambda serial, artifacts: bool((artifacts / "logcat.txt").write_text("log")),
    )
    monkeypatch.setenv("FAKE_DUMP", str(dump))
    monkeypatch.setenv("AUTOFLOW_MODEL_PROVIDER_KIND", "openai-compatible")
    monkeypatch.setenv("AUTOFLOW_MODEL_BASE_URL", "http://gw.local/v1")
    monkeypatch.setenv("AUTOFLOW_MODEL_KEY", "gpt-x")
    monkeypatch.setenv("AUTOFLOW_MODEL_SECRET", SECRET)

    def go(mode, max_steps=10, instruction="打开设置"):
        monkeypatch.setenv("FAKE_MODE", mode)
        monkeypatch.setattr(sys, "stdin", io.StringIO(instruction))
        art = tmp_path / "art"
        code = artemis_bridge.main(
            ["run", "--serial", "emu-1", "--mode", "flash", "--max-steps", str(max_steps), "--artifacts", str(art)]
        )
        return code, art, dump

    return go


def lines(capsys):
    out, err = capsys.readouterr()
    return [json.loads(line) for line in out.splitlines()], err


def test_success_emits_steps_and_result(harness, capsys):
    code, art, dump = harness("ok")
    events, _ = lines(capsys)
    assert code == 0
    assert [e["type"] for e in events] == ["step", "step", "result"]
    assert events[0] == {"type": "step", "index": 1, "summary": "step 1", "screenshot": "step-001.jpg"}
    assert events[1]["screenshot"] == "step-002.jpg"  # no post image -> pre image
    assert (art / "step-001.jpg").read_bytes() == b"img-bbb"
    result = events[-1]
    assert result["succeeded"] is True and result["error"] is None and result["traceId"]
    assert {"artemis-run_outcome.json", "artemis-stdout.txt", "logcat.txt"} <= set(result["artifacts"])
    assert not list(art.glob(".work-*"))
    seen = json.loads(dump.read_text("utf-8"))
    assert "--standalone" in seen["argv"] and seen["argv"][-1] == "打开设置"
    assert seen["env"] == {
        "OPENAI_API_KEY": SECRET,
        "OPENAI_BASE_URL": "http://gw.local/v1",
        "GOOGLE_API_KEY": None,
        "ARTEMIS_HELPER_AUTO_INSTALL": "false",
        "AUTOFLOW_MODEL_SECRET": None,
        "ADB_DEVICE_SERIAL": "emu-1",
    }
    cfg = seen["jsonc"]
    assert cfg["planner"]["provider"] == "openai" and cfg["planner"]["fallback"]["model"] == "gpt-x"
    assert cfg["utils"]["object_detector"]["model"] == "gpt-x"
    assert cfg["planner_validation"]["model"] == "gpt-x" and cfg["agent"]["flash"]["max_turns"] == 10


def test_blocked_task_is_a_failed_result_not_an_error(harness, capsys):
    code, _, _ = harness("blocked")
    events, err = lines(capsys)
    assert code == 0
    assert events[-1]["succeeded"] is False and "阻塞" in events[-1]["error"]
    assert "阻塞" in err


def test_steps_fall_back_to_database_without_ipc(harness, capsys):
    code, _, _ = harness("noipc")
    events, _ = lines(capsys)
    assert code == 0
    assert [e.get("summary") for e in events[:-1]] == ["db step 1", "db step 2"]
    assert events[-1]["succeeded"] is True


def test_crash_without_outcome_reports_stderr_and_redacts_secret(harness, capsys):
    code, _, _ = harness("crash")
    events, err = lines(capsys)
    assert code == 0 and len(events) == 1
    assert events[0]["succeeded"] is False
    assert "DeviceNotFoundError" in events[0]["error"] and SECRET not in events[0]["error"]
    assert SECRET not in err


def test_step_budget_terminates_the_run(harness, capsys):
    code, _, _ = harness("slow", max_steps=2)
    events, _ = lines(capsys)
    assert code == 0
    assert [e["type"] for e in events] == ["step", "step", "result"]
    assert events[-1]["succeeded"] is False and "最大步数 2" in events[-1]["error"]


def test_unsupported_provider_exits_2(harness, monkeypatch, capsys):
    monkeypatch.setenv("AUTOFLOW_MODEL_PROVIDER_KIND", "custom")
    code, _, _ = harness("ok")
    out, err = capsys.readouterr()
    assert code == 2 and out == "" and "unsupported provider" in err


@pytest.mark.parametrize(
    ("kind", "provider"), [("gemini", "google"), ("anthropic", "anthropic")]
)
def test_provider_mapping(harness, monkeypatch, kind, provider):
    monkeypatch.setenv("AUTOFLOW_MODEL_PROVIDER_KIND", kind)
    _, _, dump = harness("ok")
    seen = json.loads(dump.read_text("utf-8"))
    assert seen["jsonc"]["planner"]["provider"] == provider
    assert seen["env"]["OPENAI_API_KEY"] is None


def test_helper_status_and_install(tmp_path, monkeypatch, capsys):
    cli = tmp_path / "cli.py"
    cli.write_text(
        'import sys\nprint("banner")\n'
        'print("{\\n  \\"installed\\": " + ("true" if sys.argv[2] == "status" else "false") + "\\n}")\n',
        "utf-8",
    )
    monkeypatch.setattr(artemis_bridge, "_artemis_command", lambda: [sys.executable, str(cli)])
    assert artemis_bridge.main(["helper-status", "--serial", "S"]) == 0
    assert lines(capsys)[0] == [{"type": "helper", "installed": True}]
    assert artemis_bridge.main(["helper-install", "--serial", "S"]) == 0
    assert lines(capsys)[0] == [{"type": "helper", "installed": True}]


def test_helper_failure_exits_nonzero_with_reason(tmp_path, monkeypatch, capsys):
    cli = tmp_path / "cli.py"
    cli.write_text('import sys\nprint("no device", file=sys.stderr)\nsys.exit(1)\n', "utf-8")
    monkeypatch.setattr(artemis_bridge, "_artemis_command", lambda: [sys.executable, str(cli)])
    assert artemis_bridge.main(["helper-install", "--serial", "S"]) == 1
    out, err = capsys.readouterr()
    assert out == "" and "no device" in err
