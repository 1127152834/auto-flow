"""Opt-in real registry transfer cut on an isolated Docker daemon in Lima."""
import argparse
import asyncio
import json
import os
import runpy
import secrets
import shlex
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
from autoflow.domain.android.ports import AndroidError
from autoflow.providers.android.mac_runtime import VM, docker, run

ROOT = Path(__file__).resolve().parents[4]
H = runpy.run_path(str(ROOT / 'docs/qa/android-management/scripts/restore-interruption-smoke.py'))
BASE = '/api/v1/android/management'
GUEST = r'''
import http.server,json,os,select,socket,subprocess,sys,threading,time
from pathlib import Path
root=Path(sys.argv[1]);root.mkdir(mode=0o700)
cut=threading.Event();lock=threading.Lock();received=0;faulted=False
class Proxy(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_CONNECT(self):
  global received,faulted
  if cut.is_set():self.send_error(503);return
  host,port=self.path.rsplit(':',1)
  if port!='443':self.send_error(403);return
  try:
   with socket.create_connection((host,443),timeout=15) as upstream:
    self.send_response(200);self.end_headers()
    while not cut.is_set():
     ready,_,_=select.select([self.connection,upstream],[],[],.1)
     for source in ready:
      data=source.recv(65536)
      if not data:return
      if source is upstream:
       with lock:
        received+=len(data)
        if not faulted and received>=4*1024**2:
         faulted=True
         partials=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size} for p in (root/'containerd-data').rglob('data') if p.is_file() and '/ingest/' in str(p)]
         (root/'fault.json').write_text(json.dumps({'upstreamBytes':received,'fault':'close TLS tunnels; reject subsequent proxy connects','hostAtCut':host,'partialFiles':partials}))
         cut.set();return
      (self.connection if source is upstream else upstream).sendall(data)
  except (OSError,ValueError):return
proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),Proxy)
threading.Thread(target=proxy.serve_forever,daemon=True).start()
(root/'daemon.json').write_text(json.dumps({'features':{'containerd-snapshotter':True}}))
containerd_log=(root/'containerd.log').open('wb')
containerd=subprocess.Popen(['containerd','--address='+str(root/'containerd.sock'),'--root='+str(root/'containerd-data'),'--state='+str(root/'containerd-state')],stdout=containerd_log,stderr=containerd_log,start_new_session=True)
for _ in range(100):
 if (root/'containerd.sock').exists():break
 if containerd.poll() is not None:raise RuntimeError('isolated containerd startup failed')
 time.sleep(.1)
args=['dockerd','--containerd='+str(root/'containerd.sock'),'--config-file='+str(root/'daemon.json'),'--host=unix://'+str(root/'docker.sock'),'--data-root='+str(root/'data'),'--exec-root='+str(root/'exec'),'--pidfile='+str(root/'docker.pid'),'--bridge=none','--iptables=false','--ip6tables=false','--ip-forward=false','--ip-masq=false','--max-download-attempts=1','--max-concurrent-downloads=1','--no-proxy=localhost,127.0.0.1','--https-proxy=http://127.0.0.1:'+str(proxy.server_port),'--http-proxy=http://127.0.0.1:'+str(proxy.server_port)]
with (root/'daemon.log').open('wb') as log:
 process=subprocess.Popen(args,stdout=log,stderr=log,start_new_session=True)
try:
 (root/'owner.json').write_text(json.dumps({'daemonPid':process.pid,'containerdPid':containerd.pid,'supervisorPid':os.getpid(),'proxyPort':proxy.server_port}))
 print(json.dumps({'root':str(root),'daemonPid':process.pid,'containerdPid':containerd.pid}),flush=True)
 while process.poll() is None and not (root/'stop').exists():
  if (root/'resume').exists():
   cut.clear();(root/'resume').unlink();(root/'resumed').touch()
  time.sleep(.2)
finally:
 proxy.shutdown()
 if process.poll() is None:
  process.terminate()
  try:process.wait(20)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 if containerd.poll() is None:
  containerd.terminate()
  try:containerd.wait(20)
  except subprocess.TimeoutExpired:containerd.kill();containerd.wait()
 containerd_log.close()
 print('stopped',flush=True)
'''


async def vm(*args, **kwargs):
    return await run(['limactl', 'shell', '--workdir=/tmp', VM, 'sudo', *args], **kwargs)


