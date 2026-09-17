// Dedicated UUID-leak E2E. This intentionally owns its scenario code instead
// of introducing another shared QA framework.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFile } from 'node:child_process'
import { constants } from 'node:fs'
import { cp, mkdir, mkdtemp, readFile, realpath, readdir, stat, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { checkCdpPage } from './qa-project-uuid-leaks.mjs'
import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')
const scenario = argument('--scenario', 'runs')
const manual = process.argv.includes('--manual')
const startedAt = new Date().toISOString()
assert.ok(['runs', 'data', 'references'].includes(scenario), '--scenario must be runs, data, or references')
const unimplemented = ['强制停止确认', '失效资源引用状态']
const owner = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-project-uuid-qa-')))
const workspace = join(owner, 'workspace')
const evidence = join(root, 'docs/project-management/implementation/pm3/qa-runs', `uuid-${scenario}-${Date.now()}`)
await mkdir(workspace); await mkdir(evidence, { recursive: true })
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))

let desktop, renderer, native, fixture, pausedWorker
const screenshots = [], knownIds = new Set(), businessIds = [], faultInjections = []
const systemIdKeys = new Set(['projectId', 'automationId', 'workflowId', 'profileId', 'batchId', 'taskId', 'runId', 'runRequestId', 'inputSnapshotId', 'nodeId', 'edgeId', 'fieldId', 'statusId', 'tableId', 'inputId', 'environmentId', 'eventId', 'nodeVisitId', 'preparedContentId', 'artifactId', 'operationId', 'requestId'])
const businessPayloadKeys = new Set(['value', 'parameters', 'parameterValues', 'inputs', 'capabilityBindings', 'resourceRequest', 'error', 'details'])
let kernelVersion

try {
  fixture = await startFixture()
  if (scenario === 'runs') kernelVersion = await copyKernel()
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.uuidQaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');uuidQaElectron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
  await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await visible('本地服务正常', 30_000)
  const runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
  assert.equal(resolve(runtime.workspaceKey), workspace)
  const project = await createProject(runtime)
  if (scenario === 'runs') await runFlow(runtime, project)
  else if (scenario === 'data') await dataFlow(runtime, project)
  else await referencesFlow(runtime, project)
  const preparation = scenario === 'data'
    ? ['系统身份表、字段、状态和记录均由UI创建', '字段身份表与记录通过真实Excel检查、字段和身份映射、导入服务创建；仅原生文件选择结果由QA定向到工具生成的XLSX']
    : scenario === 'references'
      ? ['项目由UI创建', '工作流通过生产WorkflowService创建；失效资源引用通过正式自动化HTTP写入契约准备']
      : ['工作流与浏览器配置为运行夹具；项目与自动化由UI创建', '保存、启动和确认提交按钮通过可见且启用的唯一按钮聚焦后发送CDP Enter，覆盖键盘用户路径']
  const remaining = scenario === 'runs' ? ['失效资源引用状态'] : scenario === 'references' ? ['强制停止确认'] : unimplemented
  const result = { status: 'scenario-passed', coverage: 'partial', scenario, owner, workspace, evidence, knownIds: [...knownIds], businessIds, screenshots, unimplemented: remaining, preparation, faultInjections, viewport: await renderer.evaluate('({width:innerWidth,height:innerHeight,devicePixelRatio})'), source: { head: await sourceHead(), scriptSha256: await hashFile(new URL(import.meta.url)), mainBundleSha256: await hashFile(join(root,'apps/desktop/out/main/index.js')), rendererHtmlSha256: await hashFile(join(root,'apps/desktop/out/renderer/index.html')), rendererAssetsSha256: await hashTree(join(root,'apps/desktop/out/renderer/assets')), rendererSourceSha256: await hashTree(join(root,'apps/desktop/src/renderer'), /\.(?:ts|tsx|css)$/) }, startedAt, finishedAt: new Date().toISOString() }
  await writeFile(join(evidence, 'result.json'), JSON.stringify(result, null, 2))
  console.log(JSON.stringify(result, null, 2))
  if (manual) { console.log(JSON.stringify({ manual: true, workspace, message: '隔离应用与本地夹具保持运行；按 Ctrl+C 清理进程并退出' })); await new Promise(resolveExit => process.once('SIGINT', resolveExit)) }
} catch (error) {
  if (renderer) await capture('failure').catch(() => undefined)
  throw error
} finally {
  if (pausedWorker) await resumePausedWorker(pausedWorker).catch(() => undefined)
  if (native) await native.evaluate('if(globalThis.__uuidQaOriginalOpenDialog)uuidQaElectron.dialog.showOpenDialog=globalThis.__uuidQaOriginalOpenDialog;true').catch(() => undefined)
  renderer?.close(); native?.close(); await stop(desktop?.child)
  if (fixture) await new Promise(resolveClose => fixture.server.close(resolveClose))
}

