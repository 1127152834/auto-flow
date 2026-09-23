// Diagnostic only: a successful probe is not successful identity preservation.
import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { createServer } from 'node:http'
import { observeInstanceSeed } from '../../../../../scripts/smoke-profile-test-browser.mjs'

// Real Studio HTTP -> project batch -> child worker -> browser -> data/End.
export async function probePersistentIdentity(baseUrl, token, browserVersion, hooks = {}) {
  const server = createServer((request, response) => {
    if (request.url === '/login') response.setHeader('Set-Cookie', 'pm9=logged-in; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax')
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    if (request.url === '/profile') {
      response.end(`<!doctype html><body><script>
        (async()=>{
          const canvas=document.createElement('canvas');canvas.width=320;canvas.height=80;
          const context=canvas.getContext('2d');context.fillStyle='#d7c8b6';context.fillRect(0,0,320,80);
          context.fillStyle='#3d3027';context.font='17px Arial';context.fillText('AutoFlow fingerprint 0123456789',8,32);
          context.beginPath();context.arc(260,42,23,0,Math.PI*2);context.stroke();
          const bytes=new TextEncoder().encode(canvas.toDataURL());
          const canvasHash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
          const output=document.createElement('output');output.id='profile-observation';
          output.textContent=JSON.stringify({userAgent:navigator.userAgent,language:navigator.language,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,canvasHash});document.body.append(output);
        })();
      </script></body>`)
      return
    }
    response.end(`<output id="account">001</output><output id="auth">${request.headers.cookie?.includes('pm9=logged-in') ? 'signed-in' : 'signed-out'}</output>`)
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const site = `http://127.0.0.1:${server.address().port}`
  async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
    const response = await fetch(baseUrl + path, { method, headers: { 'x-autoflow-token': token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(60_000) })
    const result = await response.json()
    assert.ok(response.ok, `${method} ${path}: ${response.status} ${JSON.stringify(result)}`)
    return result
  }
  const node = (id, moduleType, config) => ({ id, type: moduleType, position: { x: 100, y: 100 }, data: { moduleType, ...config } })
  const edge = (source, target, sourceHandle) => ({ id: randomUUID(), source, target, ...(sourceHandle ? { sourceHandle } : {}) })
  try {
    const project = await api('/api/v1/projects', { name: 'PM9 生产运行链' })
    const prefix = `/api/v1/projects/${project.projectId}`
    const profile = await api('/api/v1/profiles', { name: 'PM9 原身份', browserVersion, headless: true, userAgent: 'AutoFlow-PM9-saved-identity', locale: 'en-US', timezone: 'UTC' })
    async function table(name) {
      const table = await api(`${prefix}/tables`, { name, sourceKind: 'local' })
      const field = (await api(`${prefix}/tables/${table.tableId}/fields`, { definition: { key: 'code', name: '编号', type: 'string', required: false, validation: {} }, sourceColumnPolicy: 'localOnly', expectedTableRevision: table.tableRevision })).field
      return { table, fieldId: field.ref.fieldId }
    }
    const source = await table('来源'), target = await table('结果')
    await api(`${prefix}/tables/${source.table.tableId}/records`, { datasetGeneration: source.table.datasetGeneration, values: [{ fieldId: source.fieldId, value: '001' }] })
    const parameter = randomUUID()
    const grant = (binding, operation) => ({ tableId: binding.table.tableId, datasetGeneration: binding.table.datasetGeneration, operations: [operation], fieldIds: [binding.fieldId], readPurposes: ['condition', 'derivedWrite'] })
    const workflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 多表登录保存', variables: [], nodes: [
      node('query', 'project_data', { operation: 'queryRecords', variableName: 'rows', tableGrant: grant(source, 'queryRecords'), arguments: { tableId: source.table.tableId, datasetGeneration: source.table.datasetGeneration, fieldIds: [source.fieldId], readPurpose: 'condition', filter: null, orderBy: [], cursor: null, limit: 10 } }),
      node('condition', 'condition', { leftValue: "{rows['items'][0]['values'][0]['value']}", rightValue: '001' }),
      node('login', 'open_page', { url: site + '/login' }),
      node('read', 'get_element_info', { selector: '#account', attribute: 'text', variableName: 'account' }),
      node('identity-page', 'open_page', { url: site + '/profile' }), node('identity-read', 'get_element_info', { selector: '#profile-observation', attribute: 'text', variableName: 'identity' }),
      node('write', 'project_data', { operation: 'createRecord', variableName: 'saved', tableGrant: grant(target, 'createRecord'), arguments: { tableId: target.table.tableId, datasetGeneration: target.table.datasetGeneration, values: { [target.fieldId]: `{account}-{${parameter}}` } } }),
      node('manual', 'project_manual', { reason: '核验登录后继续', timeoutSeconds: 60, inputSchema: [{ name: 'confirmation', title: '确认码', type: 'string', required: true }], resumeTargets: [{ nodeId: 'accepted', title: '确认后保存', requiredVariables: ['confirmation'] }, { nodeId: 'alternate', title: '其他分支' }] }),
      node('accepted', 'set_variable', { variableName: 'humanConfirmation', variableValue: 'human-{confirmation}' }),
      node('alternate', 'set_variable', { variableName: 'unselected', variableValue: 'must-not-run' }),
      node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: "{saved['ref']['recordKey']['value']}", recordTargets: [{ recordRef: "{saved['ref']}", expectedLinkRevision: "{saved['linkRevision']}", replaceAllowed: false }] } }),
    ], edges: [edge('query', 'condition'), edge('condition', 'login', 'true'), edge('login', 'read'), edge('read', 'identity-page'), edge('identity-page', 'identity-read'), edge('identity-read', 'write'), edge('write', 'manual'), edge('manual', 'accepted'), edge('manual', 'alternate'), edge('accepted', 'end'), edge('alternate', 'end')] })
    const runPolicy = { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 600, manualDeadlineSeconds: 60 }
    async function run(workflowId, environmentPolicy, parameterSchema = [], parameters = {}, expectedStatus = 'succeeded', inputPlan = { inputs: [] }, followUp = null, options = {}) {
      const maxTasks = options.maxTasks ?? 1
      const automation = followUp ? null : options.automation ?? await api(prefix + '/automations', { name: randomUUID(), description: '', workflowId, inputPlan, parameterSchema, environmentPolicy, runPolicy: { ...runPolicy, maxTasks } })
      if (automation) {
        const validation = await api(`${prefix}/automations/${automation.automationId}/validation`)
        assert.equal(validation.runnable, true, JSON.stringify(validation))
      }
      const started = followUp ? await api(`${prefix}/tasks/${followUp.taskId}/follow-up-batches`, { mode: 'originalInputGroup', expectedTaskStatusRevision: followUp.statusRevision, parameterOverrides: parameters }) : await api(`${prefix}/automations/${automation.automationId}/batches`, { expectedAutomationRevision: automation.managementRevision, parameters, maxTasks, concurrency: 1 })
      const batchId = started.operation.result.batch.batchId
      const handled = new Set()
      let resumed = 0
      for (let attempt = 0; attempt < 1200; attempt++) {
        const manual = await api(prefix + '/manual-items')
        for (const item of manual.items.filter(item => item.status === 'waiting' && !handled.has(item.manualItemId))) {
          if (options.stopAtManual) {
            const batch = await api(`${prefix}/batches/${batchId}`)
            await api(`${prefix}/batches/${batchId}/stop`, { expectedStatusRevision: batch.batch.statusRevision, reason: '验证父批次停止撤销子流程后续写入' })
            handled.add(item.manualItemId)
            continue
          }
          await options.beforeResume?.(item)
          const body = { checkpointRevision: item.checkpointRevision, expectedStatusRevision: item.statusRevision, ...(item.inputSchema?.length ? { inputs: { confirmation: 'verified' }, targetNodeId: 'accepted' } : {}) }
          if (item.inputSchema?.length && hooks.resumeManual) await hooks.resumeManual(project.projectId, item, body)
          else await api(`${prefix}/manual-items/${item.manualItemId}/resume`, body)
          handled.add(item.manualItemId)
          resumed++
        }
        const state = await api(`${prefix}/batches/${batchId}`)
        if (['completed', 'failed', 'interrupted', 'stopped'].includes(state.batch.status)) {
          const tasks = await api(`${prefix}/tasks?batchId=${batchId}`)
          const task = tasks.items[0]
          const attempts = await api(`${prefix}/tasks/${task.taskId}/node-attempts`)
          if (state.statusCounts[expectedStatus] !== maxTasks) {
            const events = await api(`${prefix}/tasks/${task.taskId}/events?afterSequence=0&pageSize=200`).catch(error => ({ error: String(error) }))
            throw new Error(JSON.stringify({ batch: state.batch, counts: state.statusCounts, task, attempts: { total: attempts.total, latest: attempts.items.at(-1) }, events: events.error ? events : { lastSequence: events.lastSequence, statuses: events.items.filter(event => event.kind === 'runStatus') } }))
          }
          if (handled.size) {
            const counts = new Map()
            for (const item of attempts.items) counts.set(item.nodeId, (counts.get(item.nodeId) ?? 0) + 1)
            for (const [id, count] of Object.entries(options.expectedVisits ?? {})) assert.equal(counts.get(id), count, `missing declared visits: ${id}`)
            for (const [id, count] of counts) assert.equal(count, options.expectedVisits?.[id] ?? 1, `unexpected replay or missing subflow visit: ${id}`)
          }
          return { task, automation, tasks: tasks.items, attempts: attempts.items, resumedManualItems: resumed, outputs: (await api(`${prefix}/tasks/${task.taskId}/outputs`)).items }
        }
        await new Promise(resolve => setTimeout(resolve, 500))
      }
      throw new Error('project runtime did not finish within 600 seconds')
    }
    const seedObservations = []
    const observeSeed = async item => seedObservations.push(await observeInstanceSeed(item.instanceId))
    const first = await run(workflow.id, { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }, [{ parameterId: parameter, name: '后缀', type: 'string', required: true }], { [parameter]: '中文' }, 'succeeded', { inputs: [] }, null, { beforeResume: observeSeed })
    assert.equal(first.resumedManualItems, 1)
    assert.equal(first.outputs.find(output => output.name === 'humanConfirmation')?.value, 'human-verified')
    assert.equal(first.attempts.some(attempt => attempt.nodeId === 'alternate'), false)
    const records = await api(`${prefix}/tables/${target.table.tableId}/records?datasetGeneration=${target.table.datasetGeneration}`)
    assert.equal(records.total, 1)
    assert.equal(records.items[0].values[0].value, '001-中文')
    const environmentId = records.items[0].currentEnvironmentId
    assert.ok(environmentId)
    const originalIdentity = JSON.parse(first.outputs.find(output => output.name === 'identity').value)
    assert.equal(originalIdentity.userAgent, 'AutoFlow-PM9-saved-identity')
    assert.equal(originalIdentity.language, 'en-US')
    assert.equal(originalIdentity.timezone, 'UTC')
    await api(`/api/v1/profiles/${profile.id}`, { name: 'PM9 修改后的Profile', browserVersion, headless: true, userAgent: 'AutoFlow-PM9-current-profile', locale: 'fr-FR', timezone: 'Europe/Paris' }, 'PUT')
    const newSeed = (await api(`/api/v1/profiles/${profile.id}/regenerate-fingerprint`, {})).fingerprintSeed
    assert.notEqual(newSeed, profile.fingerprintSeed)
    const readLogin = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 登录复用', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#auth', attribute: 'text', variableName: 'login' }), node('identity-page', 'open_page', { url: site + '/profile' }), node('identity-read', 'get_element_info', { selector: '#profile-observation', attribute: 'text', variableName: 'identity' }), node('identity-pause', 'project_manual', { reason: '观察实际身份', timeoutSeconds: 60 }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'read'), edge('read', 'identity-page'), edge('identity-page', 'identity-read'), edge('identity-read', 'identity-pause'), edge('identity-pause', 'end')] })
    const second = await run(readLogin.id, { source: 'fixedEnvironment', environmentId, proxyOverride: { mode: 'none' }, modelProviderId: null }, [], {}, 'succeeded', { inputs: [] }, null, { beforeResume: observeSeed })
    assert.equal(second.outputs.find(output => output.name === 'login')?.value, 'signed-in')
    const inputId = randomUUID()
    const inputPlan = { inputs: [{ inputId, alias: '已关联记录', tableId: target.table.tableId, datasetGeneration: target.table.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: '编号', fieldRef: { projectId: project.projectId, tableId: target.table.tableId, datasetGeneration: target.table.datasetGeneration, fieldId: target.fieldId } }], filter: { type: 'all', items: [] }, orderBy: [{ systemField: 'recordKey', direction: 'asc' }] }] }
    const inputWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 输入身份恢复', variables: readLogin.variables, nodes: readLogin.nodes, edges: readLogin.edges })
    const third = await run(inputWorkflow.id, { source: 'inputEnvironment', inputId, proxyOverride: { mode: 'none' }, modelProviderId: null }, [], {}, 'succeeded', inputPlan, null, { beforeResume: observeSeed })
    assert.equal(third.outputs.find(output => output.name === 'login')?.value, 'signed-in')
    const restored = [second, third].map(result => ({ taskId: result.task.taskId, identity: JSON.parse(result.outputs.find(output => output.name === 'identity').value), login: result.outputs.find(output => output.name === 'login').value }))
    return { status: 'observed_not_acceptance', projectId: project.projectId, environmentId, profileId: profile.id, originalSeed: profile.fingerprintSeed, newSeed, originalIdentity, seedObservations, fixedEnvironment: restored[0], inputEnvironment: restored[1], identityPreserved: restored.every(result => JSON.stringify(result.identity) === JSON.stringify(originalIdentity)), seedPreserved: seedObservations.every(item => item && item.seed === profile.fingerprintSeed), boundary: 'Actual packaged HTTP/SQLite/browser/worker, public Profile edit/reset, own local fixture site; no current Google or cross-platform claim.' }
  } finally { await new Promise(resolve => server.close(resolve)) }
}

