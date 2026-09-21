import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { createServer } from 'node:http'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { installRuntimeKernel, projectSmokeOptions } from './smoke-project-management.mjs'
import { assertOutsideHistory } from './project-smoke-output.mjs'
import { stop, waitForReady } from './smoke-sidecar.mjs'

// Packaged business combinations using production HTTP and real workers.
// Passed assertions do not imply concurrent Task, Sheets or native UI acceptance.
export async function checkBusinessCombinations(baseUrl, token, browserVersion) {
  async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
    const response = await fetch(baseUrl + path, { method, headers: { 'x-autoflow-token': token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(60_000) })
    const value = await response.json()
    assert.ok(response.ok, `${method} ${path}: ${response.status} ${JSON.stringify(value)}`)
    return value
  }
  const node = (id, moduleType, config) => ({ id, type: moduleType, position: { x: 100, y: 100 }, data: { moduleType, ...config } })
  const project = await api('/api/v1/projects', { name: 'PM9 业务组合补证' })
  const prefix = `/api/v1/projects/${project.projectId}`
  const profile = await api('/api/v1/profiles', { name: 'PM9 业务组合浏览器', browserVersion, headless: true })
  const environment = { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }
  const runPolicy = { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 120, manualDeadlineSeconds: 120 }
  const end = () => node('end', 'project_end', { retainEnvironment: { enabled: false } })
  async function table(name, key = 'code') {
    const table = await api(`${prefix}/tables`, { name, sourceKind: 'local' })
    const field = (await api(`${prefix}/tables/${table.tableId}/fields`, { definition: { key, name: '编号', type: 'string', required: false, validation: {} }, sourceColumnPolicy: 'localOnly', expectedTableRevision: 1 })).field
    return { ...table, fieldId: field.ref.fieldId }
  }
  const grant = (table, operation) => ({ tableId: table.tableId, datasetGeneration: table.datasetGeneration, operations: [operation], fieldIds: [table.fieldId], readPurposes: ['condition', 'derivedWrite'] })
  const data = (id, table, operation, args) => node(id, 'project_data', { operation, variableName: id, tableGrant: grant(table, operation), arguments: args })
  const records = table => api(`${prefix}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)
  const create = (table, value) => api(`${prefix}/tables/${table.tableId}/records`, { datasetGeneration: table.datasetGeneration, values: [{ fieldId: table.fieldId, value }] })
  async function workflow(name, nodes) {
    return api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name, variables: [], nodes, edges: nodes.slice(1).map((n, i) => ({ id: randomUUID(), source: nodes[i].id, target: n.id })) })
  }
  const automations = new Map()
  async function start(flow, inputPlan = { inputs: [] }, environmentPolicy = environment) {
    const automation = automations.get(flow.id) ?? await api(prefix + '/automations', { name: randomUUID(), description: '', workflowId: flow.id, inputPlan, parameterSchema: [], environmentPolicy, runPolicy })
    automations.set(flow.id, automation)
    const validation = await api(`${prefix}/automations/${automation.automationId}/validation`)
    assert.equal(validation.runnable, true, JSON.stringify(validation))
    const accepted = await api(`${prefix}/automations/${automation.automationId}/batches`, { expectedAutomationRevision: automation.managementRevision, parameters: {}, maxTasks: 1, concurrency: 1 })
    return accepted.operation.result.batch.batchId
  }
  async function wait(check, label) {
    for (let i = 0; i < 480; i++) {
      const result = await check()
      if (result) return result
      await new Promise(resolveWait => setTimeout(resolveWait, 250))
    }
    throw new Error(`Timeout: ${label}`)
  }
  async function completed(batchId) {
    const state = await wait(async () => {
      const value = await api(`${prefix}/batches/${batchId}`)
      return ['completed', 'failed', 'interrupted', 'stopped'].includes(value.batch.status) && value
    }, 'terminal batch')
    const task = (await api(`${prefix}/tasks?batchId=${batchId}`)).items[0]
    const attempts = await api(`${prefix}/tasks/${task.taskId}/node-attempts`)
    assert.equal(state.statusCounts.succeeded, 1, JSON.stringify({ state, attempts }))
    return { task, attempts: attempts.items }
  }
  async function sharedPersonChain() {
    const server = createServer((request, response) => {
      if (request.url === '/login') response.setHeader('Set-Cookie', 'pm9=registered; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax')
      response.setHeader('Content-Type', 'text/html; charset=utf-8')
      response.end(`<output id="auth">${request.headers.cookie?.includes('pm9=registered') ? 'signed-in' : 'signed-out'}</output>`)
    })
    await new Promise(resolveListen => server.listen(0, '127.0.0.1', resolveListen))
    const site = `http://127.0.0.1:${server.address().port}`
    try {
      const person = await table('共享人员', 'personNo'), email = await table('消耗邮箱'), account = await table('新建账号', 'personNo')
      const p1 = await create(person, 'P001'), e1 = await create(email, 'e1@example.invalid')
      const makeStatus = (table, name, revision) => api(`${prefix}/tables/${table.tableId}/statuses`, { name, color: '#123456', order: revision, expectedTableRevision: revision })
      const verified = await makeStatus(person, '已核验', 2), pending = await makeStatus(email, '待使用', 2), registered = await makeStatus(email, '已注册', 3)
      const setInitial = (table, row, statusId) => api(`${prefix}/tables/${table.tableId}/records/${Buffer.from(row.ref.recordKey.value).toString('base64url')}/status`, { datasetGeneration: table.datasetGeneration, recordKeyType: row.ref.recordKey.type, statusId, expectedStatusRevision: row.statusRevision }, 'PUT')
      await setInitial(person, p1, verified.statusId)
      await setInitial(email, e1, pending.statusId)
      const fieldRef = table => ({ projectId: project.projectId, tableId: table.tableId, datasetGeneration: table.datasetGeneration, fieldId: table.fieldId })
      const input = (table, alias, statusId) => ({ inputId: randomUUID(), alias, tableId: table.tableId, datasetGeneration: table.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: alias, fieldRef: fieldRef(table) }], filter: statusId ? { type: 'status', operator: 'eq', statusId } : { type: 'all', items: [] }, orderBy: [{ systemField: 'recordKey', direction: 'asc' }] })
      const readInputs = () => node('inputs', 'project_data', { operation: 'inputs', variableName: 'frozen', arguments: {} })
      const personSetup = await workflow('人员已有独立环境', [readInputs(), node('open', 'open_page', { url: site + '/login' }), node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: '人员原环境', recordTargets: [{ recordRef: "{frozen[0]['recordRef']}", expectedLinkRevision: "{frozen[0]['linkRevision']}", replaceAllowed: false }] } })])
      await completed(await start(personSetup, { inputs: [input(person, '人员', verified.statusId)] }))
      const beforePerson = (await records(person)).items[0]
      assert.ok(beforePerson.currentEnvironmentId, 'person must begin with an existing environment association')
      const firstInputs = { inputs: [input(person, '人员', verified.statusId), input(email, '邮箱', pending.statusId)] }
      const registration = await workflow('共享人员注册新账号', [
        readInputs(), node('login', 'open_page', { url: site + '/login' }),
        data('register', email, 'setRecordStatus', { recordRef: "{frozen[1]['recordRef']}", statusId: registered.statusId, expectedStatusRevision: "{frozen[1]['statusRevision']}", expectedContentRevisionWhenDerived: "{frozen[1]['contentRevision']}" }),
        data('account', account, 'createRecord', { tableId: account.tableId, datasetGeneration: account.datasetGeneration, values: { [account.fieldId]: "{frozen[0]['values'][0]['value']}" } }),
        node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: '邮箱账号共享登录', recordTargets: [{ recordRef: "{frozen[1]['recordRef']}", expectedLinkRevision: "{frozen[1]['linkRevision']}", replaceAllowed: false }, { recordRef: "{account['ref']}", expectedLinkRevision: "{account['linkRevision']}", replaceAllowed: false }] } }),
      ])
      const registeredTask = await completed(await start(registration, firstInputs))
      const accounts = await records(account), emails = await records(email)
      assert.equal(accounts.total, 1)
      const a1 = accounts.items[0], savedEmail = emails.items[0]
      assert.equal(a1.values[0].value, 'P001')
      assert.equal(savedEmail.statusId, registered.statusId)
      assert.ok(a1.currentEnvironmentId)
      assert.equal(savedEmail.currentEnvironmentId, a1.currentEnvironmentId)
      assert.notEqual(a1.currentEnvironmentId, beforePerson.currentEnvironmentId)
      const exhaustedBatch = await start(registration, firstInputs)
      await wait(async () => (await api(`${prefix}/batches/${exhaustedBatch}`)).batch.status === 'completed', 'consumed email no longer matches original filter')
      assert.equal((await api(`${prefix}/tasks?batchId=${exhaustedBatch}`)).total, 0)
      assert.equal((await records(account)).total, 1, 'empty input selection must not create another account')
      const accountInput = input(account, '账号'), personInput = input(person, '关联人员', verified.statusId)
      personInput.mode = 'related'
      personInput.relation = { type: 'fieldEquals', sourceInputId: accountInput.inputId, sourceFieldRef: fieldRef(account), targetFieldRef: fieldRef(person) }
      const restore = await workflow('按账号环境和人员编号继续', [readInputs(), node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#auth', attribute: 'text', variableName: 'login' }), end()])
      const restoredTask = await completed(await start(restore, { inputs: [accountInput, personInput] }, { source: 'inputEnvironment', inputId: accountInput.inputId, proxyOverride: { mode: 'none' }, modelProviderId: null }))
      const detail = await api(`${prefix}/tasks/${restoredTask.task.taskId}`)
      assert.deepEqual(detail.inputSnapshot.inputs.map(item => item.recordRef), [a1.ref, p1.ref])
      assert.equal(detail.run.resourceRequest.profileId, profile.id, 'restore must freeze the selected environment profile')
      const outputs = await api(`${prefix}/tasks/${restoredTask.task.taskId}/outputs`)
      assert.equal(outputs.items.find(output => output.name === 'login')?.value, 'signed-in')
      const afterPerson = (await records(person)).items[0]
      for (const key of ['values', 'statusId', 'currentEnvironmentId', 'contentRevision', 'statusRevision', 'linkRevision']) assert.deepEqual(afterPerson[key], beforePerson[key], `shared person ${key} must remain unchanged`)
      return { status: 'passed', checks: ['P1 verified state/content/environment link and revisions unchanged across both Tasks', 'E1 explicitly registered and excluded from original pending selection; retry batch creates no Task/account', 'Exactly one new A1 and E1 link the same saved login environment', 'Next Task starts from A1 input environment, restores cookie, and selects P1 through personNo field equality'], taskIds: [registeredTask.task.taskId, restoredTask.task.taskId], environmentId: a1.currentEnvironmentId, scope: 'ARM packaged public HTTP and actual worker/browser; no full native UI flow or live Sheets claim' }
    } finally {
      await new Promise((resolveClose, reject) => server.close(error => error ? reject(error) : resolveClose()))
    }
  }
  const source = await table('旧契约数据'), target = await table('运行中新建记录')
  const first = await create(source, 'row-1'), second = await create(source, 'row-2')
  const status = await api(`${prefix}/tables/${source.tableId}/statuses`, { name: '已提交', color: '#123456', order: 0, expectedTableRevision: 2 })
  const query = (value) => data('query', source, 'queryRecords', { tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldIds: [source.fieldId], readPurpose: 'derivedWrite', filter: { type: 'compare', fieldId: source.fieldId, operator: 'eq', value }, orderBy: [], cursor: null, limit: 10 })
  const update = value => data('update', source, 'updateRecord', { recordRef: "{query['items'][0]['ref']}", changes: { [source.fieldId]: value }, expectedContentRevision: "{query['items'][0]['contentRevision']}" })
  const old = await start(await workflow('T2 先准备旧字段契约', [node('open', 'open_page', { url: 'about:blank' }), node('manual', 'project_manual', { reason: '等待另一个任务完成兼容加列', timeoutSeconds: 120 }), query('row-2'), update('old-contract-written'), end()]))
  const checkpoint = await wait(async () => {
    const tasks = (await api(`${prefix}/tasks?batchId=${old}`)).items
    const items = (await api(prefix + '/manual-items')).items
    return items.find(item => item.status === 'waiting' && tasks.some(task => task.taskId === item.taskId))
  }, 'old prepared task checkpoint')
  const addedFieldId = randomUUID()
  const newer = await start(await workflow('T1 运行中加列增行并写状态', [
    node('open', 'open_page', { url: 'about:blank' }),
    data('ensure', source, 'ensureField', { tableId: source.tableId, datasetGeneration: source.datasetGeneration, fieldId: addedFieldId, definition: { key: 'receipt', name: '回执', type: 'string', required: false, validation: {} }, hasDefault: false, default: null, expectedTableRevision: 3 }),
    data('create', target, 'createRecord', { tableId: target.tableId, datasetGeneration: target.datasetGeneration, values: { [target.fieldId]: 'created-by-T1' } }),
    query('row-1'), update('new-task-written'),
    data('status', source, 'setRecordStatus', { recordRef: "{query['items'][0]['ref']}", statusId: status.statusId, expectedStatusRevision: "{query['items'][0]['statusRevision']}", expectedContentRevisionWhenDerived: "{update['contentRevision']}" }), end(),
  ]))
  const blocked = await wait(async () => {
    const value = await api(`${prefix}/batches/${newer}`)
    return value.batch.status === 'blocked' && value
  }, 'single-capacity boundary')
  const queued = (await api(`${prefix}/tasks?batchId=${newer}`)).items
  assert.equal(queued.length, 1)
  assert.equal(queued[0].status, 'queued', 'second parameter Task must remain queued while the core slot is occupied')
  assert.equal((await api(`${prefix}/tasks/${checkpoint.taskId}`)).run.status, 'waiting_manual')
  await api(`${prefix}/manual-items/${checkpoint.manualItemId}/resume`, { checkpointRevision: checkpoint.checkpointRevision, expectedStatusRevision: checkpoint.statusRevision })
  const t2 = await completed(old)
  const t1 = await completed(newer)
  const fields = await api(`${prefix}/tables/${source.tableId}/fields`)
  assert.ok(fields.items.some(field => field.ref.fieldId === addedFieldId && field.key === 'receipt'))
  const created = await records(target)
  assert.equal(created.total, 1, 'createRecord must have exactly one effect')
  assert.equal(created.items[0].values[0].value, 'created-by-T1')
  const rows = (await records(source)).items
  const row = original => rows.find(item => item.ref.recordKey.value === original.ref.recordKey.value)
  assert.equal(row(first).values.find(value => value.fieldId === source.fieldId).value, 'new-task-written')
  assert.equal(row(first).statusId, status.statusId)
  assert.equal(row(second).values.find(value => value.fieldId === source.fieldId).value, 'old-contract-written')
  assert.equal(row(second).statusId, null)
  assert.equal(t2.attempts.filter(attempt => attempt.nodeId === 'manual').length, 1)
  return {
    projectId: project.projectId,
    sharedPersonChain: await sharedPersonChain(),
    checks: ['Second parameter batch remained blocked with its Task queued while first Task waited for manual input', 'After first Task resumed and finished, second Task ensured a persistent field, created exactly one second-table record, queried/updated content and explicitly set status', 'Both sequential Tasks completed; manual node executed once'],
    taskIds: [t1.task.taskId, t2.task.taskId],
    concurrency: { status: 'implementation_missing', observedBatchStatus: blocked.batch.status, observedTaskStatus: queued[0].status, reason: 'Production WorkflowRunDispatcher owns one worker and reports capacity=1. Manual waiting occupies that slot.', unsupportedScenario: 'Concurrent old-contract Task across schema extension is unsupported; this run asserts queuing and subsequent sequential completion only' },
    remaining: ['Concurrent old-contract Task across compatible schema extension is NOT verified', 'Sheets structure/value phases require authorized live resources', 'Excel source byte preservation belongs to separate native import/export evidence', 'Conflict and partial-success combinations remain separate evidence'],
  }
}

