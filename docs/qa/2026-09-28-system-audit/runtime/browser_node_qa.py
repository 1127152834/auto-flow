"""Additional read-only browser nodes, real HTTP/worker/CloakBrowser and real sources."""
import asyncio, importlib.util, json, hashlib, struct, subprocess, time, traceback
from pathlib import Path
from uuid import uuid4

spec=importlib.util.spec_from_file_location('qa',Path(__file__).with_name('real_runtime_qa.py'))
qa=importlib.util.module_from_spec(spec);spec.loader.exec_module(qa)
public='https://example.com/'
source=(qa.ROOT/'apps/backend/pyproject.toml').as_uri()
package=(qa.ROOT/'package.json').as_uri()
steps=[
 ('open_page',{'url':public,'openMode':'current_tab','timeout':20}),
 ('wait_page_load',{'waitUntil':'load','timeout':10}),
 ('page_load_complete',{'checkState':'domcontentloaded','saveToVariable':'public_loaded'}),
 ('wait_element',{'selector':'h1','waitCondition':'visible','waitTimeout':10}),
 ('get_element_info',{'selector':'h1','attribute':'text','variableName':'heading'}),
 ('element_exists',{'selector':'h1'}),
 ('element_visible',{'selector':'h1'}),
 ('get_child_elements',{'parentSelector':'body','variableName':'body_children'}),
 ('get_sibling_elements',{'elementSelector':'h1','siblingType':'all','variableName':'heading_siblings'}),
 ('hover_element',{'selector':'h1','hoverDuration':0}),
 ('inject_javascript',{'javascriptCode':'return {title:document.title,heading:document.querySelector("h1").textContent,url:location.href}','saveResult':'public_dom'}),
 ('screenshot',{'screenshotType':'viewport','fileNamePattern':'real-example-domain','variableName':'public_screenshot'}),
 ('open_page',{'url':source,'openMode':'new_tab'}),
 ('switch_tab',{'switchMode':'first','saveTitleVariable':'first_title','saveIndexVariable':'first_index'}),
 ('switch_tab',{'switchMode':'last','saveUrlVariable':'last_url','saveIndexVariable':'last_index'}),
 ('use_opened_page',{'pageIdentifier':source,'matchMode':'url'}),
 ('refresh_page',{'waitUntil':'load'}),
 ('scroll_page',{'direction':'down','distance':400,'scrollMode':'javascript'}),
 ('inject_javascript',{'javascriptCode':'return {scrollY:window.scrollY,body:document.body.innerText,url:location.href}','saveResult':'scrolled_source'}),
 ('open_page',{'url':package,'openMode':'current_tab'}),
 ('go_back',{'waitUntil':'load'}),
 ('inject_javascript',{'javascriptCode':'return {url:location.href,text:document.body.innerText}','saveResult':'back_source'}),
 ('go_forward',{'waitUntil':'load'}),
 ('inject_javascript',{'javascriptCode':'return {url:location.href,text:document.body.innerText}','saveResult':'forward_source'}),
 ('switch_tab',{'switchMode':'first'}),
 ('close_page',{}),
]

