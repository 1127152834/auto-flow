"""Run after run_real_nodes.py; continues real runtime QA with uncovered safe nodes."""
import asyncio, base64, colorsys, itertools, json, math, re, shutil, statistics, sys, tempfile, uuid
from datetime import datetime
from pathlib import Path
import run_real_nodes as q

FILTERS=sys.argv[1:]
def selected(name): return not FILTERS or any(text in name for text in FILTERS)
q.RESULTS[:]=[r for r in json.loads((q.OUT/'results.json').read_text())['results'] if not (r['name'].startswith('补充 ') and selected(r['name']))]
async def direct(name, kind, cfg, expected=None, **kwargs):
    if selected(name): await q.direct('补充 '+name,kind,cfg,expected,**kwargs)
async def worker(name,*args,**kwargs):
    if selected(name): return await q.worker('补充 '+name,*args,**kwargs)
def edge(a,b,handle=None):
    return {'id':a+'-'+b,'source':a,'target':b,**({'sourceHandle':handle} if handle else {})}
def node(i,k,c): return q.node(k,c,i)
def values(ev,n): return [x['data'] for x in ev if x['nodeId']==n]

async def main():
    size_map={r['path']:r['bytes'] for r in q.ROWS}
    for k,c,e,v in [
        ('list_operation',{'listVariable':'paths','listAction':'append','listValue':q.ROWS[0]['path']},q.VARS['paths']+[q.ROWS[0]['path']],{}),
        ('dict_operation',{'dictVariable':'package','dictAction':'set','dictKey':'name','dictValue':q.DESKTOP['name']},{**q.PKG,'name':q.DESKTOP['name']},{}),
        ('dict_merge',{'dict1':'package','dict2':'desktop'},{**q.PKG,**q.DESKTOP},{}),
        ('dict_filter',{'dictVariable':'package','filterKeys':'name,version','filterMode':'include'},{k:v for k,v in q.PKG.items() if k in {'name','version'}},{}),
        ('dict_map_values',{'dictVariable':'size_map','expression':'v / 1024'},{k:v/1024 for k,v in size_map.items()},{'size_map':size_map}),
        ('dict_invert',{'dictVariable':'size_map'},{str(v):k for k,v in size_map.items()},{'size_map':size_map}),
        ('dict_flatten',{'dictVariable':'nested'}, {'metadata.'+k:v for k,v in size_map.items()},{'nested':{'metadata':size_map}}),
        ('list_flatten',{'listVariable':'nested'},q.VARS['paths'],{'nested':[q.VARS['paths'][:2],q.VARS['paths'][2:]]}),
        ('list_intersection',{'list1':'paths','list2':'subset'},q.VARS['paths'][:2],{'subset':q.VARS['paths'][:2]}),
        ('list_union',{'list1':'paths','list2':'subset'},q.VARS['paths'],{'subset':q.VARS['paths'][:2]}),
        ('list_difference',{'list1':'paths','list2':'subset'},q.VARS['paths'][2:],{'subset':q.VARS['paths'][:2]}),
        ('list_cartesian_product',{'list1':'paths','list2':'subset'},[list(x) for x in itertools.product(q.VARS['paths'],q.VARS['paths'][:2])],{'subset':q.VARS['paths'][:2]}),
        ('list_to_string_advanced',{'listVariable':'paths','formatTemplate':'{item}','separator':'\n'},'\n'.join(q.VARS['paths']),{}),
        ('stat_mode',{'listVariable':'sizes'},statistics.mode(q.SIZES),{}),
    ]:
        output='paths' if k=='list_operation' else 'package' if k=='dict_operation' else 'out'
        if k in {'list_union','list_difference','list_intersection'}:
            await direct('真实清单 '+k,k,{**c,'resultVariable':'out'},variables=v,output=output,check=lambda actual,e=e:len(actual)==len(e) and set(actual)==set(e))
        else:
            await direct('真实清单 '+k,k,{**c,'resultVariable':'out'},e,variables=v,output=output)
    for k,c,expected in [('math_log',{'value':len(q.SOURCES),'base':'e'},math.log(len(q.SOURCES))),('math_exp',{'value':len(q.SOURCES)},math.exp(len(q.SOURCES))),('math_trig',{'value':len(q.SOURCES),'function':'sin','unit':'radian'},math.sin(len(q.SOURCES))),('math_percentage',{'value1':q.SIZES[0],'value2':sum(q.SIZES),'operation':'what_percent'},q.SIZES[0]/sum(q.SIZES)*100)]:
        await direct('真实元数据 '+k,k,{**c,'resultVariable':'out'},check=lambda v,e=expected:isinstance(v,(float,int)) and math.isclose(v,e,rel_tol=1e-10))
    await direct('真实列表洗牌','list_shuffle',{'listVariable':'paths','resultVariable':'out'},check=lambda v: sorted(v)==sorted(q.VARS['paths']))
    await direct('真实列表抽样','list_sample',{'listVariable':'paths','sampleSize':2,'resultVariable':'out'},check=lambda v:len(v)==len(set(v))==2 and set(v)<=set(q.VARS['paths']))
    await direct('运行时 UUID','uuid_generator',{'uuidVersion':4,'resultVariable':'out'},check=lambda v:uuid.UUID(v).version==4)
    await direct('运行时随机口令','random_password_generator',{'length':len(q.SOURCES)*4,'resultVariable':'out'},check=lambda v:len(v)==len(q.SOURCES)*4)
    await direct('源文件尺寸边界内随机数','random_number',{'minValue':min(q.SIZES),'maxValue':max(q.SIZES),'variableName':'out'},check=lambda v:isinstance(v,int) and min(q.SIZES)<=v<=max(q.SIZES))
    await direct('高级随机数','math_random_advanced',{'type':'uniform','min':min(q.SIZES),'max':max(q.SIZES),'count':len(q.SOURCES),'resultVariable':'out'},check=lambda v:len(v)==len(q.SOURCES) and all(min(q.SIZES)<=x<=max(q.SIZES) for x in v))
    await direct('系统日期','get_time',{'timeFormat':'date','variableName':'out'},datetime.now().strftime('%Y-%m-%d'))
    await direct('实际源文件 mtime 时间戳','timestamp_converter',{'operation':'to_datetime','inputValue':int(q.SOURCES[0].stat().st_mtime),'resultVariable':'out'},datetime.fromtimestamp(int(q.SOURCES[0].stat().st_mtime)).strftime('%Y-%m-%d %H:%M:%S'))
    css=q.ROOT/'apps/desktop/src/renderer/domains/workflows/styles/autoflow.css'
    hexcolor=re.search(r'#[0-9a-fA-F]{6}',css.read_text()).group();rgb=[int(hexcolor[i:i+2],16) for i in (1,3,5)]
    h,s,v=colorsys.rgb_to_hsv(*(x/255 for x in rgb)); hi,si,vi=int(h*360),int(s*100),int(v*100)
    hsv={'h':hi,'s':si,'v':vi,'string':f'HSV({hi}, {si}%, {vi}%)'}
    await direct('实际 CSS token RGB 转 HSV','rgb_to_hsv',dict(zip(('r','g','b'),rgb))|{'resultVariable':'out'},hsv)
    r,g,b=[x/255 for x in rgb]; k=1-max(r,g,b); c,m,y=[(1-x-k)/(1-k) for x in (r,g,b)];ci,mi,yi,ki=[int(x*100) for x in (c,m,y,k)]
    cmyk={'c':ci,'m':mi,'y':yi,'k':ki,'string':f'CMYK({ci}%, {mi}%, {yi}%, {ki}%)'}
    await direct('实际 CSS token RGB 转 CMYK','rgb_to_cmyk',dict(zip(('r','g','b'),rgb))|{'resultVariable':'out'},cmyk)
    await direct('实际 CSS token HEX 转 CMYK','hex_to_cmyk',{'hexColor':hexcolor,'resultVariable':'out'},cmyk)
    with tempfile.TemporaryDirectory(prefix='autoflow-extra-nodes-') as t:
        directory=Path(t)
        await worker('日志实际导出 JSON',[('print_log',{'logMessage':q.ROWS[0]['sha256']}),('export_log',{'logFormat':'json','outputPath':'logs/source.json'})],directory,verify=lambda ev,art,run:q.equals(q.ROWS[0]['sha256'] in (art/'runs'/run/'outputs/logs/source.json').read_text(),True))
        await worker('表格删除与清空',[('table_add_row',{'rowData':json.dumps(q.ROWS[0])}),('table_add_row',{'rowData':json.dumps(q.ROWS[1])}),('table_delete_row',{'rowIndex':0}),('table_get_cell',{'rowIndex':0,'columnName':'path','variableName':'value'}),('table_clear',{})],directory,verify=lambda ev,*_:q.equals(ev[3]['data'],q.ROWS[1]['path']))
        await worker('Allure 完整报告真实源文件附件',[('allure_init',{'suiteName':q.PKG['name']}),('allure_start_test',{'testName':q.ROWS[0]['path']}),('allure_add_step',{'stepName':q.ROWS[0]['sha256']}),('allure_add_attachment',{'filePath':str(q.SOURCES[0])}),('allure_stop_test',{'status':'passed'}),('allure_generate_report',{'reportDir':'allure','autoOpen':False})],directory,verify=lambda ev,art,run:q.equals(any(q.ROWS[0]['sha256'] in p.read_text() for p in (art/'runs'/run/'outputs').rglob('*.html')),True))
        await worker('PyPI 真实公开 API 轮询条件',[('api_trigger',{'apiUrl':'https://pypi.org/pypi/httpx/json','conditionPath':'$.info.name','conditionValue':'httpx','timeout':15,'checkInterval':1})],directory,verify=lambda ev,art,run:q.equals(json.loads(next((art/'runs'/run/'artifacts/node-results').glob('*.json')).read_text())['info']['name'],'httpx'))
        await worker('Webhook request 的公开网页 GET',[('webhook_request',{'url':'https://www.iana.org/domains/reserved','method':'GET','timeout':15,'saveResponse':True})],directory,verify=lambda ev,*_:q.equals(ev[0]['data']['status_code'],200))
        screenshot=q.ROOT/'docs/migration/automation-studio-m5-retest-2026-09-13/packaged-editor.png'
        image_source=[('base64',{'operation':'base64_to_file','inputBase64':base64.b64encode(screenshot.read_bytes()).decode(),'outputPath':'images','fileName':'real-studio.png'})]
        await worker('真实历史应用截图 OCR',image_source+[('image_ocr',{'imagePath':'images/real-studio.png','ocrType':'general'})],directory,verify=lambda ev,*_:q.equals('保存' in ev[-1]['data']['text'] and ev[-1]['data']['length']>50,True))
        await worker('真实应用截图人脸负样本',image_source+[('face_recognition',{'sourceImage':'images/real-studio.png','targetImage':'images/real-studio.png'})],directory,verify=lambda ev,*_:q.equals(ev[-1]['data']['source_faces'],0))
        await worker('Python 真实源文件散列与日志复核',[('python_script',{'scriptContent':'from pathlib import Path\nimport hashlib\nvars.sha=hashlib.sha256(Path(vars.source).read_bytes()).hexdigest()\nreturn vars.sha'}),('print_log',{'logMessage':'${sha}'})],directory,variables={'source':str(q.SOURCES[0])},verify=lambda ev,*_:q.equals(ev[-1]['data']['message'],q.ROWS[0]['sha256']))
        watched=directory/'watch';watched.mkdir()
        async def create_actual(events):
            for _ in range(200):
                if any(e.get('type')=='execution:node_start' for e in events):break
                await asyncio.sleep(.02)
            await asyncio.sleep(1.2)
            shutil.copy2(q.SOURCES[0],watched/'package.json')
        await worker('真实文件创建触发器',[('file_watcher_trigger',{'watchPath':str(watched),'watchType':'created','filePattern':'*.json','timeout':8})],directory,during=create_actual,verify=lambda ev,*_:q.equals(ev[0]['data']['fileName'],'package.json'))
        await worker('真实延迟定时与 wait',[('scheduled_task',{'scheduleType':'delay','delaySeconds':1}),('wait',{'waitType':'time','waitDuration':.05})],directory)
        await worker('概率节点真实随机值与必达分支',[('probability_trigger',{'probability':100})],directory,verify=lambda ev,*_:q.equals(ev[0]['data']['selected_path'],'path1'))
        # The graph reads source-file sizes and routes using real per-file values.
        graph={'nodes':[node('init','set_variable',{'variableName':'total','variableValue':'0'}),node('files','foreach',{'listVariable':'sizes','itemVariable':'size'}),node('positive','condition',{'leftValue':'${size}','rightValue':0,'operator':'>'}),node('sum','increment_decrement',{'variableName':'total','step':'${size}'}),node('skip','continue_loop',{}),node('check','assert_checkpoint',{'actualValue':'${total}','expectedValue':sum(q.SIZES),'operator':'=='})], 'edges':[edge('init','files'),edge('files','positive','loop'),edge('positive','sum','true'),edge('positive','skip','false'),edge('files','check','done')]}
        await worker('真实文件 foreach 条件求和',[(x['data']['moduleType'],x['data']['config']) for x in graph['nodes']],directory,document=graph,verify=lambda ev,*_: (q.equals(values(ev,'check')[0]['passed'],True),q.equals(len(values(ev,'sum')),len(q.SOURCES))))
        for kind,config,count in [('loop',{'loopCount':len(q.SOURCES)},len(q.SOURCES)),('foreach_dict',{'dictVariable':'scripts'},len(q.PKG['scripts']))]:
            graph={'nodes':[node('loop',kind,config),node('log','print_log',{'logMessage':q.PKG['name']}),node('continue','continue_loop',{}),node('forbidden','print_log',{'logMessage':'must-not-run'}),node('done','print_log',{'logMessage':q.DESKTOP['name']})],'edges':[edge('loop','log','loop'),edge('log','continue'),edge('continue','forbidden'),edge('loop','done','done')]}
            await worker('真实仓库计数 '+kind+' continue',[(x['data']['moduleType'],x['data']['config']) for x in graph['nodes']],directory,document=graph,verify=lambda ev,*_,count=count:(q.equals(len(values(ev,'log')),count),q.equals(values(ev,'forbidden'),[]),q.equals(len(values(ev,'done')),1)))
        graph={'nodes':[node('loop','infinite_loop',{}),node('break','break_loop',{}),node('done','stop_workflow',{'stopReason':q.PKG['name']}),node('forbidden','print_log',{'logMessage':'must-not-run'})], 'edges':[edge('loop','break','loop'),edge('loop','done','done'),edge('done','forbidden')]}
        await worker('无限循环 break 并停止后继',[(x['data']['moduleType'],x['data']['config']) for x in graph['nodes']],directory,document=graph,verify=lambda ev,*_:(q.equals(len(values(ev,'break')),1),q.equals(values(ev,'forbidden'),[])))
        child={'id':'source-summary','name':q.PKG['name'],'nodes':[node('childsum','list_sum',{'listVariable':'sizes','resultVariable':'source_bytes'})],'edges':[],'variables':[]}
        graph={'nodes':[node('call','run_workflow_file',{'workflowFile':'source-summary','resultVariable':'child_result'}),node('check','assert_checkpoint',{'actualValue':'${source_bytes}','expectedValue':sum(q.SIZES)})],'edges':[edge('call','check')]}
        await worker('真实嵌套工作流返回变量',[(x['data']['moduleType'],x['data']['config']) for x in graph['nodes']],directory,document=graph,extra={'workflowDependencies':{'source-summary':child}},verify=lambda ev,*_:q.equals(values(ev,'check')[0]['passed'],True))
        custom={'id':'source-summary','name':'source-summary','workflow':child,'parameters':[{'name':'sizes','default_value':q.SIZES}],'outputs':[{'name':'source_bytes'}]}
        graph={'nodes':[node('call','custom_module',{'customModuleId':'source-summary'}),node('check','assert_checkpoint',{'actualValue':'${source_bytes}','expectedValue':sum(q.SIZES)})],'edges':[edge('call','check')]}
        await worker('真实自定义模块参数输出',[(x['data']['moduleType'],x['data']['config']) for x in graph['nodes']],directory,document=graph,extra={'customModuleDependencies':{'source-summary':custom}},verify=lambda ev,*_:q.equals(values(ev,'check')[0]['passed'],True))
        inner=node('inner','list_sum',{'listVariable':'sizes','resultVariable':'source_bytes'});inner['position']={'x':1010,'y':1010}
        group=node('group','group',{});group['data'].update({'isSubflow':True,'subflowName':'source-summary','width':500,'height':500});group['position']={'x':1000,'y':1000}
        graph={'nodes':[group,inner,node('call','subflow',{'subflowGroupId':'group'}),node('check','assert_checkpoint',{'actualValue':'${source_bytes}','expectedValue':sum(q.SIZES)}),node('note','note',{})],'edges':[edge('call','check')]}
        await worker('真实画布子流程与结构节点',[(x['data']['moduleType'],x['data']['config']) for x in graph['nodes']],directory,document=graph,verify=lambda ev,*_:q.equals(values(ev,'check')[0]['passed'],True))
    q.save()

if __name__=='__main__':
    asyncio.run(main())
    raise SystemExit(1 if any(r['status']=='fail' for r in q.RESULTS) else 0)
