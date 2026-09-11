import json


def ready_line(*, port: int, api_version: str, instance_id: str) -> str:
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    payload = {"apiVersion": api_version, "instanceId": instance_id, "port": port}
    return "AUTOFLOW_READY " + json.dumps(payload, sort_keys=True, separators=(",", ":"))
