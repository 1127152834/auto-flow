from dataclasses import dataclass


@dataclass
class Settings:
    data_dir: str
    instance_id: str
    instance_token: str | None = None
    parent_pid: int | None = None
    renderer_origin: str | None = None
    api_version: str = "v1"
    host_token: str | None = None