def worker():
    from autoflow.__main__ import main
    from autoflow.providers.android import mac_runtime

    guest = os.environ['AUTOFLOW_QA_DOCKER_ROOT']
    async def isolated_docker(*args, timeout=30, input_data=None):
        argv = ['docker', '--host', 'unix://' + guest + '/docker.sock', *args]
        if args[:1] == ('pull',):
            calls = Path(os.environ['AUTOFLOW_QA_PULL_CALLS'])
            calls.write_text((calls.read_text() if calls.exists() else '') + args[1] + '\n')
            argv = ['bash', '-o', 'pipefail', '-c', shlex.join(argv) + ' | tee ' + shlex.quote(guest + '/pull-progress.log')]
        return await vm(*argv, timeout=timeout, input_data=input_data)
    mac_runtime.docker = isolated_docker
    sys.argv.remove('--worker')
    main()


async def start(workspace, guest):
    token = secrets.token_hex(32)
    env = {**os.environ, 'AUTOFLOW_INSTANCE_TOKEN': token, 'AUTOFLOW_HOST_TOKEN': secrets.token_hex(32), 'AUTOFLOW_QA_DOCKER_ROOT': guest, 'AUTOFLOW_QA_PULL_CALLS': str(workspace / 'pull-calls.txt')}
    with (workspace / 'sidecar.log').open('ab') as log:
        process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()), '--worker', '--instance-id', str(uuid4()), '--data-dir', str(workspace), '--port', '0', env=env, stdout=asyncio.subprocess.PIPE, stderr=log, start_new_session=True)
    client = None
    try:
        line = await asyncio.wait_for(process.stdout.readline(), 45)
        assert line.startswith(b'AUTOFLOW_READY '), line
        port = json.loads(line.removeprefix(b'AUTOFLOW_READY '))['port']
        client = httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', headers={'x-autoflow-token': token}, timeout=300, trust_env=False)
        async with asyncio.timeout(30):
            while True:
                try:
                    if (await client.get(BASE + '/images')).status_code == 200:
                        return process, client
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(.1)
    except BaseException:
        await H['kill_owned_tree'](process)
        if client:
            await client.aclose()
        raise