async function createProject(runtime) {
  await click('项目'); await click('新建项目'); await input('#project-name', `UUID专项${scenario}`); await click('创建项目'); await visible('项目资料')
  const project = (await api(runtime, `/projects?q=UUID专项${scenario}`)).items[0]
  collect(project)
  return project
}

async function runFlow(runtime, project) {
  const workflow = await seedWorkflow(runtime.workspaceKey, fixture.url)
  const profile = await seedProfile(runtime, kernelVersion)
  collect(workflow, profile)
  workflow.nodeIds.forEach(id => knownIds.add(id))
  await click('自动化', '[aria-label="项目功能"] button'); await visible('新建自动化'); await click('新建自动化')
  await input('[aria-label="自动化名称"]', '参数运行验收'); await input('[aria-label="用途说明"]', 'UUID专项')
  await click('关联工作流', '[role=combobox]'); await click('UUID冻结节点验收流程', '[role=option]')
  await click('资源与环境', '[role=tab]'); await chooseNextOption('浏览器配置来源'); await chooseNextOption('浏览器配置'); await activate('保存配置'); await visible('自动化已创建')
  const automation = (await api(runtime, `/projects/${project.projectId}/automations`)).items[0]; collect(automation)
  await click('启动运行'); await visible('启动自动化'); await input('[aria-label="本次任务数"]', '2'); await activate('启动 2 个任务'); await visible('本批次任务', 30_000)
  const batch = (await api(runtime, `/projects/${project.projectId}/batches?pageSize=20`)).items[0]; collect(batch)
  const tasks = (await api(runtime, `/projects/${project.projectId}/tasks?batchId=${batch.batchId}`)).items; assert.equal(tasks.length, 2); tasks.forEach(collect)
  assert.deepEqual(tasks.map(task => task.taskOrdinal).sort((left, right) => left - right), [1, 2])
  await checkpoint('01-batch-detail')
  await waitTerminal(runtime, project.projectId, batch.batchId)
  await activate('返回批次列表'); await checkpoint('02-batch-directory')
  const fault = await injectBatchReadFailure(runtime, project.projectId, batch.batchId)
  await activate('刷新记录', fault.arm); await visible('刷新失败，当前显示上次读取的记录：操作失败，请重试'); await visible('参数运行验收'); await checkpoint('02a-synthetic-refresh-error'); await fault.finish()
  await activate('重试读取'); await waitFor(renderer, "!document.querySelector('[role=alert]')", 'batch refresh recovery')
  await click('任务记录', '[role=tab]'); await visible('任务 1'); await visible('任务 2'); await checkpoint('03-task-directory')
  for (const task of tasks) collect(await api(runtime, `/projects/${project.projectId}/tasks/${task.taskId}`))
  const evidenceBase = `/projects/${project.projectId}/tasks/${tasks[0].taskId}`
  for (const suffix of ['node-attempts', 'logs', 'outputs', 'artifacts']) collect(await api(runtime, `${evidenceBase}/${suffix}`))
  await click('查看任务', 'tbody tr:first-child button'); await visible('输入与输出'); await visible('填写业务值'); await checkpoint('04-task-logs')
  await click('输入与输出', '[role=tab]'); await checkpoint('05-task-io')
  await click('异常与证据', '[role=tab]'); await checkpoint('06-task-evidence')
  await stopDialogFlow(runtime, project)
}

async function stopDialogFlow(runtime, project) {
  const workflow = await seedWorkflow(runtime.workspaceKey, fixture.slowUrl, 'UUID慢任务停止流程'); knownIds.add(workflow.workflowId); workflow.nodeIds.forEach(id => knownIds.add(id))
  await click('自动化', '[aria-label="项目功能"] button'); await visible('新建自动化'); await click('新建自动化')
  await input('[aria-label="自动化名称"]', '停止确认验收'); await input('[aria-label="用途说明"]', '慢任务停止与强停确认')
  await click('关联工作流', '[role=combobox]'); await click('UUID慢任务停止流程', '[role=option]')
  await click('资源与环境', '[role=tab]'); await chooseNextOption('浏览器配置来源'); await chooseNextOption('浏览器配置'); await activate('保存配置'); await visible('自动化已创建')
  const automation = (await api(runtime, `/projects/${project.projectId}/automations?q=停止确认验收`)).items[0]; collect(automation)
  await click('启动运行'); await visible('启动自动化'); await input('[aria-label="本次任务数"]', '2'); await activate('启动 2 个任务'); await visible('本批次任务', 30_000)
  const batch = (await api(runtime, `/projects/${project.projectId}/batches?automationId=${automation.automationId}&pageSize=20`)).items[0]; collect(batch)
  const tasks = (await api(runtime, `/projects/${project.projectId}/tasks?batchId=${batch.batchId}`)).items; assert.equal(tasks.length, 2); tasks.forEach(collect); assert.deepEqual(tasks.map(task => task.taskOrdinal).sort((a,b) => a-b), [1,2])
  await waitForRunningAttempt(runtime,project.projectId,tasks)
  pausedWorker=await pauseOwnedWorkflowWorker()
  const processFault={kind:'synthetic-os-process-pause',target:'the unique workflow worker in this isolated Electron process tree',purpose:'simulate an unresponsive worker while preserving real stop, grace-period, force-stop, and cleanup handling',processExitConfirmed:false};faultInjections.push(processFault)
  await checkpoint('07-slow-batch-detail')
  await click('停止批次'); await visible('停止当前批次？'); await checkpoint('08-stop-dialog'); await click('取消')
  await click('停止批次'); await activate('确认停止'); await visible('正在停止', 10_000); await wait(31_000); await click('强制停止'); await visible('强制停止批次？')
  const disabled = await renderer.evaluate("[...document.querySelectorAll('button')].find(button=>button.textContent.trim()==='确认强制停止')?.disabled"); assert.equal(disabled, true)
  await input('[aria-label="确认强制停止"]', '强制停止'); await checkpoint('09-force-stop-dialog'); await activate('确认强制停止')
  await waitTerminal(runtime, project.projectId, batch.batchId)
  await waitForWorkerExit(pausedWorker);processFault.processExitConfirmed=true;pausedWorker=undefined
  await failedTaskFlow(runtime, project)
}

