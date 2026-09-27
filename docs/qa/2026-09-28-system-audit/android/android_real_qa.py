"""Production Mac Android lifecycle over real sidecar HTTP; owns one UUID only."""
from __future__ import annotations
import hashlib, json, os, secrets, sqlite3, struct, subprocess, sys, tempfile, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
RUN=Path(tempfile.mkdtemp(prefix='run-',dir=OUT))
WORKSPACE=Path(tempfile.mkdtemp(prefix='autoflow-android-realqa-'))
DEVICE=str(uuid4());NAME='autoflow-android-'+DEVICE;VOLUME=NAME+'-data'
WORKSPACE_LABEL=hashlib.sha256(str((WORKSPACE/'workspace').resolve()).encode()).hexdigest()
TOKEN=secrets.token_hex(32);HOST_TOKEN=secrets.token_hex(32)
RESULT={'startedAt':datetime.now(timezone.utc).isoformat(),'gitHead':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'deviceId':DEVICE,'containerName':NAME,'volumeName':VOLUME,'workspace':str(WORKSPACE),'workspaceLabel':WORKSPACE_LABEL,'checks':[],'cleanup':{}}
PROCESS=None;CLIENT=None;CREATED=False

def save(): (RUN/'results.json').write_text(json.dumps(RESULT,ensure_ascii=False,indent=2))
def check(name,ok,detail=None):
    RESULT['checks'].append({'name':name,'passed':bool(ok),'detail':detail});save();print(json.dumps(RESULT['checks'][-1],ensure_ascii=False),flush=True)

def docker(*args):
    return subprocess.check_output(['limactl','shell','--workdir=/tmp','autoflow-redroid','sudo','docker',*args],timeout=30).decode()

def inventory():
    ids=docker('ps','-aq').split(); rows=json.loads(docker('inspect',*ids)) if ids else []
    return {'containers':[{'id':x['Id'],'name':x['Name'],'state':x['State']['Status'],'startedAt':x['State'].get('StartedAt'),'imageId':x['Image'],'memoryBytes':x['HostConfig'].get('Memory',0),'labels':x['Config'].get('Labels') or {}} for x in rows],'volumes':docker('volume','ls','--format','{{.Name}}').splitlines()}

def verify_owned():
    inv=inventory();mine=[x for x in inv['containers'] if x['name']=='/'+NAME]
    for obj in mine:
        assert obj['labels'].get('io.autoflow.android.workspace')==WORKSPACE_LABEL,obj
        assert obj['labels'].get('io.autoflow.android.device')==DEVICE,obj
    if VOLUME in inv['volumes']:
        obj=json.loads(docker('volume','inspect',VOLUME))[0]
        assert obj.get('Labels',{}).get('io.autoflow.android.workspace')==WORKSPACE_LABEL
        assert obj.get('Labels',{}).get('io.autoflow.android.device')==DEVICE
    return {'containerCount':len(mine),'volumeExists':VOLUME in inv['volumes'],'ownershipMatches':True}

def api(method,path,body=None,expected=(200,202)):
    response=CLIENT.request(method,path,json=body)
    try:data=response.json()
    except ValueError:data={'bytes':len(response.content),'sha256':hashlib.sha256(response.content).hexdigest()}
    with (RUN/'http.jsonl').open('a') as log:log.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'method':method,'path':path,'body':body,'status':response.status_code,'response':data},ensure_ascii=False)+'\n')
    assert response.status_code in expected,(response.status_code,data)
    return data

def wait_device(timeout=230):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        items=api('GET','/api/v1/android/devices')
        d=next((x for x in items if x['deviceId']==DEVICE),None)
        if d is None:return None
        if d.get('operation',{}).get('state')!='running':return d
        time.sleep(.5)
    raise TimeoutError('owned Android operation timed out')

def command(action,delete=False):
    ownership=verify_owned();assert ownership['ownershipMatches']
    body={'requestId':str(uuid4()),'action':action,'deleteData':delete}
    api('POST',f'/api/v1/android/devices/{DEVICE}/operations',body)
    d=wait_device()
    RESULT.setdefault('operations',[]).append({'action':action,'result':d});save()
    if d is not None:assert d.get('operation',{}).get('state')=='succeeded',d
    return d

