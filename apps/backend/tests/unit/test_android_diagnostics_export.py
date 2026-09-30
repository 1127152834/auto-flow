from datetime import UTC, datetime

from autoflow.application.android.diagnostics_export import (
    redact_diagnostics,
    summarize_logcat,
)


def test_diagnostics_export_removes_paths_secrets_and_input_text():
    output = redact_diagnostics({"path": "/Users/private/work", "token": "secret", "inputText": "账号", "code": "E1"})
    assert output == {"code": "E1"}


def test_diagnostics_export_removes_accounts_and_raw_logs():
    output = redact_diagnostics({"code": "ANDROID_BUSY", "accounts": ["private"], "logcat": "raw", "rawLogcat": "raw", "message": "safe"})
    assert output == {"code": "ANDROID_BUSY", "message": "safe"}


def test_diagnostics_export_redacts_nested_private_values_and_host_paths():
    output = redact_diagnostics(
        {
            "checks": {
                "message": "failed at /Users/alice/Library/Containers/autoflow",
                "details": {"token": "secret", "safe": "value"},
            },
            "items": [{"workspacePath": "/home/alice/work", "code": "E1"}],
        }
    )

    assert output == {
        "checks": {
            "message": "failed at [REDACTED_PATH]",
            "details": {"safe": "value"},
        },
        "items": [{"code": "E1"}],
    }


def test_advanced_log_summary_bounds_time_size_and_excludes_message_text():
    now = datetime.now(UTC).timestamp()
    raw = (
        f"{now - 400:.3f}  1  2 E Old: forgotten-secret\n"
        f"         {now:.3f}  1  2 W secretInput: account=private@example.com\n"
        f"{now:.3f}  1  2 E Bad/Tag: password=hunter2\n"
    ).encode()
    assert summarize_logcat(raw) == [{"at": round(now, 3), "priority": "W"}]
    assert summarize_logcat(raw, max_bytes=1) == []