async function failedTaskFlow(runtime, project) {
  const workflow = await seedWorkflow(runtime.workspaceKey, fixture.url, 'UUID真实失败证据流程', true); knownIds.add(workflow.workflowId); workflow.nodeIds.forEach(id => knownIds.add(id))
  await click('自动化', '[aria-label="项目功能"] button'); await visible('新建自动化'); await click('新建自动化')
  await input('[aria-label="自动化名称"]', '真实失败证据验收'); await input('[aria-label="用途说明"]', '不存在元素的短超时失败')
  await click('关联工作流', '[role=combobox]'); await click('UUID真实失败证据流程', '[role=option]')
  await click('资源与环境', '[role=tab]'); await chooseNextOption('浏览器配置来源'); await chooseNextOption('浏览器配置'); await activate('保存配置'); await visible('自动化已创建')
  const automation = (await api(runtime, `/projects/${project.projectId}/automations?q=真实失败证据验收`)).items[0]; collect(automation)
  await click('启动运行'); await visible('启动自动化'); await input('[aria-label="本次任务数"]', '1'); await activate('启动 1 个任务'); await visible('本批次任务', 30_000)
  const batch = (await api(runtime, `/projects/${project.projectId}/batches?automationId=${automation.automationId}&pageSize=20`)).items[0]; collect(batch); await waitTerminal(runtime, project.projectId, batch.batchId)
  const tasks = (await api(runtime, `/projects/${project.projectId}/tasks?batchId=${batch.batchId}`)).items; assert.equal(tasks.length,1); assert.equal(tasks[0].taskOrdinal,1); tasks.forEach(collect)
  const base=`/projects/${project.projectId}/tasks/${tasks[0].taskId}`; collect(await api(runtime,base)); for(const suffix of ['node-attempts','logs','outputs','artifacts']) collect(await api(runtime,`${base}/${suffix}`))
  await click('查看任务', 'tbody tr:first-child button'); await visible('任务 1'); await visible('填写业务值'); await checkpoint('10-failed-task-logs')
  await click('异常与证据', '[role=tab]'); await visible('运行失败'); await visible('发生节点'); await visible('填写业务值'); await waitFor(renderer, "(()=>{const image=document.querySelector('img[alt^=\"失败截图：\"]');return image?.complete&&image.naturalWidth>0})()", 'inline failure screenshot image', 30_000); await checkpoint('11-failed-task-evidence')
  const previewLabel=await renderer.evaluate("document.querySelector('button[aria-label^=\"放大失败截图：\"]')?.getAttribute('aria-label')"); assert.ok(previewLabel); await click(previewLabel); await waitFor(renderer, "(()=>{const image=document.querySelector('[role=dialog] img[alt^=\"失败截图：\"]');return image?.complete&&image.naturalWidth>0})()", 'failure screenshot preview image', 30_000); await checkpoint('12-failed-screenshot-preview'); await key('Escape')
}

