"""VM-wide pending lifecycle budgets; writers hold the existing runtime lock."""
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from autoflow.domain.android.ports import AndroidError

FILENAME = 'autoflow-redroid-capacity.json'


def key(device: dict[str, Any]) -> str:
    return device['workspaceId'] + ':' + device['deviceId']


def load(root: Path) -> dict[str, dict[str, Any]]:
    path = root / FILENAME
    try:
        if path.is_symlink():
            raise ValueError('reservation journal is a link')
        try:
            document = json.loads(path.read_text())
        except FileNotFoundError:
            return {}
        if document['version'] != 1 or not isinstance(document['items'], dict):
            raise ValueError('unsupported reservation journal')
        for identifier, item in document['items'].items():
            if (
                key(item) != identifier
                or not re.fullmatch(r'[0-9a-f]{64}', item['workspaceId'])
                or str(UUID(item['deviceId'])) != item['deviceId']
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,254}', item['containerId'])
                or type(item['generation']) is not int or item['generation'] < 0
                or (item['memoryBytes'] is not None and (type(item['memoryBytes']) is not int or item['memoryBytes'] <= 0))
                or not re.fullmatch(r'/tmp/autoflow-lifecycle-[0-9a-f]{32}', item['marker'])
            ):
                raise ValueError('invalid reservation')
        return document['items']
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise AndroidError('ANDROID_CAPACITY_UNKNOWN', '运行环境预留预算尚未核实，不能启动实例', 409) from error


def save(root: Path, items: dict[str, dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=root, prefix='.android-capacity-', delete=False) as output:
            path = Path(output.name)
            json.dump({'version': 1, 'items': items}, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(path, root / FILENAME)
        directory = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def pending(root: Path, device: dict[str, Any]) -> dict[str, Any] | None:
    item = load(root).get(key(device))
    if item is not None and (item['containerId'] != device['containerId'] or item['generation'] > device.get('generation', 0)):
        raise AndroidError('ANDROID_RECOVERY_REQUIRED', '设备预留预算与当前代次或容器不符', 409)
    return item


def reserve(root: Path, device: dict[str, Any], marker: str, memory: int | None) -> None:
    items = load(root)
    identifier = key(device)
    if identifier in items:
        raise AndroidError('ANDROID_RECOVERY_REQUIRED', '设备仍有未核实的资源预留', 409)
    items[identifier] = {field: device[field] for field in ('workspaceId', 'deviceId', 'containerId')}
    items[identifier].update(generation=device.get('generation', 0), marker=marker, memoryBytes=memory)
    save(root, items)


def release(root: Path, device: dict[str, Any], marker: str) -> None:
    item = pending(root, device)
    if item is None:
        return
    if item['marker'] != marker:
        raise AndroidError('ANDROID_RECOVERY_REQUIRED', '设备预留操作标记已变化', 409)
    items = load(root)
    items.pop(key(device))
    save(root, items)
