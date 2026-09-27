"""Build an exhaustive production-node ledger from current registry and actual QA evidence."""
import json
from collections import Counter
from pathlib import Path
from autoflow.application.workflows.executors.production import build_production_executor_registry
from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES

root=Path(__file__).resolve().parent
report=json.loads((root/'results.json').read_text())
registry=build_production_executor_registry()
supplemental=[]
js_path=root.parent/'ui/native-js-result.json'
if js_path.exists():
    js=json.loads(js_path.read_text())
    assert js['status']=='passed' and js['packaged'] and js['createdViaNativeUI'] and js['actual']==js['expected'] and js['run']['status']=='completed'
    supplemental.append({'name':'主任务补验：打包 Electron 正式 JS Gateway','moduleTypes':['js_script'],'status':'pass','evidence':'../ui/native-js-result.json'})
browser_path=root.parent/'runtime/browser-node-results.json'
if browser_path.exists():
    browser=json.loads(browser_path.read_text())
    assert browser['kind']=='real_browser_node_coverage' and browser['finishedAt']
    assert browser['gitHead']==report['gitHead']
    assert browser['checks'] and all(check['passed'] for check in browser['checks'])
    assert browser['ownedProcessesAfterCleanup']==[]
    node_types={step['nodeId']:step['type'] for step in browser['steps']}
    tasks=browser['scenarios']['browser_nodes']['result']['tasks']
    assert tasks and all(task['summary']['status']=='succeeded' for task in tasks)
    attempts=[attempt for task in tasks for attempt in task['node-attempts']['items']]
    assert len(attempts)==len(browser['steps']) and all(attempt['status']=='succeeded' for attempt in attempts)
    successful_types=sorted({node_types[attempt['nodeId']] for attempt in attempts})
    assert successful_types==sorted(browser['successfulNodeTypes'])
    supplemental.append({'name':'运行链补验：真实 CloakBrowser 公开网页与仓库文件','moduleTypes':successful_types,'status':'pass','evidence':'../runtime/browser-node-results.json','scenarioCount':1,'taskCount':len(tasks),'nodeVisits':len(attempts),'assertions':len(browser['checks'])})
external={'send_email','email_trigger','notify_telegram','notify_webhook','ssh_connect','ssh_disconnect','ssh_download_file','ssh_upload_file','ssh_execute_command','proxy_query','proxy_change_ip','proxy_change_location'}
native={'get_clipboard','set_clipboard','play_sound','printer_call','hotkey_trigger','mouse_trigger','gesture_trigger','face_trigger','sound_trigger','image_trigger','lock_screen','shutdown_system','start_screen_share','stop_screen_share','text_to_speech','system_notification'}
local={'share_file','share_folder','stop_share','webhook_trigger'}
rows=[]
for kind in sorted(registry.get_all_types()):
    cases=[r for r in [*report['results'],*supplemental] if kind in r.get('moduleTypes',[])]
    if cases:
        status='known-failure' if any(r['status']=='fail' for r in cases) else 'real-tested'
        category='实际执行'
        reason='仅证明所列场景；不表示该类型所有配置、异常路径或平台已穷尽。'
        if kind=='face_recognition':
            status='real-negative-only';reason='真实应用截图经本地人脸模型推理返回0个人脸；缺少授权真人样本，未验证人脸正向匹配和误识率。'
        if kind in {'element_exists','element_visible'}:
            reason+=' 浏览器补组仅真实可见元素的正向分支，未覆盖不存在/隐藏分支。'
    elif kind in {'group','note'}:
        status='structural-tested';category='结构节点';reason='真实画布子流程图包含该节点；运行时按结构语义处理，不记为执行器完成。'
    elif kind.startswith(('ai_','firecrawl_')) or kind in external:
        status='not-run';category='需外部服务或账号';reason='需要真实已配置供应商/服务/代理/SSH与授权目标；本子任务未使用账号、付费凭据或发送外部消息。'
        if kind.startswith(('ai_element','ai_smart','ai_vision_act','firecrawl_')):reason+=' 还需要真实浏览器会话。'
    elif kind in native:
        status='not-run';category='需设备或原生交互';reason='需要系统设备/屏幕/剪贴板/音频/通知/打印或原生UI权限；本子任务未触发全局键鼠、关机、锁屏、屏幕分享或改变剪贴板。'
    elif registry.get(kind).requires_browser or kind in {'js_script','input_prompt'}:
        status='not-run';category='需浏览器或正式UI';reason='需要CloakBrowser页面、真实元素/下载/网络/验证码，或正式Electron交互Gateway；由主任务浏览器/UI测试合并证据，本报告未计通过。'
    elif kind in local:
        status='not-run';category='本机可执行但本子任务未测';reason='需真实sidecar注册与desktop_actions/webhook Gateway、隔离服务端口及回调；单独worker无宿主交互响应，不使用fake Gateway冒充通过。'
    else:
        raise RuntimeError('Unclassified node: '+kind)
    rows.append({'moduleType':kind,'approved':kind in APPROVED_NODE_TYPES,'status':status,'category':category,'reason':reason,'cases':[r['name'] for r in cases],'evidence':sorted({r.get('evidence') or r.get('httpEvidence') for r in cases if r.get('evidence') or r.get('httpEvidence')})})
executed=set(report['executedModuleTypes'])|{kind for case in supplemental for kind in case['moduleTypes']}
ledger={'registryCount':len(rows),'approvedCount':len(APPROVED_NODE_TYPES),'registryExtra':sorted(set(registry.get_all_types())-APPROVED_NODE_TYPES),'approvedMissingExecutor':sorted(APPROVED_NODE_TYPES-set(registry.get_all_types())),'scriptExecutedTypes':len(report['executedModuleTypes']),'supplementalScenarios':supplemental,'executedTypes':len(executed),'statusCounts':dict(Counter(r['status'] for r in rows)),'categoryCounts':dict(Counter(r['category'] for r in rows)),'nodes':rows}
(root/'coverage.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
lines=['# 逐节点覆盖台账','','日期：2026-09-28；状态：confirmed。来源：生产注册表、批准集合与本次实际结果。','',f"生产注册表 {len(rows)} 种；批准集合 {len(APPROVED_NODE_TYPES)} 种；差集 custom_module；批准集合无缺失执行器。执行、结构处理、未执行严格区分。",'','| 节点 | 批准集合 | 状态 | 分类 / 先决条件 |','| --- | --- | --- | --- |']
for r in rows:lines.append(f"| `{r['moduleType']}` | {'是' if r['approved'] else '自定义模块入口'} | {r['status']} | {r['category']}：{r['reason']} |")
(root/'coverage.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:v for k,v in ledger.items() if k!='nodes'},ensure_ascii=False,indent=2))
