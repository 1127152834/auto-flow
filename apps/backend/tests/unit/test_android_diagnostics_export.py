from autoflow.application.android.diagnostics_export import redact_diagnostics


def test_diagnostics_export_removes_paths_secrets_and_input_text():
    output = redact_diagnostics({"path": "/Users/private/work", "token": "secret", "inputText": "账号", "code": "E1"})
    assert output == {"code": "E1"}


def test_diagnostics_export_removes_accounts_and_raw_logs():
    output = redact_diagnostics({"code": "ANDROID_BUSY", "accounts": ["private"], "logcat": "raw", "rawLogcat": "raw", "message": "safe"})
    assert output == {"code": "ANDROID_BUSY", "message": "safe"}
