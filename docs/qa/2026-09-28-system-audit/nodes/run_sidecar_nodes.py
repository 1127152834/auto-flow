"""Four previously uncovered node contracts through real isolated sidecar/worker/Gateways.
Only this process's temporary share paths and newly allocated ports are used.
"""
import asyncio, hashlib, json, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path
from uuid import uuid4
import httpx
import run_real_nodes as q

NAME='补充 真实 sidecar 文件共享与 Webhook 契约'
q.RESULTS[:]=[r for r in json.loads((q.OUT/'results.json').read_text())['results'] if r['name'] != NAME]
RECORD={'source':str(q.SOURCES[0].relative_to(q.ROOT)), 'sourceSha256':q.ROWS[0]['sha256'],'requests':[],'checks':[]}
TOKEN,HOST_TOKEN=secrets.token_hex(32),secrets.token_hex(32)

def save(): (q.OUT/'sidecar-results.json').write_text(json.dumps(RECORD,ensure_ascii=False,indent=2)+'\n')
def check(name, condition, details=None):
    RECORD['checks'].append({'name':name,'passed':bool(condition),'details':details});save()
    assert condition,(name,details)

def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

async def main():
    process=None;log=None;error=None;client=None;url='';started=time.monotonic();executed_types=set()
    with tempfile.TemporaryDirectory(prefix='autoflow-sidecar-nodes-') as raw:
        workspace=Path(raw);shared=workspace/'repo share';shared.mkdir();source=shared/'package.json';shutil.copy2(q.SOURCES[0],source)
        kernel=Path.home()/'Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
        destination=workspace/'data/kernels'/kernel.name
        destination.parent.mkdir(parents=True)
        subprocess.run(['cp','-cR',str(kernel),str(destination)],check=True)
        RECORD['kernel']={'source':str(kernel),'copyMode':'APFS clone of actual installed kernel; profile validation only, no browser launch'}
        folder_port=free_port();file_port=free_port()
        while folder_port==file_port:file_port=free_port()
        RECORD['ports']={'folder':folder_port,'file':file_port}
        async def request(method,path,body=None,headers=None,expected=(200,201,202,204),authenticated=True):
            h={'x-autoflow-token':TOKEN} if authenticated else {}
            h.update(headers or {})
            response=await client.request(method,url+path,headers=h,json=body)
            try:result=response.json()
            except ValueError:result=response.text
            RECORD['requests'].append({'method':method,'path':path,'request':body,'status':response.status_code,'response':result});save()
            assert response.status_code in expected,(path,response.status_code,result)
            return result
        try:
            log=(q.OUT/'sidecar.log').open('w')
            process=subprocess.Popen([sys.executable,'-m','autoflow','--port','0','--instance-id',str(uuid4()),'--data-dir',str(workspace),'--parent-pid',str(os.getpid())],cwd=q.ROOT,env={**os.environ,'PYTHONPATH':str(q.ROOT/'apps/backend/src'),'AUTOFLOW_INSTANCE_TOKEN':TOKEN,'AUTOFLOW_HOST_TOKEN':HOST_TOKEN},stdout=subprocess.PIPE,stderr=log,text=True,start_new_session=True)
            line=await asyncio.wait_for(asyncio.to_thread(process.stdout.readline),60)
            assert line.startswith('AUTOFLOW_READY '),line
            ready=json.loads(line.split(' ',1)[1]);url='http://127.0.0.1:'+str(ready['port']);RECORD['sidecarPort']=ready['port']
            def drain():
                for line in process.stdout:log.write(line);log.flush()
            threading.Thread(target=drain,daemon=True).start()
            client=httpx.AsyncClient(timeout=30,trust_env=False)
            await request('GET','/health')
            profile=await request('POST','/api/v1/profiles',{'name':'QA repository sharing only','headless':True,'browserVersion':'145.0.7632.109.2','browserEdition':'public','proxyMode':'none'})
            hook='qa-'+uuid4().hex
            steps=[('share_folder',{'folderPath':str(shared),'port':folder_port,'allowWrite':False}),('share_file',{'filePath':str(source),'port':file_port}),('webhook_trigger',{'webhookId':hook,'method':'POST','timeout':30,'validateHeaders':json.dumps({'x-source-sha256':q.ROWS[0]['sha256']}),'validateParams':json.dumps({'source':'package.json'}),'responseBody':json.dumps({'source':q.PKG['name']}),'responseStatus':200,'saveToVariable':'webhook_data'}),('json_parse',{'sourceVariable':'webhook_data','jsonPath':'$.body.sha256','variableName':'sha'}),('print_log',{'logMessage':'${sha}'}),('stop_share',{'port':folder_port}),('stop_share',{'port':file_port})]
            document={'id':str(uuid4()),'name':'真实仓库文件共享与Webhook回调','clientRequestId':str(uuid4()),'nodes':[q.node(k,c,f'n{i}')|{'position':{'x':i*200,'y':0}} for i,(k,c) in enumerate(steps)],'edges':[{'id':f'e{i}','source':f'n{i}','target':f'n{i+1}'} for i in range(len(steps)-1)],'variables':[]}
            saved=await request('POST','/api/workflows',document)
            run_id='qa-'+uuid4().hex;RECORD['runId']=run_id;RECORD['workflowId']=saved['id']
            await request('POST',f'/api/workflows/{saved["id"]}/execute',{'runId':run_id,'documentId':saved['id'],'profileId':profile['id'],'headless':True})
            path=f'/api/triggers/webhook/{hook}'
            # A wrong-method callback proves the wait exists without consuming it.
            for _ in range(200):
                logs=await request('GET',f'/api/workflow-runs/{run_id}/logs?cursor=0&limit=100')
                if any(x.get('nodeId')=='n1' for x in logs['items']):break
                await asyncio.sleep(.05)
            await asyncio.sleep(.25)
            for port,download in [(folder_port,'/download/package.json'),(file_port,'/download')]:
                response=await client.get(f'http://127.0.0.1:{port}'+download)
                check('actual repository download '+str(port),response.status_code==200 and response.content==q.SOURCES[0].read_bytes(),{'status':response.status_code,'sha256':hashlib.sha256(response.content).hexdigest()})
            listing=await client.get(f'http://127.0.0.1:{folder_port}/api/list')
            check('folder listing contains actual package.json',listing.status_code==200 and 'package.json' in listing.text,{'status':listing.status_code})
            await request('GET',path,expected=(404,),authenticated=False)
            await request('POST',path+'?source=package.json',q.ROWS[0],expected=(403,),authenticated=False)
            answer=await request('POST',path+'?source=package.json',q.ROWS[0],{'x-source-sha256':q.ROWS[0]['sha256']},authenticated=False)
            check('valid callback custom response',answer=={'source':q.PKG['name']})
            for _ in range(300):
                run=await request('GET',f'/api/workflow-runs/{run_id}')
                if run['status'] in {'completed','failed','stopped','interrupted'}:break
                await asyncio.sleep(.05)
            check('all seven real nodes complete',run['status']=='completed',run)
            logs=await request('GET',f'/api/workflow-runs/{run_id}/logs?cursor=0&limit=100')
            results=await request('GET',f'/api/workflow-runs/{run_id}/results?cursor=0&limit=100')
            completed_ids={x['nodeId'] for x in results['items']}
            executed_types={kind for i,(kind,_) in enumerate(steps) if f'n{i}' in completed_ids}
            check('every node has persisted result',set(x['nodeId'] for x in results['items'])=={f'n{i}' for i in range(7)})
            check('webhook real payload reached log',any(x['nodeId']=='n4' and x['message']==q.ROWS[0]['sha256'] for x in logs['items']))
            await request('POST',path+'?source=package.json',q.ROWS[0],{'x-source-sha256':q.ROWS[0]['sha256']},expected=(404,),authenticated=False)
            for port in (folder_port,file_port):
                try:await client.get(f'http://127.0.0.1:{port}/',timeout=1);closed=False
                except httpx.TransportError:closed=True
                check('stop_share closed own port '+str(port),closed)
        except Exception as exc:
            error=repr(exc);RECORD['error']=error
        finally:
            if process and process.poll() is None:
                if client and url:
                    try:await client.post(url+'/internal/lifecycle/shutdown',headers={'x-autoflow-host-token':HOST_TOKEN})
                    except Exception:pass
                try:await asyncio.wait_for(asyncio.to_thread(process.wait),15)
                except TimeoutError:
                    process.terminate()
                    try:await asyncio.wait_for(asyncio.to_thread(process.wait),5)
                    except TimeoutError:process.kill();process.wait()
            if client:await client.aclose()
            if log:log.close()
            RECORD['processExited']=process is not None and process.poll() is not None;save()
    q.RESULTS.append({'name':NAME,'layer':'real isolated sidecar HTTP + SQLite + production worker + NetworkShareHost/webhook Gateway','moduleTypes':sorted(executed_types),'status':'fail' if error else 'pass','durationMs':round((time.monotonic()-started)*1000,2),'error':error,'httpEvidence':'sidecar-results.json'})
    q.save();print(json.dumps({'status':'fail' if error else 'pass','error':error,'checks':RECORD['checks']},ensure_ascii=False,indent=2))
    return error

if __name__=='__main__':raise SystemExit(1 if asyncio.run(main()) else 0)