async function dataFlow(runtime, project) {
  await click('数据', '[aria-label="项目功能"] button'); await visible('新建数据表'); await click('新建数据表')
  await input('#data-table-name', '系统身份资料'); await click('创建数据表'); await visible('系统身份资料')
  const table = (await api(runtime, `/projects/${project.projectId}/tables`)).items[0]; assert.equal(table.identity.mode, 'system'); collect(table)
  if (typeof table.datasetGeneration === 'string') knownIds.add(table.datasetGeneration)
  const base = `/projects/${project.projectId}/tables/${table.tableId}`
  await click('字段与校验', '[role=tab]'); await click('新增字段'); await input('#field-name', '业务标题'); await input('#field-key', 'title'); await click('应用到草稿'); await waitFor(renderer, "!document.querySelector('#schema-field-drawer-form')", 'field drawer closes')
  await click('新增字段'); await input('#field-name', '外部参考'); await input('#field-key', 'external_reference'); await click('应用到草稿'); await waitFor(renderer, "!document.querySelector('#schema-field-drawer-form')", 'second field drawer closes')
  await click('保存字段'); await visible('保存字段前核对影响'); await click('确认保存字段')
  const fields = (await api(runtime, `${base}/fields`)).items; assert.equal(fields.length, 2); fields.forEach(collect)
  await click('数据状态', '[role=tab]'); await click('新增状态'); await input('[role="dialog"] input[name="name"]', '待处理'); await click('创建状态'); const status = (await api(runtime, `${base}/statuses`)).items[0]; collect(status)
  await click('数据记录', '[role=tab]'); await click('新增行'); await doubleClickGridCell('第 1 行 · 业务标题'); await input('textarea[aria-label="第 1 行 · 业务标题"]', '温室光照笔记')
  await doubleClickGridCell('第 1 行 · 外部参考')
  const businessUuid = crypto.randomUUID(); businessIds.push(businessUuid); await input('textarea[aria-label="第 1 行 · 外部参考"]', businessUuid); await click('保存 1 行'); await visible(businessUuid); await assertExactText('[data-record-open]', '查看记录 温室光照笔记', 'system record list action')
  const record = (await api(runtime, `${base}/records?datasetGeneration=${table.datasetGeneration}`)).items[0]; collect(record)
  assert.equal(record.ref.recordKey.type, 'uuid'); knownIds.add(record.ref.recordKey.value)
  await checkpoint('11-system-record-directory', [businessUuid])
  const viewLabel = await renderer.evaluate("document.querySelector('[data-record-open]')?.getAttribute('aria-label')"); assert.equal(viewLabel, '查看记录 温室光照笔记'); await click(viewLabel); await waitFor(renderer, "!!document.querySelector('[data-record-page=detail]')", 'system record detail'); await assertExactText('[data-record-page=detail] h2', '温室光照笔记', 'system record detail title'); await checkpoint('12-system-record-detail', [businessUuid])
  await click('编辑记录'); await visible('编辑记录'); await assertExactText('main h2', '编辑记录 · 温室光照笔记', 'system record edit title'); await checkpoint('13-system-record-edit'); await click('取消')
  await waitFor(renderer, "!!document.querySelector('[data-record-open]')", 'system records after edit cancel'); const reopenLabel=await renderer.evaluate("document.querySelector('[data-record-open]')?.getAttribute('aria-label')"); await click(reopenLabel); await waitFor(renderer, "!!document.querySelector('[data-record-page=detail]')", 'system record reopened')
  await click('记录业务状态', '[aria-label="记录业务状态"]'); await assertExactText('[data-record-page=detail] h2', '温室光照笔记', 'status record title'); await checkpoint('14-system-record-status', [businessUuid]); await key('Escape')
  await click('更多记录操作'); await click('删除记录', '[role=menuitem]'); await click('检查删除影响'); await assertExactText('[role=dialog] strong', '温室光照笔记', 'delete record target'); await checkpoint('15-system-record-delete', [businessUuid]); await click('取消')
  await fieldIdentityFlow(runtime, project)
}

