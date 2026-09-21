from autoflow.adapters.http.android_fleet_schemas import AppAction, AppLaunch


def test_app_mutations_require_idempotency_request_ids() -> None:
    launch = AppLaunch.model_validate({"requestId": "r1", "generation": 1, "packageName": "com.example.app"})
    action = AppAction.model_validate({"requestId": "r2", "generation": 1, "packageName": "com.example.app", "action": "stop"})
    assert launch.request_id == "r1"
    assert action.request_id == "r2"