async def exercise(output):
    workspace = Path(tempfile.mkdtemp(prefix='autoflow-network-cut-'))
    guest = '/tmp/autoflow-network-cut-' + uuid4().hex
    report = {'status': 'started', 'workspace': str(workspace), 'guestRoot': guest, 'scope': 'production HTTP/services/Mac adapter; Docker command transport selects dedicated real daemon; real TLS proxy fault; no mock response'}
    process = client = supervisor = None
    expect = H['expect']
    before = (await docker('ps', '-aq')).decode().splitlines()
    original_info = json.loads(await docker('info', '--format', '{{json .}}'))
    metadata = json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]
    reference = next(x for x in metadata['RepoDigests'] if x.startswith('redroid/redroid@sha256:'))
    report.update(reference=reference, existingImageId=metadata['Id'], existingContainerIds=before)
    output.write_text(json.dumps(report))
    compile(GUEST, '<guest supervisor>', 'exec')
    try:
        supervisor = await asyncio.create_subprocess_exec('limactl', 'shell', '--workdir=/tmp', VM, 'sudo', 'python3', '-u', '-c', GUEST, guest, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
        line = await asyncio.wait_for(supervisor.stdout.readline(), 30)
        assert line, (await supervisor.stderr.read()).decode()[:1000]
        report['supervisor'] = json.loads(line)
        async with asyncio.timeout(60):
            while True:
                try:
                    info = json.loads(await vm('docker', '--host', 'unix://' + guest + '/docker.sock', 'info', '--format', '{{json .}}', timeout=5))
                    assert info['DockerRootDir'] == guest + '/data'
                    assert info['Driver'] == original_info['Driver'] and info['DriverStatus'] == original_info['DriverStatus']
                    report['isolatedStorageDriver'] = info['Driver']
                    report['isolatedStorageDriverStatus'] = info['DriverStatus']
                    break
                except AndroidError:
                    await asyncio.sleep(.2)
        assert not (await vm('docker', '--host', 'unix://' + guest + '/docker.sock', 'image', 'ls', '-q')).strip()
        process, client = await start(workspace, guest)
        request_id = str(uuid4())
        body = {'requestId': request_id, 'reference': reference, 'allowUnknownDiskEstimate': True}
        response = await client.post(BASE + '/image-pulls', json=body)
        report.update(responseStatus=response.status_code, responseBody=response.json())
        report['fault'] = json.loads(await vm('cat', guest + '/fault.json'))
        progress = (await vm('cat', guest + '/pull-progress.log')).decode()
        (workspace / 'pull-progress.log').write_text(progress)
        assert 'Pulling fs layer' in progress and 'Pull complete' not in progress, progress
        assert any(item['bytes'] > 1024**2 for item in report['fault']['partialFiles']), report['fault']
        assert response.status_code == 502 and response.json()['error']['code'] == 'ANDROID_COMMAND_FAILED'
        report['partialDownloadObserved'] = True
        record = expect(await client.get(BASE + '/operations/by-request/' + request_id), 200)
        assert record['state'] == 'failed' and record['resultCode'] == 'ANDROID_COMMAND_FAILED', record
        assert expect(await client.get(BASE + '/images'), 200)['items'] == []
        replay = expect(await client.post(BASE + '/image-pulls', json=body), 202)
        assert replay['state'] == 'failed' and replay['operationId'] == record['operationId']
        await H['stop_server'](process, client)
        process = client = None
        process, client = await start(workspace, guest)
        restarted = expect(await client.get(BASE + '/operations/by-request/' + request_id), 200)
        assert restarted['state'] == 'failed' and restarted['operationId'] == record['operationId']
        replay = expect(await client.post(BASE + '/image-pulls', json=body), 202)
        assert replay['state'] == 'failed'
        assert (workspace / 'pull-calls.txt').read_text().splitlines() == [reference]
        report.update(operation=record, afterRestart=restarted, actualPullCallsBeforeRetry=1, noRegisteredImageAtFailure=True)
        await vm('touch', guest + '/resume')
        async with asyncio.timeout(10):
            while True:
                try:
                    await vm('test', '-e', guest + '/resumed')
                    break
                except AndroidError:
                    await asyncio.sleep(.1)
        new_request = {**body, 'requestId': str(uuid4())}
        recovered = expect(await client.post(BASE + '/image-pulls', json=new_request), 202)
        assert recovered['state'] == 'succeeded', recovered
        page = expect(await client.get(BASE + '/images'), 200)
        assert len(page['items']) == 1 and page['items'][0]['imageId'] == metadata['Id'], page
        assert (workspace / 'pull-calls.txt').read_text().splitlines() == [reference, reference]
        image = page['items'][0]
        deleted = expect(await client.request('DELETE', BASE + '/images/' + image['id'], json={'requestId': str(uuid4()), 'expectedRevision': image['revision'], 'deleteContent': True}), 200)
        assert deleted['state'] == 'deleted', deleted
        assert not (await vm('docker', '--host', 'unix://' + guest + '/docker.sock', 'image', 'ls', '-q')).strip()
        report.update(recovery=recovered, recoveredImageId=image['imageId'], actualPullCalls=2, ownedImageDeleted=True, status='passed')
    except BaseException as error:
        report.update(status='failed', errorType=type(error).__name__, error=str(error)[:500])
        raise
    finally:
        if process and client:
            await H['stop_server'](process, client)
        if supervisor and report.get('supervisor'):
            await vm('touch', guest + '/stop')
            await asyncio.wait_for(supervisor.wait(), 30)
            report['daemonLog'] = (await vm('cat', guest + '/daemon.log')).decode()[-10000:]
            assert (await vm('test', '!', '-e', guest + '/docker.pid')) == b''
            for key in ('daemonPid', 'containerdPid'):
                await vm('test', '!', '-d', '/proc/' + str(report['supervisor'][key]))
            await vm('python3', '-c', 'import shutil,sys;from pathlib import Path;p=Path(sys.argv[1]);assert p.parent==Path("/tmp") and p.name.startswith("autoflow-network-cut-");shutil.rmtree(p)', guest)
            report['isolatedDaemonRemoved'] = True
        after = (await docker('ps', '-aq')).decode().splitlines()
        assert after == before
        assert json.loads(await docker('image', 'inspect', 'redroid/redroid:13.0.0_64only-latest'))[0]['Id'] == metadata['Id']
        report['existingResourcesUnchanged'] = True
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'daemonLog'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if '--worker' in sys.argv:
        worker()
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--allow-image-pull', action='store_true', required=True)
        parser.add_argument('--output', type=Path, required=True)
        args = parser.parse_args()
        asyncio.run(exercise(args.output))