async function referencesFlow(runtime, project) {
  const workflow = await seedWorkflow(runtime.workspaceKey, fixture.url); knownIds.add(workflow.workflowId); workflow.nodeIds.forEach(id => knownIds.add(id))
  const environmentId = crypto.randomUUID(), modelProviderId = crypto.randomUUID(), proxyId = crypto.randomUUID(), profileId = crypto.randomUUID()
  for (const id of [environmentId, modelProviderId, proxyId, profileId]) knownIds.add(id)
  const standard = { description: '失效资源引用专项夹具', workflowId: workflow.workflowId, inputPlan: { inputs: [] }, parameterSchema: [], runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 } }
  const fixed = await api(runtime, `/projects/${project.projectId}/automations`, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { ...standard, name: '历史环境引用验收', environmentPolicy: { source: 'fixedEnvironment', environmentId, modelProviderId, proxyOverride: { mode: 'fixed', proxyId } } } }); collect(fixed)
  const profileWorkflow = await seedWorkflow(runtime.workspaceKey, fixture.url); knownIds.add(profileWorkflow.workflowId); profileWorkflow.nodeIds.forEach(id => knownIds.add(id))
  const profile = await api(runtime, `/projects/${project.projectId}/automations`, { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { ...standard, workflowId: profileWorkflow.workflowId, name: '历史浏览器引用验收', environmentPolicy: { source: 'newFromProfile', profileId } } }); collect(profile)
  await click('自动化', '[aria-label="项目功能"] button'); await visible('历史环境引用验收'); await click('打开自动化 历史环境引用验收'); await click('资源与环境', '[role=tab]')
  for (const label of ['已保存的环境引用暂不可用', '已保存的模型提供方引用暂不可用', '已保存的代理引用暂不可用']) await visible(label)
  await checkpoint('31-unavailable-fixed-environment')
  const resourceFault=await injectResourceReadFailure(runtime,'/api/v1/profiles',environmentId); await renderer.command('Page.reload'); await wait(500); await visible('历史环境引用验收',30_000); await visible('部分资料读取失败，当前草稿已保留。操作失败，请重试',30_000); await click('资源与环境','[role=tab]'); await visible('已保存的环境引用暂不可用'); await checkpoint('31a-synthetic-resource-error'); await resourceFault.finish()
  await activate('重新读取资料'); await waitFor(renderer,"!document.querySelector('[role=alert]')",'automation resource read recovery',30_000); await visible('已保存的环境引用暂不可用')
  await click('模型提供方', '[role=combobox]'); await visible('已保存的模型提供方引用暂不可用'); await checkpoint('32-unavailable-model-option'); await key('Escape')
  await click('固定代理', '[role=combobox]'); await visible('已保存的代理引用暂不可用'); await checkpoint('33-unavailable-proxy-option'); await key('Escape')
  await click('返回自动化目录'); await click('打开自动化 历史浏览器引用验收'); await click('资源与环境', '[role=tab]'); await visible('已保存的浏览器配置引用暂不可用'); await click('浏览器配置', '[role=combobox]'); await checkpoint('34-unavailable-browser-profile-option')
}

async function injectBatchReadFailure(runtime, projectId, leakedId) {
  const requestId = crypto.randomUUID(); knownIds.add(requestId); let armed = false, targetUrl = null, attempts = 0
  const body = Buffer.from(JSON.stringify({ error: { code: 'UNKNOWN_UUID_QA', message: `测试注入原始消息 ${leakedId}`, requestId } })).toString('base64')
  const listener = event => { const message=JSON.parse(event.data);if(message.method!=='Fetch.requestPaused')return;const {requestId:pausedId,request}=message.params;const url=new URL(request.url);const directoryRead=armed&&request.method==='GET'&&url.pathname.endsWith(`/projects/${projectId}/batches`);if(!targetUrl&&directoryRead)targetUrl=request.url;const matches=armed&&attempts<3&&request.url===targetUrl;if(matches){attempts++;void renderer.command('Fetch.fulfillRequest',{requestId:pausedId,responseCode:500,responseHeaders:[{name:'content-type',value:'application/json'}],body})}else void renderer.command('Fetch.continueRequest',{requestId:pausedId}) }
  renderer.socket.addEventListener('message', listener); await renderer.command('Fetch.enable',{patterns:[{urlPattern:`${runtime.sidecar.baseUrl}/api/v1/projects/*/batches*`,requestStage:'Response'}]})
  faultInjections.push({ kind: 'synthetic-http-responses', target: 'one batch directory refresh including all query retries', httpAttempts: 3, code: 'UNKNOWN_UUID_QA', purpose: 'verify retained content and safe unknown-error presentation; not a natural backend failure' })
  return { arm:()=>{armed=true}, finish:async()=>{await renderer.command('Fetch.disable');renderer.socket.removeEventListener('message',listener);assert.ok(targetUrl,'synthetic batch directory URL must be bound');assert.equal(attempts,3,'one refresh plus retry=2 must receive three synthetic failures')} }
}

async function injectResourceReadFailure(runtime, path, leakedId) {
  const requestId=crypto.randomUUID();knownIds.add(requestId);let targetUrl=null,attempts=0
  const body=Buffer.from(JSON.stringify({error:{code:'UNKNOWN_UUID_QA',message:`测试注入原始消息 ${leakedId}`,requestId}})).toString('base64')
  const listener=event=>{const message=JSON.parse(event.data);if(message.method!=='Fetch.requestPaused')return;const {requestId:pausedId,request}=message.params;const matchesPath=request.method==='GET'&&new URL(request.url).pathname===path;if(!targetUrl&&matchesPath)targetUrl=request.url;const matches=attempts<3&&request.url===targetUrl;if(matches){attempts++;void renderer.command('Fetch.fulfillRequest',{requestId:pausedId,responseCode:500,responseHeaders:[{name:'content-type',value:'application/json'}],body})}else void renderer.command('Fetch.continueRequest',{requestId:pausedId})}
  renderer.socket.addEventListener('message',listener);await renderer.command('Fetch.enable',{patterns:[{urlPattern:`${runtime.sidecar.baseUrl}${path}*`,requestStage:'Response'}]})
  faultInjections.push({kind:'synthetic-http-responses',target:'automation profile resource read after page reload',httpAttempts:3,code:'UNKNOWN_UUID_QA',purpose:'verify retained automation content and safe resource-read error presentation; not a natural backend failure'})
  return{finish:async()=>{await renderer.command('Fetch.disable');renderer.socket.removeEventListener('message',listener);assert.ok(targetUrl,'synthetic resource URL must be bound');assert.equal(attempts,3,'resource read plus retry=2 must receive three synthetic failures')}}
}

