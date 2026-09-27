"""Real production runtime/worker QA; no fake executors, transports, or responses.
Run: PYTHONPATH=apps/backend/src apps/backend/.venv/bin/python docs/qa/2026-09-28-system-audit/nodes/run_real_nodes.py
"""
from __future__ import annotations
import asyncio, base64, csv, hashlib, io, json, math, platform, shlex, shutil, statistics, subprocess, sys, tempfile, time, zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote
from uuid import uuid4

from autoflow.application.workflows.executors.production import build_production_executor_registry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext
from autoflow.infrastructure.process.workflow_worker import WorkflowWorkerManager
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RUNTIME = WorkflowRuntime(build_production_executor_registry())
RESULTS = []
SOURCES = [ROOT / p for p in ('package.json', 'apps/desktop/package.json', 'apps/backend/pyproject.toml', 'AGENTS.md', 'docs/PROJECT_STRUCTURE.md')]
PKG = json.loads(SOURCES[0].read_text())
DESKTOP = json.loads(SOURCES[1].read_text())
TEXT = SOURCES[3].read_text()
SIZES = [p.stat().st_size for p in SOURCES]
ROWS = [{'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in SOURCES]
VARS = {'package': PKG, 'packageText': SOURCES[0].read_text(), 'desktop': DESKTOP, 'text': TEXT, 'sizes': SIZES, 'paths': [r['path'] for r in ROWS], 'rows': ROWS, 'scripts': PKG['scripts']}


def node(kind, config, identity=None):
    return {'id': identity or kind, 'type': 'moduleNode', 'data': {'moduleType': kind, 'label': kind, 'config': config}}


def save():
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'gitHead': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(), 'platform': platform.platform(), 'python': sys.version, 'dataSources': ROWS, 'results': RESULTS}
    report['totals'] = {status: sum(x['status'] == status for x in RESULTS) for status in ('pass','fail','blocked')}
    report['executedModuleTypes'] = sorted({kind for r in RESULTS for kind in r.get('moduleTypes', [])})
    (OUT/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')


async def direct(name, kind, config, expected=None, *, variables=None, output='out', success=True, check=None):
    ctx = ExecutionContext(variables=json.loads(json.dumps({**VARS, **(variables or {})})))
    started = time.monotonic()
    result = await RUNTIME.execute({'nodes':[node(kind,config)], 'edges':[]}, ctx)
    actual = ctx.variables.get(output)
    ok = result.success == success and (not success or (check(actual) if check else actual == expected))
    item = {'name':name,'layer':'WorkflowRuntime + production executor','moduleTypes':[kind],'status':'pass' if ok else 'fail', 'durationMs':round((time.monotonic()-started)*1000,2), 'actual':actual,'expected':expected if not check else 'predicate in source','success':result.success,'error':result.node_result.error if result.node_result else None,'issues':[asdict(i) for i in result.issues]}
    RESULTS.append(item); save(); print(item['status'].upper(), name, flush=True)


async def worker(name, steps, directory, *, variables=None, verify=None, expected_success=True, document=None, extra=None, during=None):
    events=[]; artifact_root=(directory/'artifacts').resolve()
    runid=f'qa-{len(RESULTS):03}-{uuid4().hex[:8]}'
    doc={'nodes':[node(kind,cfg,f'n{i}') for i,(kind,cfg) in enumerate(steps)], 'edges':[{'id':f'e{i}', 'source':f'n{i}', 'target':f'n{i+1}'} for i in range(len(steps)-1)], 'variables':[{'name':k,'value':v} for k,v in {**VARS,**(variables or {})}.items()]}
    if document is not None:
        doc.update(document)
    mgr=WorkflowWorkerManager(directory, on_event=events.append)
    started=time.monotonic(); error=None
    try:
        await mgr.start(runid,'qa-real-files',None,{'runId':runid,'workflowId':runid,'profileId':'qa-real-files','requiresBrowser':False,'artifactRoot':str(artifact_root),'document':doc, **(extra or {})})
        pending = asyncio.create_task(during(events)) if during else None
        deadline=time.monotonic()+60
        while mgr.busy() and time.monotonic()<deadline:
            await asyncio.sleep(.05)
        if mgr.busy():
            raise TimeoutError('worker did not finish in 60 seconds')
        terminal=[e for e in events if e.get('type') in {'execution:completed','execution:failed'}]
        completed=[e for e in events if e.get('type')=='execution:node_complete']
        assert terminal, 'missing terminal event'
        succeeded=terminal[-1]['type']=='execution:completed'
        assert succeeded == expected_success, terminal[-1]
        if expected_success and document is None: assert len(completed)==len(steps), completed
        if pending: await pending
        if verify: verify(completed,artifact_root,runid)
    except Exception as exc:
        error=repr(exc)
    finally:
        await mgr.shutdown()
    evidence=OUT/f'{runid}-events.json'
    evidence.write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n')
    executed_ids={event.get('nodeId') for event in events if event.get('type')=='execution:node_complete'}
    actual_types={n['data']['moduleType'] for n in doc['nodes'] if n['id'] in executed_ids}
    item={'name':name,'layer':'real subprocess worker + production WorkflowRuntime/adapters','moduleTypes':sorted(actual_types),'scenarioModuleTypes':sorted({s[0] for s in steps}),'status':'fail' if error else 'pass','durationMs':round((time.monotonic()-started)*1000,2),'error':error,'evidence':evidence.name}
    RESULTS.append(item); save(); print(item['status'].upper(),name,error or '',flush=True)
    return events


def equals(actual, expected):
    assert actual == expected, {'actual':actual,'expected':expected}


def data(event): return event['data']


async def main():
    for kind,expected in [('list_sum',sum(SIZES)),('list_average',statistics.mean(SIZES)),('list_min',min(SIZES)),('list_max',max(SIZES)),('list_reverse',list(reversed(SIZES))),('list_sort',sorted(SIZES)),('list_unique',list(dict.fromkeys(SIZES))),('stat_median',statistics.median(SIZES)),('stat_variance',statistics.variance(SIZES)),('stat_stdev',statistics.stdev(SIZES)),('stat_percentile',statistics.median(SIZES))]:
        await direct('真实源文件尺寸 '+kind,kind,{'listVariable':'sizes','resultVariable':'out'},expected)
    await direct('源文件列表计数','list_length',{'listVariable':'paths','variableName':'out'},len(SOURCES))
    await direct('源文件负索引','list_get',{'listVariable':'paths','listIndex':-1,'variableName':'out'},ROWS[-1]['path'])
    await direct('源文件区间','list_slice',{'listVariable':'sizes','startIndex':1,'endIndex':3,'resultVariable':'out'},SIZES[1:3])
    await direct('源文件过滤','list_filter',{'listVariable':'sizes','filterType':'greater','compareValue':SIZES[0],'resultVariable':'out'},[v for v in SIZES if v>SIZES[0]])
    await direct('源文件 KiB 换算','list_map',{'listVariable':'sizes','expression':'x / 1024','resultVariable':'out'},[v/1024 for v in SIZES])
    await direct('源文件首项查找','list_find',{'listVariable':'paths','searchValue':ROWS[0]['path'],'resultVariable':'out'},0)
    await direct('源文件次数','list_count',{'listVariable':'paths','searchValue':ROWS[0]['path'],'resultVariable':'out'},1)
    for kind,cfg,expected in [
        ('dict_get',{'dictVariable':'package','dictKey':'name','variableName':'out'},PKG['name']),
        ('dict_keys',{'dictVariable':'scripts','keyType':'keys','variableName':'out'},list(PKG['scripts'])),
        ('dict_get_path',{'dictVariable':'package','path':'scripts.test','resultVariable':'out'},PKG['scripts'].get('test','')),
        ('dict_deep_copy',{'dictVariable':'package','resultVariable':'out'},PKG),
        ('dict_sort',{'dictVariable':'scripts','sortBy':'key','sortOrder':'asc','resultVariable':'out'},dict(sorted(PKG['scripts'].items()))),
        ('json_parse',{'sourceVariable':'packageText','jsonPath':'$.name','variableName':'out'},PKG['name']),
        ('md5_encrypt',{'inputText':'${text}','resultVariable':'out'},hashlib.md5(TEXT.encode()).hexdigest()),
        ('sha_encrypt',{'inputText':'${text}','shaType':'sha256','resultVariable':'out'},hashlib.sha256(TEXT.encode()).hexdigest()),
        ('url_encode_decode',{'inputText':ROWS[-1]['path'],'operation':'encode','resultVariable':'out'},quote(ROWS[-1]['path'],safe='')),
        ('base64',{'inputText':'${text}','operation':'encode','variableName':'out'},base64.b64encode(TEXT.encode()).decode()),
        ('string_split',{'inputText':'${text}','separator':'\n','variableName':'out'},TEXT.split('\n')),
        ('string_join',{'listVariable':'paths','separator':'\n','variableName':'out'},'\n'.join(VARS['paths'])),
        ('string_replace',{'inputText':ROWS[0]['path'],'searchValue':'.json','replaceValue':'.yaml','variableName':'out'},ROWS[0]['path'].replace('.json','.yaml')),
        ('string_concat',{'string1':PKG['name'],'string2':PKG.get('version',''),'variableName':'out'},PKG['name']+PKG.get('version','')),
        ('string_trim',{'inputText':'${text}','variableName':'out'},TEXT.strip()),
        ('string_case',{'inputText':PKG['name'],'caseMode':'upper','variableName':'out'},PKG['name'].upper()),
        ('string_substring',{'inputText':'${text}','startIndex':0,'endIndex':10,'variableName':'out'},TEXT[:10]),
        ('regex_extract',{'inputText':SOURCES[0].read_text(),'pattern':'"name"\\s*:\\s*"([^"]+)"','extractMode':'groups','variableName':'out'},[PKG['name']]),
        ('math_gcd',{'value1':SIZES[0],'value2':SIZES[1],'resultVariable':'out'},math.gcd(SIZES[0],SIZES[1])),
        ('math_lcm',{'value1':SIZES[0],'value2':SIZES[1],'resultVariable':'out'},math.lcm(SIZES[0],SIZES[1])),
        ('math_clamp',{'value':SIZES[0],'min':min(SIZES),'max':max(SIZES),'resultVariable':'out'},SIZES[0]),
    ]:
        await direct('仓库真实数据 '+kind,kind,cfg,expected)
    for kind,cfg,expected in [
        ('math_round',{'value':SIZES[0]/1024,'decimals':2},round(SIZES[0]/1024,2)),
        ('math_floor',{'value':SIZES[0]/1024},math.floor(SIZES[0]/1024)),
        ('math_abs',{'value':SIZES[0]-SIZES[1]},abs(SIZES[0]-SIZES[1])),
        ('math_sqrt',{'value':SIZES[0]},math.sqrt(SIZES[0])),
        ('math_power',{'base':SIZES[0],'exponent':2},SIZES[0]**2),
        ('math_modulo',{'dividend':SIZES[0],'divisor':1024},SIZES[0]%1024),
        ('math_base_convert',{'value':str(SIZES[0]),'fromBase':10,'toBase':16},format(SIZES[0],'X')),
        ('math_factorial',{'value':len(SOURCES)},math.factorial(len(SOURCES))),
        ('math_permutation',{'n':len(SOURCES),'r':2,'calcType':'combination'},math.comb(len(SOURCES),2)),
        ('stat_normalize',{'listVariable':'sizes'},[(v-min(SIZES))/(max(SIZES)-min(SIZES)) for v in SIZES]),
        ('stat_standardize',{'listVariable':'sizes'},[(v-statistics.mean(SIZES))/statistics.stdev(SIZES) for v in SIZES]),
        ('list_merge',{'list1':'paths','list2':'paths'},VARS['paths']*2),
        ('list_chunk',{'listVariable':'paths','chunkSize':2},[VARS['paths'][i:i+2] for i in range(0,len(SOURCES),2)]),
        ('list_remove_empty',{'listVariable':'paths'},VARS['paths']),
    ]:
        await direct('源文件元数据 '+kind,kind,{**cfg,'resultVariable':'out'},expected)
    await direct('真实 CSV 生成解析','csv_generate',{'listVariable':'rows','resultVariable':'out'},check=lambda v:list(csv.DictReader(io.StringIO(v)))==[{k:str(v) for k,v in r.items()} for r in ROWS])
    csv_data=io.StringIO(); w=csv.DictWriter(csv_data,fieldnames=list(ROWS[0]));w.writeheader();w.writerows(ROWS)
    await direct('源文件 CSV 解析','csv_parse',{'csvContent':csv_data.getvalue(),'hasHeader':True,'resultVariable':'out'},[{k:str(v) for k,v in r.items()} for r in ROWS])
    await direct('真实 CSV 导出仅剩表头时应为空数据集','csv_parse',{'csvContent':csv_data.getvalue().splitlines()[0]+'\n','hasHeader':True,'resultVariable':'out'},[])
    await direct('源文件列表索引越界','list_get',{'listVariable':'paths','listIndex':len(SOURCES),'variableName':'out'},success=False)
    await direct('截断真实 package JSON 应拒绝','json_parse',{'sourceVariable':'broken','jsonPath':'$.name','variableName':'out'},variables={'broken':SOURCES[0].read_text()[:-3]},success=False)
    await direct('不支持的散列算法应拒绝','sha_encrypt',{'inputText':'${text}','shaType':'sha-does-not-exist','resultVariable':'out'},success=False)
    with tempfile.TemporaryDirectory(prefix='autoflow-real-nodes-') as temp:
        directory=Path(temp)
        steps=[('python_script',{'scriptContent':'from pathlib import Path\nimport hashlib, json\np=Path(vars.source)\nvars.sha=hashlib.sha256(p.read_bytes()).hexdigest()\nreturn {"name":json.loads(p.read_text())["name"],"bytes":p.stat().st_size,"sha256":vars.sha}','resultVariable':'py'}),('json_parse',{'sourceVariable':'py','jsonPath':'$.sha256','variableName':'sha'}),('print_log',{'logMessage':'${sha}'})]
        await worker('Python 真实读仓库文件 → JSON → 日志',steps,directory,variables={'source':str(SOURCES[0])},verify=lambda ev,*_: (equals(data(ev[0])['result']['sha256'],ROWS[0]['sha256']), equals(data(ev[-1])['message'],ROWS[0]['sha256'])))
        table_steps=[('table_add_row',{'rowData':json.dumps(row)}) for row in ROWS]
        table_steps.extend([('table_add_column',{'columnName':'source','defaultValue':PKG['name']}),('table_set_cell',{'rowIndex':0,'columnName':'source','cellValue':DESKTOP['name']}),('table_get_cell',{'rowIndex':0,'columnName':'source','variableName':'cell'}),('table_export',{'exportFormat':'csv','savePath':'report','fileNamePattern':'source-files','variableName':'csv_path'}),('table_export',{'exportFormat':'excel','savePath':'report','fileNamePattern':'source-files','sheetName':'源文件','variableName':'xlsx_path'})])
        def verify_table(ev,art,run):
            files=list((art/'runs'/run/'outputs').rglob('*'))
            xlsx=next(p for p in files if p.suffix=='.xlsx')
            csvfile=next(p for p in files if p.suffix=='.csv')
            with csvfile.open(newline='') as f: rows=list(csv.DictReader(f))
            equals(len(rows),len(ROWS)); equals(rows[0]['source'],"'"+DESKTOP['name'])
            wb=load_workbook(xlsx,read_only=True,data_only=False); grid=list(wb['源文件'].values); wb.close()
            equals(len(grid),len(ROWS)+1); equals(grid[1][0],ROWS[0]['path']);equals(grid[1][1],ROWS[0]['bytes'])
            shutil.copy2(xlsx,OUT/'source-files.xlsx');shutil.copy2(csvfile,OUT/'source-files.csv')
        await worker('实际表格增列改格 → CSV/XLSX 文件 → 独立库回读',table_steps,directory,verify=verify_table)
        await worker('真实列表导出覆盖后追加', [('list_export',{'listVariable':'paths','outputPath':'paths.txt','appendMode':False}),('list_export',{'listVariable':'paths','outputPath':'paths.txt','appendMode':True})],directory,verify=lambda ev,art,run:equals((art/'runs'/run/'outputs'/'paths.txt').read_text(),'\n'.join(VARS['paths']+VARS['paths'])))
        await worker('真实文件 Base64 写入再读取', [('base64',{'operation':'base64_to_file','inputBase64':base64.b64encode(SOURCES[0].read_bytes()).decode(),'outputPath':'copies','fileName':'package.json'}),('base64',{'operation':'file_to_base64','filePath':'copies/package.json','variableName':'content'})],directory,verify=lambda ev,art,run:equals(base64.b64decode(data(ev[-1]).split(',',1)[1]),SOURCES[0].read_bytes()))
        await worker('产物路径越界应拒绝', [('list_export',{'listVariable':'paths','outputPath':'../outside.txt'})],directory,expected_success=False,verify=lambda ev,art,run:equals((art/'runs'/run/'outside.txt').exists(),False))
        zipdir=directory/'zip workspace'; zipdir.mkdir(); copied=zipdir/'package source.json';shutil.copy2(SOURCES[0],copied)
        script='from pathlib import Path\nfrom zipfile import ZipFile\nimport hashlib\np=Path(vars.source)\nz=Path(vars.destination)\nwith ZipFile(z,"w") as out: out.write(p,p.name)\nwith ZipFile(z) as inp: content=inp.read(p.name)\nreturn {"sha256":hashlib.sha256(content).hexdigest(),"file":str(z),"members":[p.name]}'
        await worker('Python 压缩真实文件并解压验 SHA256',[('python_script',{'scriptContent':script,'resultVariable':'zip_result'})],directory,variables={'source':str(copied),'destination':str(zipdir/'sources.zip')},verify=lambda ev,*_:equals(data(ev[0])['result']['sha256'],ROWS[0]['sha256']))
        arg_script=zipdir/'read argument.py';arg_script.write_text('import sys,json\nfrom pathlib import Path\nprint(json.loads(Path(sys.argv[1]).read_text())["name"])\n')
        await worker('Python 文件模式带空格路径参数', [('python_script',{'scriptMode':'file','scriptPath':str(arg_script),'scriptArgs':shlex.quote(str(copied)),'stdoutVariable':'out'})],directory,verify=lambda ev,*_:equals(data(ev[0])['stdout'],PKG['name']))
        await worker('Python 失败应中断后继节点',[('python_script',{'scriptContent':'from pathlib import Path\nreturn Path(vars.source).read_text()'}),('print_log',{'logMessage':PKG['name']})],directory,variables={'source':str(directory/'not-created.json')},expected_success=False,verify=lambda ev,*_:equals(len(ev),1))
        await worker('Python 超时清理',[('python_script',{'scriptContent':'import time\ntime.sleep(10)','timeout':1})],directory,expected_success=False)
        cmd='node -p '+shlex.quote('require('+json.dumps(str(SOURCES[0]))+').name')
        await worker('系统命令 Node.js 真实读取 package.json',[('run_command',{'command':cmd,'shell':'sh','timeout':10,'variableName':'node_name'})],directory,verify=lambda ev,*_:equals(data(ev[0])['output'],PKG['name']))
        await worker('公开 IANA 网页真实 HTTP GET',[('api_request',{'requestUrl':'https://www.iana.org/domains/reserved','requestMethod':'GET','requestTimeout':15,'variableName':'page'})],directory,verify=lambda ev,*_: (equals(data(ev[0])['status_code'],200),equals('IANA-managed Reserved Domains' in data(ev[0])['response'],True)))
    RESULTS.append({'name':'Studio JavaScript 节点完整浏览器执行','moduleTypes':[],'status':'blocked','reason':'js_script 经 sidecar UI/SSE 的 BrowserScriptGateway 运行；本分工不启动 Electron，未用 Node.js 替代品假冒节点通过。run_command 中 Node.js 执行单独计为命令节点。'})
    RESULTS.append({'name':'专用文件路径/压缩节点','moduleTypes':[],'status':'blocked','reason':'production registry 未发现通用 read_file/write_file/path/zip 节点；真实文件读写由 Base64/导出/Python 验证，压缩经 Python 脚本验证，不虚称独立节点。'})
    save()

if __name__=='__main__':
    asyncio.run(main())
    raise SystemExit(1 if any(item['status'] == 'fail' for item in RESULTS) else 0)
