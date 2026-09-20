import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { createServer } from 'node:http'

// Real Studio HTTP -> project batch -> child worker -> browser -> data/End.
export async function checkProjectRuntime(baseUrl, token, browserVersion) {
  const server = createServer((request, response) => {
    if (request.url === '/login') response.setHeader('Set-Cookie', 'pm9=logged-in; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax')
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
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
    const profile = await api('/api/v1/profiles', { name: 'PM9 真实浏览器', browserVersion, headless: true })
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
      node('write', 'project_data', { operation: 'createRecord', variableName: 'saved', tableGrant: grant(target, 'createRecord'), arguments: { tableId: target.table.tableId, datasetGeneration: target.table.datasetGeneration, values: { [target.fieldId]: `{account}-{${parameter}}` } } }),
      node('manual', 'project_manual', { reason: '核验登录后继续', timeoutSeconds: 30 }),
      node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: "{saved['ref']['recordKey']['value']}", recordTargets: [{ recordRef: "{saved['ref']}", expectedLinkRevision: "{saved['linkRevision']}", replaceAllowed: false }] } }),
    ], edges: [edge('query', 'condition'), edge('condition', 'login', 'true'), edge('login', 'read'), edge('read', 'write'), edge('write', 'manual'), edge('manual', 'end')] })
    const runPolicy = { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 180, manualDeadlineSeconds: 30 }
    async function run(workflowId, environmentPolicy, parameterSchema = [], parameters = {}, expectedStatus = 'succeeded') {
      const automation = await api(prefix + '/automations', { name: randomUUID(), description: '', workflowId, inputPlan: { inputs: [] }, parameterSchema, environmentPolicy, runPolicy })
      const validation = await api(`${prefix}/automations/${automation.automationId}/validation`)
      assert.equal(validation.runnable, true, JSON.stringify(validation))
      const started = await api(`${prefix}/automations/${automation.automationId}/batches`, { expectedAutomationRevision: automation.managementRevision, parameters, maxTasks: 1, concurrency: 1 })
      const batchId = started.operation.result.batch.batchId
      const handled = new Set()
      for (let attempt = 0; attempt < 1800; attempt++) {
        const manual = await api(prefix + '/manual-items')
        for (const item of manual.items.filter(item => item.status === 'waiting' && !handled.has(item.manualItemId))) {
          await api(`${prefix}/manual-items/${item.manualItemId}/resume`, { checkpointRevision: item.checkpointRevision, expectedStatusRevision: item.statusRevision })
          handled.add(item.manualItemId)
        }
        const state = await api(`${prefix}/batches/${batchId}`)
        if (['completed', 'failed', 'interrupted', 'stopped'].includes(state.batch.status)) {
          const tasks = await api(`${prefix}/tasks?batchId=${batchId}`)
          const task = tasks.items[0]
          const attempts = await api(`${prefix}/tasks/${task.taskId}/node-attempts`)
          if (state.statusCounts[expectedStatus] !== 1) {
            const events = await api(`${prefix}/tasks/${task.taskId}/events?afterSequence=0&pageSize=200`)
            throw new Error(JSON.stringify({ state, task, attempts, events }))
          }
          if (handled.size) assert.equal(new Set(attempts.items.map(item => item.nodeId)).size, attempts.total, 'completed nodes must not replay across manual continuation')
          return { task, resumedManualItems: handled.size, outputs: (await api(`${prefix}/tasks/${task.taskId}/outputs`)).items }
        }
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      throw new Error('project runtime did not finish within 180 seconds')
    }
    const first = await run(workflow.id, { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }, [{ parameterId: parameter, name: '后缀', type: 'string', required: true }], { [parameter]: '中文' })
    assert.equal(first.resumedManualItems, 1)
    const records = await api(`${prefix}/tables/${target.table.tableId}/records?datasetGeneration=${target.table.datasetGeneration}`)
    assert.equal(records.total, 1)
    assert.equal(records.items[0].values[0].value, '001-中文')
    const environmentId = records.items[0].currentEnvironmentId
    assert.ok(environmentId)
    const readLogin = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 登录复用', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#auth', attribute: 'text', variableName: 'login' }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'read'), edge('read', 'end')] })
    const second = await run(readLogin.id, { source: 'fixedEnvironment', environmentId, proxyOverride: { mode: 'none' }, modelProviderId: null })
    assert.equal(second.outputs.find(output => output.name === 'login')?.value, 'signed-in')
    const loadWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 日志负载', variables: [], nodes: [node('loop', 'loop', { count: 500 }), node('tick', 'set_variable', { variableName: 'tick', variableValue: 'bounded' }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('loop', 'tick', 'loop'), edge('loop', 'end', 'done')] })
    const startedAt = performance.now()
    const loaded = await run(loadWorkflow.id, { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null })
    const elapsedMs = performance.now() - startedAt
    let logCount = 0, logPages = 0
    for (let cursor = 0; ;) {
      const logs = await api(`${prefix}/tasks/${loaded.task.taskId}/logs?afterSequence=${cursor}&pageSize=200`)
      logCount += logs.items.length; logPages++
      assert.ok(logs.items.every(item => item.sequence > cursor), 'log pages must not repeat')
      if (!logs.hasMore) break
      assert.ok(logs.afterSequence > cursor, 'log pagination must advance')
      cursor = logs.afterSequence
    }
    assert.ok(logCount >= 1000, `expected at least 1000 real worker log events, got ${logCount}`)
    const statistics = await api(prefix + '/statistics')
    const drilldown = await api(`${prefix}/statistics/${statistics.resultSetId}/tasks?result=succeeded`)
    assert.ok(drilldown.items.some(item => item.taskId === loaded.task.taskId), 'statistics must link to real terminal tasks')
    const impact = await api(prefix + '/lifecycle-impact?action=archive')
    const archived = await api(prefix + '/archive', { impactRevision: impact.impactRevision, expectedManagementRevision: (await api(prefix)).managementRevision })
    for (let attempt = 0; attempt < 100; attempt++) {
      const operation = await api(`${prefix}/operations/${archived.operation.operationId}`)
      if (operation.status === 'succeeded') break
      assert.notEqual(operation.status, 'failed', JSON.stringify(operation))
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    assert.equal((await api(prefix)).lifecycleState, 'archived')
    const restored = await api(prefix + '/restore', { expectedManagementRevision: (await api(prefix)).managementRevision })
    for (let attempt = 0; attempt < 100; attempt++) {
      const operation = await api(`${prefix}/operations/${restored.operation.operationId}`)
      if (operation.status === 'succeeded') break
      assert.notEqual(operation.status, 'failed', JSON.stringify(operation))
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    assert.equal((await api(prefix)).lifecycleState, 'active')
    return { projectId: project.projectId, environmentId, logLoad: { logCount, logPages, elapsedMs: Math.round(elapsedMs), logsPerMinute: Math.round(logCount * 60_000 / elapsedMs), scope: 'real worker throughput and server pagination; no renderer memory claim' }, taskIds: [first.task.taskId, second.task.taskId, loaded.task.taskId], checks: ['Studio HTTP saved graph', 'real browser and UUID parameters', 'cross-table query/condition/create', 'manual checkpoint continues without replay', 'End closes, saves and links', 'second automation restores login', '1000 worker logs and paginated retrieval', 'statistics drilldown reaches real task', 'archive and restore preserve executed project'] }
  } finally {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  }
}
