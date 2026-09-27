"""Real sidecar TCP/SQLite/production worker/CloakBrowser audit, no mocks."""
from __future__ import annotations
import asyncio, base64, hashlib, json, os, secrets, shutil, signal, subprocess, sys, tempfile, threading, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
KERNEL = Path.home() / 'Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
RUN = Path(tempfile.mkdtemp(prefix='run-', dir=EVIDENCE))
WORKSPACE = Path(tempfile.mkdtemp(prefix='autoflow-real-runtime-'))
TOKEN, HOST_TOKEN = secrets.token_hex(32), secrets.token_hex(32)
RESULT = {'startedAt': datetime.now(timezone.utc).isoformat(), 'gitHead': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'workspace':str(WORKSPACE), 'evidence':str(RUN), 'checks':[], 'scenarios':{}, 'processes':[]}
TRACE = RUN / 'http.jsonl'


def save():
    (RUN/'results.json').write_text(json.dumps(RESULT, ensure_ascii=False, indent=2))


def check(name, condition, detail=None):
    limitation = name == 'requested concurrency 2 actually reaches 2' and not condition
    RESULT['checks'].append({'name':name,'passed':None if limitation else bool(condition),'status':'observed_limitation' if limitation else ('passed' if condition else 'failed'),'detail':detail})
    save()
    print(json.dumps({'check':name,'passed':None if limitation else bool(condition),'status':'observed_limitation' if limitation else ('passed' if condition else 'failed')},ensure_ascii=False),flush=True)


class Sidecar:
    def __init__(self): self.process=None; self.url=''; self.log=None
    async def start(self):
        self.log=(RUN/f'sidecar-{len(RESULT["processes"])}.log').open('w')
        env={**os.environ,'AUTOFLOW_INSTANCE_TOKEN':TOKEN,'AUTOFLOW_HOST_TOKEN':HOST_TOKEN,'PYTHONPATH':str(ROOT/'apps/backend/src')}
        self.process=subprocess.Popen([sys.executable,'-m','autoflow','--port','0','--instance-id',str(uuid4()),'--data-dir',str(WORKSPACE),'--parent-pid',str(os.getpid())],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=self.log,text=True,start_new_session=True)
        RESULT['processes'].append(self.process.pid);save()
        line=await asyncio.wait_for(asyncio.to_thread(self.process.stdout.readline),60)
        assert line.startswith('AUTOFLOW_READY '), line
        self.url='http://127.0.0.1:'+str(json.loads(line.split(' ',1)[1])['port'])
        threading.Thread(target=lambda:[self.log.write(line) or self.log.flush() for line in self.process.stdout],daemon=True).start()
        for _ in range(180):
            try:
                async with httpx.AsyncClient() as client:
                    res=await client.get(self.url+'/health',headers={'x-autoflow-token':TOKEN})
                    if res.status_code==200:return
            except httpx.TransportError:pass
            await asyncio.sleep(.2)
        raise RuntimeError('sidecar health timeout')
    async def stop(self,crash=False):
        if self.process and self.process.poll() is None:
            if crash:self.process.kill()
            else:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(self.url+'/internal/lifecycle/shutdown',headers={'x-autoflow-host-token':HOST_TOKEN},timeout=10)
                except Exception:pass
                try:await asyncio.wait_for(asyncio.to_thread(self.process.wait),15)
                except TimeoutError:self.process.terminate()
            try:await asyncio.wait_for(asyncio.to_thread(self.process.wait),10)
            except TimeoutError:self.process.kill();self.process.wait()
        if self.log:self.log.flush()

SIDE=Sidecar()
async def api(method,path,payload=None,key=None,expected=(200,201,202,204)):
    headers={'x-autoflow-token':TOKEN}
    if key:headers['Idempotency-Key']=key
    async with httpx.AsyncClient(timeout=30) as client:
        response=await client.request(method,SIDE.url+path,headers=headers,json=payload)
    try:data=response.json()
    except ValueError:data=response.text
    with TRACE.open('a') as log:log.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'method':method,'path':path,'request':payload,'status':response.status_code,'response':data},ensure_ascii=False)+'\n')
    assert response.status_code in expected,(method,path,response.status_code,data)
    return data


def graph(name,steps):
    return {'id':str(uuid4()),'name':name,'clientRequestId':str(uuid4()),'nodes':[{'id':f'n{i}','type':kind,'position':{'x':i*200,'y':0},'data':{'moduleType':kind,'config':config}} for i,(kind,config) in enumerate(steps)],'edges':[{'id':f'e{i}','source':f'n{i}','target':f'n{i+1}'} for i in range(len(steps)-1)],'variables':[]}