// Run only against a disposable workspace and an explicitly supplied production binary.
import { spawn } from 'node:child_process'
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { installRuntimeKernel, projectSmokeOptions } from '../../../../../scripts/smoke-project-management.mjs'
import { waitForReady, stop } from '../../../../../scripts/smoke-sidecar.mjs'
const options = projectSmokeOptions(process.argv.slice(2))
assert.ok(options.executable && options['runtime-kernel'], 'Supply packaged --executable and --runtime-kernel')
const workspace = await mkdtemp(join(tmpdir(), 'autoflow-identity-probe-'))
const token = randomUUID()
let child
try {
  const browserVersion = await installRuntimeKernel(options['runtime-kernel'], workspace)
  child = spawn(resolve(options.executable), ['--instance-id', randomUUID(), '--data-dir', workspace, '--port', '0'], { env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token }, stdio: ['ignore', 'pipe', 'inherit'] })
  const ready = await waitForReady(child, 60000)
  const report = await probePersistentIdentity(`http://127.0.0.1:${ready.port}`, token, browserVersion)
  if (options['output-dir']) {
    await mkdir(options['output-dir'], { recursive: true })
    await writeFile(join(options['output-dir'], 'observations.json'), JSON.stringify(report, null, 2) + '\n')
  }
  console.log(JSON.stringify(report, null, 2))
} finally {
  await stop(child)
  await rm(workspace, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 })
}
