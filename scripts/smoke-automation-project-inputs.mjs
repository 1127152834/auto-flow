import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, connectCdp, waitFor, wait } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const workspace = await mkdtemp(join(tmpdir(), 'autoflow-project-inputs-'))
const evidence = resolve(process.argv[2] ?? join(root, 'artifacts/project-inputs'))
await mkdir(evidence, { recursive: true })
await rm(join(evidence, 'verification.json'), { force: true })
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
let desktop, studio, runtime
async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
  const response = await fetch(runtime.sidecar.baseUrl + path, { method, headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
  const result = await response.json()
  assert.ok(response.ok, `${method} ${path}: ${response.status} ${JSON.stringify(result)}`)
  return result
}
async function click(label, selector = 'button') {
  const point = await waitFor(studio, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.getClientRects().length&&!e.disabled&&(e.textContent.trim().startsWith(${JSON.stringify(label)})||e.getAttribute('aria-label')===${JSON.stringify(label)}));if(!e)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, label)
  for (const type of ['mousePressed', 'mouseReleased']) await studio.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
}
async function capture(name) {
  const { data } = await studio.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(evidence, `${name}.png`), data, 'base64')
}
try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`], cliArgs: [] })
  await waitFor(desktop.cdp, "document.body.innerText.includes('本地服务正常')", 'isolated sidecar', 30000)
  runtime = await desktop.cdp.evaluate('window.autoflow.getRuntimeContext()')
  assert.ok(runtime.workspaceKey.includes(workspace), 'Only the test-owned workspace may be changed')
  const project = await api('/api/v1/projects', { name: '输入一体化验收' }), base = `/api/v1/projects/${project.projectId}`
  const table = await api(base + '/tables', { name: '账号表', sourceKind: 'local' })
  const field = (await api(`${base}/tables/${table.tableId}/fields`, { expectedTableRevision: 1, sourceColumnPolicy: 'localOnly', definition: { key: 'account', name: '账号', type: 'string', required: true, validation: {} } })).field
  const states = []
  for (const [index, name] of ['未注册', '已注册'].entries()) states.push((await api(`${base}/tables/${table.tableId}/statuses`, { expectedTableRevision: 2 + index, name, color: '#996644', order: index })))
  const records = []
  for (const code of ['A-001', 'A-002', 'A-003']) {
    const record = await api(`${base}/tables/${table.tableId}/records`, { datasetGeneration: table.datasetGeneration, values: [{ fieldId: field.ref.fieldId, value: code }] })
    await api(`${base}/tables/${table.tableId}/records/${Buffer.from(record.ref.recordKey.value).toString('base64url')}/status`, { datasetGeneration: table.datasetGeneration, recordKeyType: record.ref.recordKey.type, expectedStatusRevision: record.statusRevision, statusId: states[0].statusId }, 'PUT')
    records.push(record)
  }
  const inputId = randomUUID(), inputFieldId = randomUUID(), reference = `PROJECT_INPUTS['${inputId}']`
  const automation = await api(base + '/automations', { name: '逐条注册', description: '', inputPlan: { inputs: [{ inputId, alias: '账号对象', tableId: table.tableId, datasetGeneration: table.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId, inputFieldAlias: '账号', fieldRef: field.ref }], filter: { type: 'status', operator: 'eq', statusId: states[0].statusId }, orderBy: [{ fieldId: field.ref.fieldId, direction: 'asc' }] }] }, parameterSchema: [], environmentPolicy: { source: 'newFromProfile' }, runPolicy: { maxTasks: 10, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 60, manualDeadlineSeconds: 300 } })
  const grant = { tableId: table.tableId, datasetGeneration: table.datasetGeneration, fieldIds: [field.ref.fieldId], operations: ['setRecordStatus'], readPurposes: ['condition', 'derivedWrite'] }
  await api(`/api/workflows/${automation.workflowId}`, { id: automation.workflowId, projectId: project.projectId, name: '注册指定账号', expectedRevision: 1, clientRequestId: randomUUID(), browserEnvironmentVersion: 1, variables: [], nodes: [{ id: 'status', type: 'project_data', position: { x: 100, y: 100 }, data: { moduleType: 'project_data', label: '标记已注册', operation: 'setRecordStatus', currentInputId: inputId, bindingProjectId: project.projectId, tableGrant: grant, variableName: 'saved', arguments: { recordRef: `{${reference}['recordRef']}`, expectedStatusRevision: `{${reference}['statusRevision']}`, statusId: states[1].statusId } } }], edges: [] }, 'PUT')
  await desktop.cdp.evaluate(`window.autoflow.openAutomationStudio(${JSON.stringify({ workspaceKey: runtime.workspaceKey, instanceId: runtime.sidecar.instanceId, projectId: project.projectId, automationId: automation.automationId, workflowId: automation.workflowId })})`)
  let target
  for (let attempt = 0; attempt < 100 && !target; attempt++) { target = (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')); if (!target) await wait(100) }
  assert.ok(target)
  studio = await connectCdp(target.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "[...document.querySelectorAll('input')].some(input=>input.value==='注册指定账号')", 'owned workflow')
  await click('项目数据'); await click('调试输入')
  await waitFor(studio, "document.body.innerText.includes('A-001')", 'default first complete input')
  await capture('debug-default')
  await click('选择数据')
  await waitFor(studio, "Boolean(document.querySelector('[aria-label=搜索候选数据]'))", 'candidate search')
  await studio.evaluate("document.querySelector('[aria-label=搜索候选数据]').focus();true")
  await studio.command('Input.insertText', { text: 'A-003' }); await click('搜索', '[role=dialog] button')
  await waitFor(studio, "document.querySelectorAll('[role=dialog] input[type=radio]').length===1", 'only matching third candidate')
  await studio.evaluate("document.querySelector('[role=dialog] input[type=radio]').click();true")
  assert.ok(await studio.evaluate("(()=>{const e=document.querySelector('[role=dialog]'),s=getComputedStyle(e);return s.backgroundColor!=='rgba(0, 0, 0, 0)'&&Number(s.zIndex)>0})()"), 'Candidate dialog must be opaque and above the canvas')
  await capture('candidate-third')
  await click('使用此条')
  await waitFor(studio, "!document.querySelector('[role=dialog]')&&document.body.innerText.includes('A-003')", 'selected third object')
  await click('运行一次')
  console.log('Selected A-003 and requested one real task')
  let detail, batchId
  for (let attempt = 0; attempt < 300; attempt++) {
    const batches = await api(`${base}/batches?automationId=${automation.automationId}`)
    batchId = batches.items[0]?.batchId
    if (batchId) {
      const batch = await api(`${base}/batches/${batchId}`)
      if (batch.batch.status === 'completed') { const tasks = await api(`${base}/tasks?batchId=${batchId}`); assert.equal(tasks.items.length, 1); detail = await api(`${base}/tasks/${tasks.items[0].taskId}`); break }
    }
    await wait(200)
  }
  assert.equal(detail?.task.status, 'succeeded', JSON.stringify(detail) ?? 'No completed debug task')
  assert.deepEqual(detail.inputSnapshot.inputs[0].recordRef, records[2].ref)
  assert.equal(detail.inputSnapshot.inputs[0].statusId, states[0].statusId)
  await waitFor(studio, "!document.body.innerText.includes('停止运行')", 'run settled')
  await click('本次任务'); await capture('task-snapshot')
  assert.ok(await studio.evaluate("document.body.innerText.includes('A-003')"))
  const fresh = await api(`${base}/automations/${automation.automationId}/debug-inputs`, { expectedAutomationRevision: 1, choices: {} })
  assert.deepEqual(fresh.selection[inputId].recordRef, records[0].ref)
  const candidates = await api(`${base}/automations/${automation.automationId}/debug-inputs`, { expectedAutomationRevision: 1, choices: {}, inputId })
  assert.equal(candidates.items.length, 2)
  const batch = await api(`${base}/automations/${automation.automationId}/batches`, { expectedAutomationRevision: 1, parameters: {}, maxTasks: 1, concurrency: 1 })
  const normalId = batch.operation.result.batch.batchId
  for (let attempt = 0; attempt < 300; attempt++) { if ((await api(`${base}/batches/${normalId}`)).batch.status === 'completed') break; await wait(200) }
  const nextTask = (await api(`${base}/tasks?batchId=${normalId}`)).items[0]
  assert.equal(nextTask.status, 'succeeded')
  assert.deepEqual((await api(`${base}/tasks/${nextTask.taskId}`)).inputSnapshot.inputs[0].recordRef, records[0].ref)
  await writeFile(join(evidence, 'verification.json'), JSON.stringify({ status: 'passed', releaseAccepted: false, projectId: project.projectId, automationId: automation.automationId, workflowId: automation.workflowId, debugBatchId: batchId, normalBatchId: normalId, checks: ['server creates owned workflow', 'Studio validates automation context', 'default first input', 'single-record search selects third', 'real worker only processes selected third', 'original snapshot unchanged', 'record lease released', 'normal batch filters fresh data and selects first remaining'], screenshots: ['debug-default.png', 'candidate-third.png', 'task-snapshot.png'] }, null, 2))
  console.log('PASS: real Electron, production HTTP and worker project input chain')
} catch (error) {
  if (studio) { await capture('failure'); console.error(await studio.evaluate('document.body.innerText.slice(0,4000)')) }
  throw error
} finally {
  studio?.close(); desktop?.cdp.close(); await stop(desktop?.child)
  await rm(workspace, { recursive: true, force: true })
}