async def main():
 print('Evidence: '+str(qa.RUN),flush=True)
 qa.RESULT['kind']='real_browser_node_coverage';qa.RESULT['nodeTypes']=sorted(set(kind for kind,_ in steps));qa.RESULT['steps']=[{'nodeId':f'n{i}','type':kind,'config':config} for i,(kind,config) in enumerate(steps)]
 try:
  dest=qa.WORKSPACE/'data/kernels'/qa.KERNEL.name;dest.parent.mkdir(parents=True)
  subprocess.run(['cp','-cR',str(qa.KERNEL),str(dest)],check=True)
  await qa.SIDE.start()
  profile=await qa.api('POST','/api/v1/profiles',{'name':'只读浏览器节点真实验收','headless':True,'browserVersion':qa.KERNEL.name.removeprefix('chromium-'),'browserEdition':'public','proxyMode':'none'})
  project=await qa.api('POST','/api/v1/projects',{'name':'浏览器节点只读真实场景','description':qa.RESULT['gitHead']},str(uuid4()))
  prefix='/api/v1/projects/'+project['projectId'];qa.RESULT['projectId']=project['projectId']
  graph=qa.graph('真实公开网页和源码文件浏览器节点',steps)
  for i,(kind,_) in enumerate(steps):
   if kind in {'element_exists','element_visible'}:
    graph['edges'][i]['sourceHandle']='true';graph['edges'].append({'id':f'false-{i}','source':f'n{i}','target':f'n{i+1}','sourceHandle':'false'})
  workflow=await qa.api('POST','/api/workflows',graph)
  automation=await qa.api('POST',prefix+'/automations',{'name':'只读浏览器节点验收','description':'公开网页与实际仓库文件，无合成HTML','workflowId':workflow['id'],'inputPlan':{'inputs':[]},'parameterSchema':[],'environmentPolicy':{'source':'newFromProfile','profileId':profile['id'],'proxyOverride':{'mode':'none'},'modelProviderId':None},'runPolicy':{'maxTasks':1,'concurrency':1,'maxLiveInstances':1,'continueAfterFailure':False,'automaticExecutionTimeoutSeconds':150,'manualDeadlineSeconds':300}},str(uuid4()))
  accepted=await qa.api('POST',prefix+f'/automations/{automation["automationId"]}/batches',{'expectedAutomationRevision':automation['managementRevision'],'parameters':{},'maxTasks':1,'concurrency':1},str(uuid4()))
  qa.RESULT['scenarios']['browser_nodes']={'workflowId':workflow['id'],'automationId':automation['automationId'],'batchId':accepted['operation']['result']['batch']['batchId']};qa.save()
  data=await qa.collect(prefix,'browser_nodes');task=data['tasks'][0]
  values={o['name']:o['value'] for o in task['outputs']['items']};attempts=task['node-attempts']['items']
  qa.RESULT['executedNodeTypes']=sorted({steps[int(a['nodeId'][1:])][0] for a in attempts});qa.RESULT['successfulNodeTypes']=sorted({steps[int(a['nodeId'][1:])][0] for a in attempts if a['status']=='succeeded'})
  qa.check('production browser graph completes all 26 visits',data['batch']['statusCounts']['succeeded']==1 and len(attempts)==len(steps) and all(a['status']=='succeeded' for a in attempts),{'taskStatus':task['summary']['status'],'attemptCount':len(attempts),'expected':len(steps)})
  qa.check('actual public page title heading and load',values.get('public_loaded') is True and values.get('heading')=='Example Domain' and values.get('public_dom')=={'title':'Example Domain','heading':'Example Domain','url':public})
  qa.check('actual body children and heading siblings queried',bool(values.get('body_children')) and bool(values.get('heading_siblings')),{'children':values.get('body_children'),'siblings':values.get('heading_siblings')})
  qa.check('first and last tab identity matches real sources',values.get('first_title')=='Example Domain' and values.get('first_index')==0 and values.get('last_index')==1 and values.get('last_url')==source)
  scrolled=values.get('scrolled_source',{})
  qa.check('scroll changes actual long source viewport',scrolled.get('scrollY',0)>0 and scrolled.get('url')==source and scrolled.get('body','').strip()==(qa.ROOT/'apps/backend/pyproject.toml').read_text().strip(),{'scrollY':scrolled.get('scrollY')})
  back=values.get('back_source',{});forward=values.get('forward_source',{})
  qa.check('back returns exact actual TOML file',back.get('url')==source and back.get('text','').strip()==(qa.ROOT/'apps/backend/pyproject.toml').read_text().strip())
  try:package_matches=json.loads(forward.get('text','null'))==json.loads((qa.ROOT/'package.json').read_text())
  except ValueError:package_matches=False
  qa.check('forward returns exact actual package JSON',forward.get('url')==package and package_matches)
  artifacts=task['artifacts']['items'];image_files=list(qa.RUN.glob('browser_nodes-*.bin'))
  qa.check('production screenshot is downloadable PNG',len(artifacts)==1 and len(image_files)==1 and image_files[0].read_bytes().startswith(b'\x89PNG\r\n\x1a\n'),artifacts)
  for file in image_files:
   file.with_suffix('.png').write_bytes(file.read_bytes())
  copies=qa.WORKSPACE/'workspace/environments/instances'
  for _ in range(100):
   if not copies.exists() or not list(copies.iterdir()):break
   await asyncio.sleep(.2)
  qa.check('browser environment cleaned',not copies.exists() or not list(copies.iterdir()))
 except Exception:qa.RESULT['fatalError']=traceback.format_exc();print(qa.RESULT['fatalError'],flush=True)
 finally:
  await qa.SIDE.stop();qa.RESULT['finishedAt']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat();qa.save()
  qa.RESULT['ownedProcessesAfterCleanup']=[line for line in subprocess.check_output(['ps','-axo','pid=,command='],text=True).splitlines() if str(qa.WORKSPACE) in line];qa.save()
  Path(__file__).with_name('browser-node-results.json').write_text(json.dumps(qa.RESULT,ensure_ascii=False,indent=2))
  print('RESULT '+str(qa.RUN/'results.json'),flush=True)

asyncio.run(main())
raise SystemExit(1 if qa.RESULT.get('fatalError') or any(x['passed'] is False for x in qa.RESULT['checks']) else 0)