async function fieldIdentityFlow(runtime, project) {
  const fieldUuid = crypto.randomUUID(); businessIds.push(fieldUuid)
  const workbook = join(owner, 'field-identity.xlsx')
  const workbookCode = `from openpyxl import Workbook\nimport sys\nb=Workbook();s=b.active;s.title='业务身份资料';s.append(['业务编号','标题']);s.append([sys.argv[2],'业务UUID记录']);b.save(sys.argv[1])`
  await exec('uv', ['run','--project',join(root,'apps/backend'),'python','-c',workbookCode,workbook,fieldUuid], { cwd: root })
  await click('返回记录列表'); await click('返回数据表'); await visible('从 Excel 导入')
  await native.evaluate(`globalThis.__uuidQaOriginalOpenDialog??=uuidQaElectron.dialog.showOpenDialog;uuidQaElectron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[${JSON.stringify(workbook)}]});true`)
  await click('从 Excel 导入'); await click('选择 Excel 文件'); await click('检查文件'); await waitFor(renderer, "!!document.querySelector('[aria-label=工作表]')", 'Excel inspection', 30_000)
  await click('工作表', '[aria-label="工作表"]'); await clickContains('业务身份资料', '[role=option]'); await click('继续字段映射'); await visible('字段映射'); await click('记录身份', '[role=combobox]'); await click('业务编号（候选）', '[role=option]'); await click('继续导入')
  await input('[aria-label="数据表名称"]', '业务身份资料'); await click('确认并开始导入'); await waitFor(renderer, "document.body.innerText.includes('业务身份资料')&&!document.body.innerText.includes('从 Excel 新建数据表')", 'field identity import', 30_000)
  await native.evaluate('uuidQaElectron.dialog.showOpenDialog=globalThis.__uuidQaOriginalOpenDialog;true')
  const table = (await api(runtime, `/projects/${project.projectId}/tables?q=业务身份资料`)).items[0]; assert.equal(table.identity.mode, 'field'); collect(table); knownIds.add(table.datasetGeneration)
  const base = `/projects/${project.projectId}/tables/${table.tableId}`
  const field = (await api(runtime, `${base}/fields`)).items.find(item => item.ref.fieldId === table.identity.fieldId); assert.ok(field); collect(field)
  await click('打开数据表：业务身份资料'); await visible(fieldUuid)
  const record = (await api(runtime, `${base}/records?datasetGeneration=${table.datasetGeneration}`)).items[0]
  assert.equal(record.ref.recordKey.value, fieldUuid); assert.equal(record.ref.recordKey.type, 'text')
  await checkpoint('21-field-identity-directory', [fieldUuid])
  await click(`查看记录 ${fieldUuid}`); await waitFor(renderer, "!!document.querySelector('[data-record-page=detail]')", 'field identity detail'); await checkpoint('22-field-identity-detail', [fieldUuid])
  await click('编辑记录'); await visible('编辑记录'); await checkpoint('23-field-identity-edit', [fieldUuid]); await click('取消')
}