async function main() {
  const options = projectSmokeOptions(process.argv.slice(2))
  assert.ok(options.executable && options['runtime-kernel'] && options['output-dir'], 'requires --executable, --runtime-kernel and --output-dir')
  const root = resolve(import.meta.dirname, '..')
  await assertOutsideHistory(join(root, 'docs'), options['output-dir'])
  const executableSha256 = createHash('sha256').update(await readFile(options.executable)).digest('hex')
  const directory = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm9-business-')))
  const token = randomUUID()
  const report = { status: 'failed', platform: process.platform, arch: process.arch, packaged: true, startedAt: new Date().toISOString(), executableSha256 }
  let child, failure
  try {
    const version = await installRuntimeKernel(options['runtime-kernel'], directory)
    child = spawn(resolve(options.executable), ['--instance-id', randomUUID(), '--data-dir', directory, '--port', '0'], { cwd: root, env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token }, stdio: ['ignore', 'pipe', 'inherit'] })
    const ready = await waitForReady(child, 60_000)
    Object.assign(report, await checkBusinessCombinations(`http://127.0.0.1:${ready.port}`, token, version), { status: 'passed' })
  } catch (error) {
    report.error = String(error.stack ?? error)
    failure = error
  } finally {
    try {
      await stop(child)
      await rm(directory, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 })
      report.cleanup = 'passed'
    } catch (error) {
      report.cleanup = { status: 'failed', error: String(error.stack ?? error), retainedDirectory: directory }
      report.status = 'failed'
      failure ??= error
    }
    await mkdir(options['output-dir'], { recursive: true })
    await writeFile(join(options['output-dir'], 'business-combinations.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify(report, null, 2))
  }
  if (failure) throw failure
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main()