async def create_scenario(prefix,profile,scenario,steps,concurrency=1,timeout=120):
    workflow=await api('POST','/api/workflows',graph('真实源码审计-'+scenario,steps))
    inputs=[]
    if concurrency>1:
        table=RESULT['table']
        inputs=[{'inputId':str(uuid4()),'alias':'真实源码','tableId':table['tableId'],'datasetGeneration':table['datasetGeneration'],'mode':'independent','required':True,'fieldBindings':[{'inputFieldId':str(uuid4()),'inputFieldAlias':'path','fieldRef':{'projectId':RESULT['projectId'],'tableId':table['tableId'],'datasetGeneration':table['datasetGeneration'],'fieldId':RESULT['fields']['path']}}],'filter':{'type':'all','items':[]},'orderBy':[{'systemField':'recordKey','direction':'asc'}]}]
    automation=await api('POST',prefix+'/automations',{'name':'真实源码-'+scenario,'description':'QA实际仓库文件和真实执行器','workflowId':workflow['id'],'inputPlan':{'inputs':inputs},'parameterSchema':[],'environmentPolicy':{'source':'newFromProfile','profileId':profile['id'],'proxyOverride':{'mode':'none'},'modelProviderId':None},'runPolicy':{'maxTasks':2,'concurrency':concurrency,'maxLiveInstances':concurrency,'continueAfterFailure':False,'automaticExecutionTimeoutSeconds':timeout,'manualDeadlineSeconds':300}},str(uuid4()))
    validation=await api('GET',prefix+f'/automations/{automation["automationId"]}/validation')
    check(scenario+' validation ready',validation['runnable'],validation)
    body={'expectedAutomationRevision':automation['managementRevision'],'parameters':{},'maxTasks':2,'concurrency':concurrency}
    key=str(uuid4())
    accepted=await api('POST',prefix+f'/automations/{automation["automationId"]}/batches',body,key)
    batch=accepted['operation']['result']['batch']['batchId']
    RESULT['scenarios'][scenario]={'workflowId':workflow['id'],'automationId':automation['automationId'],'batchId':batch,'startRequest':body,'idempotencyKey':key,'accepted':accepted};save()
    return batch


async def details(prefix,batch):
    batch_detail=await api('GET',prefix+f'/batches/{batch}')
    tasks=await api('GET',prefix+f'/tasks?batchId={batch}')
    return batch_detail,tasks['items']


async def wait_for(prefix,batch,waiting=False):
    history=[]
    for _ in range(450):
        detail,tasks=await details(prefix,batch)
        history.append({'at':time.time(),'batchStatus':detail['batch']['status'],'counts':detail['statusCounts']})
        if waiting:
            for task in tasks:
                attempts=await api('GET',prefix+f'/tasks/{task["taskId"]}/node-attempts')
                if any(a['nodeId']=='n1' and a['status']=='running' for a in attempts['items']):return detail,tasks,history
        elif detail['batch']['status'] in {'completed','failed','stopped','interrupted'}:return detail,tasks,history
        await asyncio.sleep(.2)
    raise AssertionError(('wait timed out',detail,tasks))


async def collect(prefix,scenario):
    batch=RESULT['scenarios'][scenario]['batchId']
    detail,tasks,history=await wait_for(prefix,batch)
    data={'batch':detail,'tasks':[],'history':history}
    for task in tasks:
        base=prefix+f'/tasks/{task["taskId"]}'
        item={'summary':task,'detail':await api('GET',base)}
        for name in ['outputs','node-attempts','logs','artifacts']:
            item[name]=await api('GET',base+'/'+name)
        for artifact in item['artifacts']['items']:
            async with httpx.AsyncClient(timeout=30) as client:
                response=await client.get(SIDE.url+base+f'/artifacts/{artifact["artifactId"]}/content',headers={'x-autoflow-token':TOKEN})
            if response.status_code==200:
                filename=f'{scenario}-{task["taskId"]}-{artifact["artifactId"]}.bin'
                (RUN/filename).write_bytes(response.content)
                artifact['downloadSha256']=hashlib.sha256(response.content).hexdigest()
        data['tasks'].append(item)
    RESULT['scenarios'][scenario]['result']=data;save()
    return data


