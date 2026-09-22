from autoflow.adapters.http.android_fleet_schemas import AppAction, AppLaunch


def test_app_mutations_require_idempotency_request_ids() -> None:
    launch = AppLaunch.model_validate({"requestId": "r1", "generation": 1, "packageName": "com.example.app"})
    action = AppAction.model_validate({"requestId": "r2", "generation": 1, "packageName": "com.example.app", "action": "stop"})
    assert launch.request_id == "r1"
    assert action.request_id == "r2"


def test_app_verification_requires_the_original_request_and_generation():
    from autoflow.adapters.http.android_fleet_schemas import AppVerify
    verify = AppVerify.model_validate({"requestId": "install-1", "generation": 3})
    assert verify.request_id == "install-1"
    assert verify.generation == 3


def test_fleet_router_exposes_request_id_app_verification_route():
    from autoflow.adapters.http.android_fleet import android_fleet_router

    router = android_fleet_router(object(), object())
    route = next(item for item in router.routes if item.path.endswith('/sessions/{identifier}/apps/verify'))
    assert route.methods == {'POST'}