async function checkpoint(name, visibleBusinessIds = []) { await capture(name); await checkCdpPage(renderer, [...knownIds], visibleBusinessIds) }
async function capture(name) { const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' }); const file = join(evidence, `${name}.png`); await writeFile(file, Buffer.from(data, 'base64')); screenshots.push(file) }
function collect(value) { walk(value, (key, item) => { if (systemIdKeys.has(key) && typeof item === 'string' && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(item)) knownIds.add(item) }) }
function walk(value, visit, key = '') { if (Array.isArray(value)) value.forEach(item => walk(item, visit, key)); else if (value && typeof value === 'object') Object.entries(value).forEach(([childKey, item]) => { visit(childKey, item); if (!businessPayloadKeys.has(childKey)) walk(item, visit, childKey) }) }
async function api(runtime, path, init = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, { ...init, headers: { 'x-autoflow-token': runtime.sidecar.token, ...(init.body ? { 'content-type': 'application/json' } : {}), ...init.headers }, ...(init.body && typeof init.body !== 'string' ? { body: JSON.stringify(init.body) } : {}) }); const text = await response.text(); assert.ok(response.ok, `${path}: ${response.status} ${text}`); return JSON.parse(text) }
async function visible(text, timeout = 10_000) { return waitFor(renderer, `document.body.innerText.includes(${JSON.stringify(text)})`, text, timeout) }
async function assertExactText(selector, expected, label) { const actual = await renderer.evaluate(`document.querySelector(${JSON.stringify(selector)})?.${selector === '[data-record-open]' ? "getAttribute('aria-label')" : 'textContent.trim()'}`); assert.equal(actual, expected, label) }
async function click(text, selector = 'button') { const point = await waitFor(renderer, `(()=>{const a=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length&&!e.disabled&&(e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}));if(a.length!==1)return null;const e=a[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `control ${text}`); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); for (const type of ['mousePressed','mouseReleased']) await renderer.command('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1}); await wait(120) }
async function clickContains(text, selector) { const point = await waitFor(renderer, `(()=>{const a=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length&&!e.disabled&&e.textContent.includes(${JSON.stringify(text)}));if(a.length!==1)return null;const e=a[0];e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `control containing ${text}`); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); for (const type of ['mousePressed','mouseReleased']) await renderer.command('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1}); await wait(120) }
async function activate(text, beforePress) { await waitFor(renderer, `(()=>{const a=[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length&&!e.disabled&&e.textContent.includes(${JSON.stringify(text)}));if(a.length!==1)return false;a[0].focus();return document.activeElement===a[0]})()`, `keyboard activation ${text}`); if(beforePress)await beforePress();const event={key:' ',code:'Space',windowsVirtualKeyCode:32,nativeVirtualKeyCode:32};await renderer.command('Input.dispatchKeyEvent',{type:'rawKeyDown',...event});await renderer.command('Input.dispatchKeyEvent',{type:'char',...event,text:' '});await renderer.command('Input.dispatchKeyEvent',{type:'keyUp',...event});await wait(120) }
async function input(selector, value) { await waitFor(renderer, `!!document.querySelector(${JSON.stringify(selector)})`, selector); await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();e.select();true})()`); await renderer.command('Input.insertText',{text:value}) }
async function doubleClickGridCell(label) { const point=await waitFor(renderer,`(()=>{const e=document.querySelector('[role="gridcell"][aria-label=${JSON.stringify(label)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`,label);await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point});await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:2});await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:2}) }
async function key(value) { const keyCode=value==='Enter'?13:value==='Escape'?27:undefined;const event={key:value,code:value,...(keyCode?{windowsVirtualKeyCode:keyCode,nativeVirtualKeyCode:keyCode}:{})};await renderer.command('Input.dispatchKeyEvent',{type:'keyDown',...event});await renderer.command('Input.dispatchKeyEvent',{type:'keyUp',...event});await wait(80) }
async function chooseNextOption(label) { await click(label, '[role=combobox]'); for (const key of ['ArrowDown','Enter']) { await renderer.command('Input.dispatchKeyEvent',{type:'keyDown',key,code:key}); await renderer.command('Input.dispatchKeyEvent',{type:'keyUp',key,code:key}) } }
async function waitTerminal(runtime, projectId, batchId) { for (let index=0; index<600; index++) { const detail=await api(runtime,`/projects/${projectId}/batches/${batchId}`); if(['completed','failed','stopped','interrupted'].includes(detail.batch.status)) return detail; await wait(200) } throw new Error('batch did not finish') }
async function waitForRunningAttempt(runtime,projectId,tasks){for(let index=0;index<150;index++){for(const task of tasks){const attempts=await api(runtime,`/projects/${projectId}/tasks/${task.taskId}/node-attempts`);collect(attempts);if(attempts.items.some(item=>item.status==='running'&&item.nodeName==='打开验收页'))return}await wait(200)}throw new Error('slow batch did not enter the frozen open-page attempt')}
async function pauseOwnedWorkflowWorker(){const {stdout}=await exec('ps',['-axo','pid=,ppid=,command=']);const rows=stdout.split('\n').map(line=>line.trim()).filter(Boolean).map(line=>{const match=line.match(/^(\d+)\s+(\d+)\s+(.*)$/);return match?{pid:Number(match[1]),ppid:Number(match[2]),command:match[3]}:null}).filter(Boolean);const owned=new Set([desktop.child.pid]);for(let changed=true;changed;){changed=false;for(const row of rows)if(owned.has(row.ppid)&&!owned.has(row.pid)){owned.add(row.pid);changed=true}}const matches=rows.filter(row=>owned.has(row.pid)&&/(?:^|\s)(?:-m\s+autoflow\s+--workflow-worker|--workflow-worker)(?:\s|$)/.test(row.command));assert.equal(matches.length,1,'isolated Electron tree must own exactly one workflow worker');const worker=matches[0];const started=(await exec('ps',['-p',String(worker.pid),'-o','lstart='])).stdout.trim();assert.ok(started);process.kill(worker.pid,'SIGSTOP');return{pid:worker.pid,started}}
async function resumePausedWorker(worker){const started=(await exec('ps',['-p',String(worker.pid),'-o','lstart='])).stdout.trim();if(started===worker.started)process.kill(worker.pid,'SIGCONT')}
async function waitForWorkerExit(worker){for(let index=0;index<100;index++){const current=await exec('ps',['-p',String(worker.pid),'-o','lstart=']).then(result=>result.stdout.trim()).catch(()=>null);if(current!==worker.started)return;await wait(100)}throw new Error('force stop reached a terminal batch but the paused workflow worker PID/birth still exists')}
function argument(name, fallback) { const index=process.argv.indexOf(name); return index<0?fallback:process.argv[index+1] }
async function sourceHead() { if (process.env.UUID_SOURCE_HEAD) return process.env.UUID_SOURCE_HEAD; return (await exec('git',['rev-parse','HEAD'],{cwd:root})).stdout.trim() }
async function hashFile(path) { return createHash('sha256').update(await readFile(path)).digest('hex') }
async function hashTree(directory, include = /./) { const digest=createHash('sha256'); for(const name of (await readdir(directory,{recursive:true})).filter(name=>include.test(name)).sort()){const path=join(directory,name);if((await stat(path)).isFile())digest.update(name).update(await readFile(path))} return digest.digest('hex') }

async function startFixture() { const { createServer } = await import('node:http'); const html='<input id="field"><button id="button" data-clicked="no">确认</button><script>button.onclick=()=>button.dataset.clicked="yes"</script>'; const server=createServer((request,response)=>{const send=()=>{response.writeHead(200,{'content-type':'text/html'});response.end(html)};if(request.url==='/slow'){const timer=setTimeout(send,120_000);timer.unref()}else send()}); await new Promise(resolveReady=>server.listen(0,'127.0.0.1',resolveReady)); const base=`http://127.0.0.1:${server.address().port}`; return {server,url:`${base}/`,slowUrl:`${base}/slow`} }
async function copyKernel() { const directory=join(homedir(),'Library','Application Support','@autoflow','desktop','data','kernels'); const candidates=(await readdir(directory,{withFileTypes:true})).filter(item=>item.isDirectory()&&item.name.startsWith('chromium-')).map(item=>join(directory,item.name)).sort().reverse(); for(const candidate of candidates){const source=await realpath(candidate), executable=kernelExecutablePath(source,process.platform);if((await stat(executable).catch(()=>null))?.isFile()){const destination=join(workspace,'data','kernels',basename(source));await cp(source,destination,{recursive:true,dereference:false,verbatimSymlinks:true,mode:constants.COPYFILE_FICLONE});return basename(source).slice('chromium-'.length)}} throw new Error('未找到可用CloakBrowser内核') }
async function seedProfile(runtime, browserVersion) { assert.ok(browserVersion); return api(runtime,'/profiles',{method:'POST',body:{name:'UUID专项浏览器',description:'',startUrl:'about:blank',locale:null,timezone:null,geoip:false,headless:true,humanize:false,humanPreset:'default',userAgent:null,viewportJson:null,colorScheme:null,extensionPathsJson:[],expertArgsJson:[],browserVersion,browserEdition:'public',releaseChannel:'stable',proxyMode:'none',proxyId:null,proxyPoolId:null}}) }
async function seedWorkflow(workspaceKey,url,name='UUID冻结节点验收流程',fail=false) { const ids=Array.from({length:4},()=>crypto.randomUUID()); const workflowId=crypto.randomUUID(); const code=`from pathlib import Path\nfrom uuid import uuid4\nimport json,sys\nfrom autoflow.application.workflows.service import WorkflowService\nfrom autoflow.infrastructure.database.session import create_session_factory\nfrom autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository\nfrom autoflow.infrastructure.filesystem.paths import AppPaths\nfrom tests.fixtures.workflows import workflow_payload\nf=create_session_factory(AppPaths.from_data_dir(Path(sys.argv[1])).database);d=workflow_payload(sys.argv[2]);d['content']['name']=sys.argv[5];ids=json.loads(sys.argv[4]);n=d['content']['nodes'];edges=d['content']['edges'];assert len(n)==4 and len(edges)==3;[(x.update(id=ids[i]),x['data'].update(name=['打开验收页','填写业务值','点击确认','读取结果'][i])) for i,x in enumerate(n)];n[0]['data']['url']=sys.argv[3];n[1]['data'].update(selector='#missing-field' if sys.argv[6]=='1' else '#field',text='业务输入',clearBefore=True,**({'timeout':.1} if sys.argv[6]=='1' else {}));n[2]['data']['selector']='#button';n[3]['data'].update(selector='#button',attribute='data-clicked');[e.update(id=str(uuid4()),source=ids[i],target=ids[i+1]) for i,e in enumerate(edges)];print(WorkflowService(SqlAlchemyWorkflowRepository(f)).create(d,str(uuid4())).workflow_id);f.dispose()`; const {stdout}=await exec('uv',['run','--directory','apps/backend','python','-c',code,workspaceKey,workflowId,url,JSON.stringify(ids),name,fail?'1':'0'],{cwd:root}); return {workflowId:stdout.trim(),nodeIds:ids} }