try:
    print('Evidence: '+str(RUN),flush=True);save()
    (WORKSPACE/'.android-qa-owned').write_text(DEVICE)
    before=inventory();RESULT['before']=before;save()
    assert not any(DEVICE in x['name'] for x in before['containers']) and VOLUME not in before['volumes']
    info=json.loads(docker('info','--format','{{json .}}'))
    allocated=sum(x['memoryBytes'] for x in before['containers'] if x['state']=='running')
    check('existing runtime has isolated capacity',allocated+1536*1024**2<=info['MemTotal']-512*1024**2,{'cpuCount':info['NCPU'],'totalMemoryBytes':info['MemTotal'],'existingReservedBytes':allocated,'newMemoryMb':1536})
    if not RESULT['checks'][-1]['passed']:raise RuntimeError('NOT_RUN: insufficient isolated capacity')
    log=(RUN/'sidecar.log').open('w')
    env={**os.environ,'AUTOFLOW_INSTANCE_TOKEN':TOKEN,'AUTOFLOW_HOST_TOKEN':HOST_TOKEN,'PYTHONPATH':str(ROOT/'apps/backend/src')}
    PROCESS=subprocess.Popen([sys.executable,'-m','autoflow','--port','0','--instance-id',str(uuid4()),'--data-dir',str(WORKSPACE),'--parent-pid',str(os.getpid())],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=log,text=True,start_new_session=True)
    RESULT['sidecarPid']=PROCESS.pid;save()
    ready=PROCESS.stdout.readline();assert ready.startswith('AUTOFLOW_READY '),ready
    url='http://127.0.0.1:'+str(json.loads(ready.split(' ',1)[1])['port'])
    CLIENT=httpx.Client(base_url=url,headers={'x-autoflow-token':TOKEN},timeout=30,trust_env=False)
    for _ in range(100):
        try:
            if CLIENT.get('/health').status_code==200:break
        except httpx.TransportError:pass
        time.sleep(.2)
    environment=api('GET','/api/v1/android/environment');RESULT['environment']=environment;save()
    assert environment['available'] and len(environment['images'])==1,environment
    check('production Android runtime available via HTTP',True,environment)
    assert api('GET','/api/v1/android/devices')==[]
    body={'deviceId':DEVICE,'name':'QA 2026-09-28 真实隔离设备','imageId':environment['images'][0]['id'],'width':720,'height':1280,'dpi':320,'cpu':1,'memoryMb':1536,'start':False}
    CREATED=True
    api('POST','/api/v1/android/devices',body)
    d=wait_device();RESULT['created']=d;save()
    assert d and d['operation']['state']=='succeeded',d
    check('create stopped device with independent data',d['androidStatus']=='stopped',verify_owned())
    api('POST','/api/v1/android/devices',body)
    check('create same UUID and payload is idempotent',len(api('GET','/api/v1/android/devices'))==1)
    started=time.monotonic();d=command('start');RESULT['started']=d;save()
    check('start reaches real Android ready',d['androidStatus']=='ready',{'bootSeconds':round(time.monotonic()-started,3),'status':d['androidStatus']})
    response=CLIENT.get(f'/api/v1/android/devices/{DEVICE}/preview')
    assert response.status_code==200,(response.status_code,response.text)
    (RUN/'preview.png').write_bytes(response.content)
    dimensions=struct.unpack('>II',response.content[16:24])
    check('real Android PNG screenshot',response.content.startswith(b'\x89PNG\r\n\x1a\n') and dimensions==(720,1280),{'dimensions':dimensions,'bytes':len(response.content),'sha256':hashlib.sha256(response.content).hexdigest()})
    d=command('stop');RESULT['stopped']=d;save()
    check('stop preserves owned device and data',d['androidStatus']=='stopped',verify_owned())
except Exception:
    RESULT['error']=traceback.format_exc();print(RESULT['error'],flush=True)
    try:
        verify_owned()
        obj=json.loads(docker('inspect',NAME))[0]
        RESULT['failureDiagnostics']={'state':obj['State'],'imageId':obj['Image'],'memoryBytes':obj['HostConfig'].get('Memory'),'nanoCpus':obj['HostConfig'].get('NanoCpus'),'privileged':obj['HostConfig'].get('Privileged'),'mounts':[{'name':m.get('Name'),'destination':m.get('Destination'),'type':m.get('Type')} for m in obj.get('Mounts',[])],'logs':docker('logs','--tail','30',NAME)}
        print(json.dumps(RESULT['failureDiagnostics'],ensure_ascii=False),flush=True)
    except Exception:RESULT['failureDiagnosticError']=traceback.format_exc()
    save()
finally:
    if CREATED and CLIENT is not None:
        try:
            d=wait_device()
            if d is not None and d['control']=='recovery_required':d=command('recover')
            RESULT['cleanup']['beforeDeletion']=verify_owned();save()
            if d is not None:command('delete',True)
            RESULT['cleanup']['afterDeletion']=verify_owned()
            check('owned container and data removed',RESULT['cleanup']['afterDeletion']['containerCount']==0 and not RESULT['cleanup']['afterDeletion']['volumeExists'])
            check('deleted device absent from API list',not any(x['deviceId']==DEVICE for x in api('GET','/api/v1/android/devices')))
        except Exception:
            RESULT['cleanup']['error']=traceback.format_exc();print(RESULT['cleanup']['error'],flush=True)
    try:
        after=inventory();RESULT['after']=after
        check('preexisting containers unchanged',sorted(before['containers'],key=lambda x:x['id'])==sorted(after['containers'],key=lambda x:x['id']))
        check('preexisting volume set unchanged',sorted(before['volumes'])==sorted(after['volumes']))
    except Exception:RESULT['postInventoryError']=traceback.format_exc()
    if PROCESS is not None and PROCESS.poll() is None:
        try:CLIENT.post('/internal/lifecycle/shutdown',headers={'x-autoflow-host-token':HOST_TOKEN})
        except Exception:pass
        try:PROCESS.wait(timeout=20)
        except subprocess.TimeoutExpired:PROCESS.terminate();PROCESS.wait(timeout=10)
    if CLIENT is not None:CLIENT.close()
    RESULT['finishedAt']=datetime.now(timezone.utc).isoformat();save()
    print('RESULT '+str(RUN/'results.json'),flush=True)
    if RESULT.get('error') or RESULT['cleanup'].get('error') or any(not c['passed'] for c in RESULT['checks']):sys.exit(1)
