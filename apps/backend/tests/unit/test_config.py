from autoflow.bootstrap.config import Settings


def test_settings_is_directly_constructible_with_defaults():
    settings = Settings(data_dir="/tmp/autoflow-test", instance_id="test")
    assert settings.data_dir == "/tmp/autoflow-test"
    assert settings.instance_id == "test"
    assert settings.instance_token is None
    assert settings.parent_pid is None
    assert settings.api_version == "v1"
