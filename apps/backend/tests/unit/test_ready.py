from autoflow.bootstrap.ready import ready_line


def test_ready_line_is_machine_readable():
    assert ready_line(port=43127, api_version="v1", instance_id="test") == (
        'AUTOFLOW_READY {"apiVersion":"v1","instanceId":"test","port":43127}'
    )
