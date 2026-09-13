"""Mac-only real API smoke: creates and cleans only its own two isolated devices."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pause-reference-container', choices=['afd-5a7beadf6de2468d'])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    process = subprocess.Popen([str(args.executable.resolve()), '--data-dir', str(args.workspace.resolve()), '--instance-id', 'android-management-smoke', '--port', '0'], env={**os.environ, 'AUTOFLOW_INSTANCE_TOKEN': token}, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    assert process.stdout
    while True:
        line = process.stdout.readline()
        if line.startswith('AUTOFLOW_READY '):
            ready = json.loads(line[len('AUTOFLOW_READY '):]); break
        if not line:
            raise RuntimeError('Sidecar did not start')
    client = httpx.Client(base_url=f"http://127.0.0.1:{ready['port']}", headers={'x-autoflow-token': token}, timeout=60, trust_env=False)
    ids, checks = [], []
    active_run = None

    def api(method, path, body=None, expected=200):
        response = client.request(method, '/api/v1/' + path, json=body)
        assert response.status_code == expected, (response.status_code, response.text)
        return response.json()

    def wait_device(identifier):
        deadline = time.monotonic() + 230
        while time.monotonic() < deadline:
            device = api('GET', 'android/devices/' + identifier)
            if device.get('operation', {}).get('state') != 'running':
                return device
            time.sleep(.4)
        raise AssertionError('device operation timed out')

    def command(identifier, action, delete=False):
        api('POST', f'android/devices/{identifier}/operations', {'requestId': str(uuid4()), 'action': action, 'deleteData': delete}, 202)
        if action == 'delete' and delete:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                items = api('GET', 'android/devices')
                found = next((d for d in items if d['deviceId'] == identifier), None)
                if found is None: return
                assert found['operation']['state'] in {'running', 'succeeded'}, found
                time.sleep(.2)
            raise AssertionError('device not removed')
        device = wait_device(identifier)
        assert device['operation']['state'] == 'succeeded', device
        return device

    paused = False
    try:
        if args.pause_reference_container:
            state = subprocess.check_output(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'inspect', args.pause_reference_container, '--format', '{{.State.Running}}']).strip()
            if state == b'true':
                paused = True
                subprocess.run(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'stop', args.pause_reference_container], check=True, capture_output=True)
        environment = api('GET', 'android/environment')
        assert environment['available'] and environment['images']
        for index in range(2):
            body = {'deviceId': str(uuid4()), 'name': f'管理验收 {index+1}', 'imageId': environment['images'][0]['id'], 'width': 540, 'height': 960, 'dpi': 240, 'cpu': 1, 'memoryMb': 768, 'start': True}
            ids.append(body['deviceId'])
            created = api('POST', 'android/devices', body, 202)
            assert created['control'] == 'managing'
            assert api('POST', 'android/devices', body, 202)['deviceId'] == ids[-1]
            device = wait_device(ids[-1])
            (args.output / f'created-{index}.json').write_text(json.dumps(device, ensure_ascii=False, indent=2))
            assert device['androidStatus'] == 'ready', device
        checks.append('two independent instances ready; create retry idempotent')
        for index, identifier in enumerate(ids):
            name = 'autoflow-android-' + identifier
            subprocess.run(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'exec', name, 'sh', '-c', f'echo device-{index} > /data/local/tmp/management-proof'], check=True, capture_output=True)
        def proof(identifier):
            return subprocess.check_output(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'exec', 'autoflow-android-' + identifier, 'cat', '/data/local/tmp/management-proof']).decode().strip()
        assert proof(ids[0]) == 'device-0' and proof(ids[1]) == 'device-1'
        before = proof(ids[1])
        image = client.get(f'/api/v1/android/devices/{ids[0]}/preview')
        assert image.status_code == 200 and image.content.startswith(b'\x89PNG')
        (args.output / 'preview.png').write_bytes(image.content)
        command(ids[0], 'stop'); assert command(ids[0], 'start')['androidStatus'] == 'ready'
        assert command(ids[0], 'restart')['androidStatus'] == 'ready'
        assert proof(ids[0]) == 'device-0'
        assert command(ids[0], 'delete')['dataRetained']
        assert command(ids[0], 'start')['androidStatus'] == 'ready'
        assert proof(ids[0]) == 'device-0' and proof(ids[1]) == before
        checks.append('stop/start/restart; remove runtime retaining data and restore; other device unchanged')
        api('PATCH', 'android/devices/' + ids[0], {'name': '管理验收 已重命名'})
        nodes = [
            {'id': 'loop', 'type': 'loop', 'label': '两轮', 'config': {'mode': 'count', 'source': {'kind': 'literal', 'value': 2}, 'indexVariable': 'index', 'endNodeId': 'end', 'maxIterations': 3}},
            {'id': 'screen', 'type': 'android_screenshot', 'label': '每轮截图', 'config': {'variableName': 'screen'}},
            {'id': 'manual', 'type': 'android_manual', 'label': '每轮人工处理', 'config': {'prompt': '第 ${index} 轮', 'timeoutSeconds': 30}},
            {'id': 'end', 'type': 'loop_end', 'label': '循环结束', 'config': {'ownerNodeId': 'loop'}},
        ]
        document = {'id': str(uuid4()), 'name': '安卓 M4 真实验收', 'schemaVersion': 2, 'variables': [], 'nodes': nodes, 'edges': [{'id': str(i), 'source': a, 'sourceHandle': b, 'target': c, 'targetHandle': 'in'} for i, (a,b,c) in enumerate([('loop','body','screen'), ('screen','out','manual'), ('manual','out','end')])]}
        layout = {'nodes': {n['id']: {'x': i*240, 'y': 0} for i,n in enumerate(nodes)}, 'viewport': {'x':0,'y':0,'zoom':1}}
        active_run = str(uuid4())
        body = {'runId': active_run, 'target': {'kind':'android','deviceId':ids[0]}, 'document':document,'layout':layout}
        api('POST', 'workflows/runs', body, 201)
        handoffs = []
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            record = api('GET', 'workflows/runs/' + active_run)
            if record['state'] == 'waiting_manual' and record['handoff']['handoffId'] not in handoffs:
                hid = record['handoff']['handoffId']; handoffs.append(hid)
                assert record['handoff']['prompt'] == f'第 {len(handoffs)} 轮'
                api('POST', f'android/devices/{ids[0]}/operations', {'requestId': str(uuid4()), 'action': 'stop'}, 409)
                api('POST', f'workflows/runs/{active_run}/handoffs/{hid}/continue', {'requestId': str(uuid4())}, 202)
            if record['state'] in {'succeeded','failed','cancelled'}: break
            time.sleep(.2)
        assert record['state'] == 'succeeded' and len(handoffs) == 2, record
        artifacts = api('GET', f'workflows/runs/{active_run}/artifacts')['items']
        assert len(artifacts) == len({a['executionId'] for a in artifacts}) == 2
        assert [a['loopPath'][0]['iteration'] for a in artifacts] == [1, 2]
        (args.output / 'loop-run.json').write_text(json.dumps(record, ensure_ascii=False, indent=2))
        checks.append('M4 two iterations, separate handoffs/artifacts; busy lifecycle rejection')
        active_run = None
        assert proof(ids[1]) == before
        checks.append('second device data remains isolated through entire workflow')
    finally:
        if active_run:
            api('POST', 'workflows/runs/' + active_run + '/stop')
        cleanup = []
        for identifier in ids:
            try:
                d = wait_device(identifier)
                if d['control'] == 'recovery_required': command(identifier, 'recover')
                command(identifier, 'delete', True)
                cleanup.append({'deviceId': identifier, 'deleted': True})
            except Exception as error:
                cleanup.append({'deviceId': identifier, 'deleted': False, 'error': str(error)})
        (args.output / 'result.json').write_text(json.dumps({'checks': checks, 'cleanup': cleanup}, ensure_ascii=False, indent=2))
        if paused:
            subprocess.run(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'start', args.pause_reference_container], check=True, capture_output=True)
        client.close()
        process.terminate()
        process.wait(timeout=20)
    names = subprocess.check_output(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'ps', '-a', '--format', '{{.Names}}']).decode()
    volumes = subprocess.check_output(['limactl', 'shell', '--workdir=/tmp', 'autoflow-redroid', 'sudo', 'docker', 'volume', 'ls', '--format', '{{.Name}}']).decode()
    assert all(identifier not in names and identifier not in volumes for identifier in ids)
    assert len(checks) == 4 and all(item['deleted'] for item in cleanup)
    print(json.dumps({'checks': checks, 'cleanup': cleanup}, ensure_ascii=False))


if __name__ == '__main__':
    main()