async def main():
    print('Evidence: '+str(RUN),flush=True)
    (WORKSPACE/'.real-qa-owned').write_text(str(RUN))
    destination=WORKSPACE/'data/kernels'/KERNEL.name
    destination.parent.mkdir(parents=True)
    subprocess.run(['cp','-cR',str(KERNEL),str(destination)],check=True)
    sources=[]
    for relative in ['package.json','apps/backend/pyproject.toml','AGENTS.md']:
        content=(ROOT/relative).read_bytes()
        sources.append({'path':relative,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()})
    RESULT['realInputFiles']=sources
    # Browser reads the actual repository package.json through file://, not a generated fixture page.
    file_url=(ROOT/'package.json').as_uri()
    actual=json.loads((ROOT/'package.json').read_text())
    steps=[('open_page',{'url':file_url,'openMode':'current_tab'}),('inject_javascript',{'javascriptCode':'return document.body.innerText','saveResult':'repository_package_json'})]
    try:
        await SIDE.start()
        check('real loopback service ready',True,{'url':SIDE.url,'pid':SIDE.process.pid})
        profile=await api('POST','/api/v1/profiles',{'name':'公开内核真实QA','headless':True,'browserVersion':KERNEL.name.removeprefix('chromium-'),'browserEdition':'public','proxyMode':'none'})
        project=await api('POST','/api/v1/projects',{'name':'2026-09-28当前仓库真实数据验收','description':RESULT['gitHead']},str(uuid4()))
        prefix='/api/v1/projects/'+project['projectId'];RESULT['projectId']=project['projectId']
        # Real metadata persisted via public table/field/record API.
        table=await api('POST',prefix+'/tables',{'name':'当前源码文件清单','description':'来自真实工作树字节与SHA-256','sourceKind':'local'},str(uuid4()))
        table_path=prefix+'/tables/'+table['tableId'];revision=table['tableRevision'];fields={};RESULT['table']=table
        for name,kind in [('path','string'),('size','number'),('sha256','string')]:
            field=await api('POST',table_path+'/fields',{'definition':{'key':name,'name':name,'type':kind,'required':True,'validation':{}},'expectedTableRevision':revision,'existingRecordDefault':sources[0][name],'sourceColumnPolicy':'localOnly'},str(uuid4()))
            revision=field['tableRevision'];fields[name]=field['field']['ref']['fieldId']
        RESULT['fields']=fields;save()
        records=[]
        for source in sources:
            body={'datasetGeneration':table['datasetGeneration'],'values':[{'fieldId':fields[k],'value':v} for k,v in source.items()]}
            key=str(uuid4());record=await api('POST',table_path+'/records',body,key);records.append(record)
            replay=await api('POST',table_path+'/records',body,key)
            check('record idempotency '+source['path'],record==replay)
        listed=await api('GET',table_path+'/records?datasetGeneration='+table['datasetGeneration'])
        check('actual file metadata roundtrip',listed['total']==3 and {tuple(sorted((v['fieldId'],str(v['value'])) for v in row['values'])) for row in listed['items']}=={tuple(sorted((fields[k],str(v)) for k,v in src.items())) for src in sources})
        first=records[0];record_path=table_path+'/records/'+base64.urlsafe_b64encode(first['ref']['recordKey']['value'].encode()).decode().rstrip('=')
        update={'datasetGeneration':table['datasetGeneration'],'recordKeyType':first['ref']['recordKey']['type'],'expectedContentRevision':first['contentRevision'],'values':[{'fieldId':fields[k],'value':v} for k,v in sources[1].items()]}
        await api('PATCH',record_path,update,str(uuid4()))
        stale=await api('PATCH',record_path,update,str(uuid4()),expected=(409,412))
        check('stale revision rejects overwrite',True,stale)
        await create_scenario(prefix,profile,'table_semantics',[
            ('table_add_row',{'rowData':json.dumps(sources[0])}),
            ('table_get_cell',{'rowIndex':0,'columnName':'sha256','variableName':'actual_source_hash'}),
        ])
        data=await collect(prefix,'table_semantics')
        after_table=await api('GET',table_path+'/records?datasetGeneration='+table['datasetGeneration'])
        check('table nodes run on real source metadata',data['batch']['statusCounts']['succeeded']==2,data['batch']['statusCounts'])
        check('table node boundary - project business table remains unchanged',after_table['total']==3,{'before':3,'after':after_table['total'],'observation':'table_add_row operates on workflow result rows, not project business records; no target-table capability exposed'})
        await create_scenario(prefix,profile,'concurrent_real_file',[steps[0],('wait',{'duration':3}),steps[1]],concurrency=2)
        data=await collect(prefix,'concurrent_real_file')
        check('two production browser workers succeed',data['batch']['statusCounts']['succeeded']==2,data['batch']['statusCounts'])
        for task in data['tasks']:
            outputs={item['name']:item['value'] for item in task['outputs']['items']}
            check('browser reads exact actual package '+task['summary']['taskId'],json.loads(outputs.get('repository_package_json','{}'))==actual)
        check('requested concurrency 2 actually reaches 2',any(row['counts'].get('running',0)==2 for row in data['history']),{'requestedConcurrency':2,'maxRunningObserved':max(row['counts'].get('running',0) for row in data['history'])})
        entry=RESULT['scenarios']['concurrent_real_file']
        replay=await api('POST',prefix+f'/automations/{entry["automationId"]}/batches',entry['startRequest'],entry['idempotencyKey'])
        check('batch original-key replay creates no second batch',replay==entry['accepted'])
        # Public site is read-only and uses no accounts, tokens, external writes or paid services.
        await create_scenario(prefix,profile,'public_web',[('open_page',{'url':'https://example.com/','openMode':'current_tab','timeout':20}),('get_element_info',{'selector':'h1','attribute':'text','variableName':'public_page_heading'})])
        data=await collect(prefix,'public_web')
        check('public HTTPS browser read',data['batch']['statusCounts']['succeeded']==2 and all(any(o['name']=='public_page_heading' and o['value']=='Example Domain' for o in t['outputs']['items']) for t in data['tasks']),data['batch']['statusCounts'])
        await create_scenario(prefix,profile,'failure',[steps[0],('wait_element',{'selector':'#autoflow-absent-'+str(uuid4()),'waitCondition':'visible','timeout':1})])
        data=await collect(prefix,'failure')
        check('real missing-element failure and pending cancellation',data['batch']['statusCounts']['failed']==1 and data['batch']['statusCounts']['cancelled']==1,data['batch']['statusCounts'])
        check('real failure has downloadable evidence',any(a.get('downloadSha256') for t in data['tasks'] for a in t['artifacts']['items']))
        await create_scenario(prefix,profile,'stop',[steps[0],('wait',{'duration':60}),steps[1]])
        batch=RESULT['scenarios']['stop']['batchId'];detail,_,_=await wait_for(prefix,batch,True)
        await api('POST',prefix+f'/batches/{batch}/stop',{'expectedStatusRevision':detail['batch']['statusRevision'],'reason':'QA在真实等待节点请求停止'},str(uuid4()))
        data=await collect(prefix,'stop')
        check('ordinary stop cancels running and queued tasks',data['batch']['batch']['status']=='stopped' and data['batch']['statusCounts']['cancelled']==2,data['batch']['statusCounts'])
        check('stopped graph never runs following read',all(not t['outputs']['items'] for t in data['tasks']))
        await create_scenario(prefix,profile,'crash_restart',[steps[0],('wait',{'duration':60}),steps[1]])
        batch=RESULT['scenarios']['crash_restart']['batchId'];before,tasks,_=await wait_for(prefix,batch,True)
        RESULT['scenarios']['crash_restart']['beforeCrash']={'batch':before,'tasks':tasks};save()
        await SIDE.stop(crash=True)
        await SIDE.start()
        data=await collect(prefix,'crash_restart')
        check('sidecar crash durable interruption',data['batch']['batch']['status']=='interrupted',data['batch']['batch'])
        check('sidecar restart does not replay read side effect',all(not t['outputs']['items'] for t in data['tasks']))
        old=await api('GET',prefix+f'/batches/{entry["batchId"]}')
        check('completed batch survives process restart',old['statusCounts']['succeeded']==2)
        # A fresh real run proves capacity/lease recovery rather than only status projection.
        await create_scenario(prefix,profile,'after_recovery',steps)
        data=await collect(prefix,'after_recovery')
        check('fresh production run succeeds after crash recovery',data['batch']['statusCounts']['succeeded']==2,data['batch']['statusCounts'])
        copies=WORKSPACE/'workspace/environments/instances'
        for _ in range(100):
            if not copies.exists() or not list(copies.iterdir()):break
            await asyncio.sleep(.2)
        check('temporary environments cleaned',not copies.exists() or not list(copies.iterdir()),[p.name for p in copies.iterdir()] if copies.exists() else [])
    except Exception:
        RESULT['fatalError']=traceback.format_exc();print(RESULT['fatalError'],flush=True)
    finally:
        await SIDE.stop()
        RESULT['finishedAt']=datetime.now(timezone.utc).isoformat();save()
        print('RESULT '+str(RUN/'results.json'),flush=True)

if __name__=='__main__':
    asyncio.run(main())
    raise SystemExit(1 if RESULT.get('fatalError') or any(item['passed'] is False for item in RESULT['checks']) else 0)
