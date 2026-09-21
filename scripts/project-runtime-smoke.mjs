import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { createServer } from 'node:http'

// Real Studio HTTP -> project batch -> child worker -> browser -> data/End.
export async function checkProjectRuntime(baseUrl, token, browserVersion, hooks = {}) {
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
      node('manual', 'project_manual', { reason: '核验登录后继续', timeoutSeconds: 60, inputSchema: [{ name: 'confirmation', title: '确认码', type: 'string', required: true }], resumeTargets: [{ nodeId: 'accepted', title: '确认后保存', requiredVariables: ['confirmation'] }, { nodeId: 'alternate', title: '其他分支' }] }),
      node('accepted', 'set_variable', { variableName: 'humanConfirmation', variableValue: 'human-{confirmation}' }),
      node('alternate', 'set_variable', { variableName: 'unselected', variableValue: 'must-not-run' }),
      node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: "{saved['ref']['recordKey']['value']}", recordTargets: [{ recordRef: "{saved['ref']}", expectedLinkRevision: "{saved['linkRevision']}", replaceAllowed: false }] } }),
    ], edges: [edge('query', 'condition'), edge('condition', 'login', 'true'), edge('login', 'read'), edge('read', 'write'), edge('write', 'manual'), edge('manual', 'accepted'), edge('manual', 'alternate'), edge('accepted', 'end'), edge('alternate', 'end')] })
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
      for (let attempt = 0; attempt < 1200; attempt++) {
        const manual = await api(prefix + '/manual-items')
        for (const item of manual.items.filter(item => item.status === 'waiting' && !handled.has(item.manualItemId))) {
          await options.beforeResume?.(item)
          const body = { checkpointRevision: item.checkpointRevision, expectedStatusRevision: item.statusRevision, ...(item.inputSchema?.length ? { inputs: { confirmation: 'verified' }, targetNodeId: 'accepted' } : {}) }
          if (item.inputSchema?.length && hooks.resumeManual) await hooks.resumeManual(project.projectId, item, body)
          else await api(`${prefix}/manual-items/${item.manualItemId}/resume`, body)
          handled.add(item.manualItemId)
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
          if (handled.size) assert.equal(new Set(attempts.items.map(item => item.nodeId)).size, attempts.total, 'completed nodes must not replay across manual continuation')
          return { task, automation, tasks: tasks.items, attempts: attempts.items, resumedManualItems: handled.size, outputs: (await api(`${prefix}/tasks/${task.taskId}/outputs`)).items }
        }
        await new Promise(resolve => setTimeout(resolve, 500))
      }
      throw new Error('project runtime did not finish within 600 seconds')
    }
    const first = await run(workflow.id, { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }, [{ parameterId: parameter, name: '后缀', type: 'string', required: true }], { [parameter]: '中文' })
    assert.equal(first.resumedManualItems, 1)
    assert.equal(first.outputs.find(output => output.name === 'humanConfirmation')?.value, 'human-verified')
    assert.equal(first.attempts.some(attempt => attempt.nodeId === 'alternate'), false)
    const records = await api(`${prefix}/tables/${target.table.tableId}/records?datasetGeneration=${target.table.datasetGeneration}`)
    assert.equal(records.total, 1)
    assert.equal(records.items[0].values[0].value, '001-中文')
    const environmentId = records.items[0].currentEnvironmentId
    assert.ok(environmentId)
    const readLogin = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 登录复用', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#auth', attribute: 'text', variableName: 'login' }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'read'), edge('read', 'end')] })
    const second = await run(readLogin.id, { source: 'fixedEnvironment', environmentId, proxyOverride: { mode: 'none' }, modelProviderId: null })
    assert.equal(second.outputs.find(output => output.name === 'login')?.value, 'signed-in')
    const selectorParameter = randomUUID()
    const failureWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 失败后续', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: `{${selectorParameter}}`, attribute: 'text', variableName: 'account', timeout: .3 }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'read'), edge('read', 'end')] })
    const inputPlan = { inputs: [{ inputId: randomUUID(), alias: '来源', tableId: source.table.tableId, datasetGeneration: source.table.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: '编号', fieldRef: { projectId: project.projectId, tableId: source.table.tableId, datasetGeneration: source.table.datasetGeneration, fieldId: source.fieldId } }], filter: { type: 'all', items: [] }, orderBy: [{ systemField: 'recordKey', direction: 'asc' }] }] }
    const environment = { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }
    const failed = await run(failureWorkflow.id, environment, [{ parameterId: selectorParameter, name: '定位', type: 'string', required: true }], { [selectorParameter]: '#missing' }, 'failed', inputPlan)
    const failedDetail = await api(`${prefix}/tasks/${failed.task.taskId}`)
    const followed = await run(null, null, [], { [selectorParameter]: '#account' }, 'succeeded', inputPlan, { taskId: failed.task.taskId, statusRevision: failedDetail.run.statusRevision })
    const followedDetail = await api(`${prefix}/tasks/${followed.task.taskId}`)
    assert.deepEqual(followedDetail.inputSnapshot.inputs.map(input => input.recordRef), failedDetail.inputSnapshot.inputs.map(input => input.recordRef), 'follow-up must reuse the original input group')
    assert.equal(followed.outputs.find(output => output.name === 'account')?.value, '001')
    // Each task receives two frozen inputs; releasing a lease permits the next
    // task to claim the same business record, including after an explicit status write.
    const companion = await table('可重复人员')
    await api(`${prefix}/tables/${companion.table.tableId}/records`, { datasetGeneration: companion.table.datasetGeneration, values: [{ fieldId: companion.fieldId, value: 'person' }] })
    const status = (await api(`${prefix}/tables/${source.table.tableId}/statuses`, { name: '已处理', color: '#123456', order: 0, expectedTableRevision: 2 }))
    const twoInputs = { inputs: [inputPlan.inputs[0], { ...inputPlan.inputs[0], inputId: randomUUID(), alias: '人员', tableId: companion.table.tableId, datasetGeneration: companion.table.datasetGeneration, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: '姓名', fieldRef: { projectId: project.projectId, tableId: companion.table.tableId, datasetGeneration: companion.table.datasetGeneration, fieldId: companion.fieldId } }] }] }
    const readInputs = () => node('inputs', 'project_data', { operation: 'inputs', variableName: 'frozen', arguments: {} })
    const change = (id, previous, value) => node(id, 'project_data', { operation: 'updateRecord', variableName: id, arguments: { recordRef: "{frozen[0]['recordRef']}", changes: { [source.fieldId]: value }, expectedContentRevision: previous }, tableGrant: grant(source, 'updateRecord') })
    const setStatus = node('status', 'project_data', { operation: 'setRecordStatus', variableName: 'statusWrite', arguments: { recordRef: "{frozen[0]['recordRef']}", statusId: status.statusId, expectedStatusRevision: "{frozen[0]['statusRevision']}", expectedContentRevisionWhenDerived: "{secondWrite['contentRevision']}" }, tableGrant: grant(source, 'setRecordStatus') })
    const mutationNodes = [readInputs(), change('firstWrite', "{frozen[0]['contentRevision']}", 'task-first'), change('secondWrite', "{firstWrite['contentRevision']}", 'task-second'), setStatus]
    const mutationEdges = [edge('inputs', 'firstWrite'), edge('firstWrite', 'secondWrite'), edge('secondWrite', 'status')]
    const repeatWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 多输入重复领取', variables: [], nodes: [...mutationNodes, node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [...mutationEdges, edge('status', 'end')] })
    const repeated = await run(repeatWorkflow.id, environment, [], {}, 'succeeded', twoInputs, null, { maxTasks: 2 })
    const repeatDetails = await Promise.all(repeated.tasks.map(task => api(`${prefix}/tasks/${task.taskId}`)))
    repeatDetails.sort((a, b) => a.inputSnapshot.inputs[0].contentRevision - b.inputSnapshot.inputs[0].contentRevision)
    assert.equal(repeatDetails.length, 2)
    assert.equal(new Set(repeated.tasks.map(task => task.taskId)).size, 2)
    assert.deepEqual(repeatDetails[0].inputSnapshot.inputs.map(input => input.recordRef), repeatDetails[1].inputSnapshot.inputs.map(input => input.recordRef))
    assert.equal(repeatDetails[0].inputSnapshot.inputs.length, 2)
    assert.equal(repeatDetails[1].inputSnapshot.inputs[0].contentRevision, repeatDetails[0].inputSnapshot.inputs[0].contentRevision + 2)
    assert.equal(repeatDetails[1].inputSnapshot.inputs[0].statusRevision, repeatDetails[0].inputSnapshot.inputs[0].statusRevision + 1)
    const sourceRecord = async () => (await api(`${prefix}/tables/${source.table.tableId}/records?datasetGeneration=${source.table.datasetGeneration}`)).items[0]
    assert.equal((await sourceRecord()).statusId, status.statusId)

    // Pause the actual worker after a successful write. A human edit must win
    // over the worker's stale second write; its original input remains frozen.
    let humanRevision
    const conflictWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 人工新值保护', variables: [], nodes: [readInputs(), change('firstWrite', "{frozen[0]['contentRevision']}", 'before-human'), node('manual', 'project_manual', { reason: '制造人工版本竞争', timeoutSeconds: 30 }), change('secondWrite', "{firstWrite['contentRevision']}", 'must-not-win'), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('inputs', 'firstWrite'), edge('firstWrite', 'manual'), edge('manual', 'secondWrite'), edge('secondWrite', 'end')] })
    const conflicted = await run(conflictWorkflow.id, environment, [], {}, 'failed', twoInputs, null, { beforeResume: async () => {
      const row = await sourceRecord()
      assert.equal(row.values.find(value => value.fieldId === source.fieldId).value, 'before-human')
      const changed = await api(`${prefix}/tables/${source.table.tableId}/records/${Buffer.from(row.ref.recordKey.value).toString('base64url')}`, { datasetGeneration: source.table.datasetGeneration, recordKeyType: row.ref.recordKey.type, expectedContentRevision: row.contentRevision, values: [{ fieldId: source.fieldId, value: 'human-new' }] }, 'PATCH')
      humanRevision = changed.contentRevision
    } })
    assert.equal((await sourceRecord()).values.find(value => value.fieldId === source.fieldId).value, 'human-new')
    assert.equal((await sourceRecord()).contentRevision, humanRevision)
    assert.equal(conflicted.attempts.find(attempt => attempt.nodeId === 'secondWrite').error.code, 'REVISION_CONFLICT')
    const conflictDetail = await api(`${prefix}/tasks/${conflicted.task.taskId}`)
    assert.equal(conflictDetail.inputSnapshot.inputs[0].contentRevision, humanRevision - 2)
    assert.equal(conflictDetail.inputSnapshot.inputs[0].values.find(value => value.fieldId === source.fieldId).value, 'task-second')

    // A later browser failure does not roll back either preceding data write.
    const submitted = await api(`${prefix}/tables/${source.table.tableId}/statuses`, { name: '已提交', color: '#234567', order: 1, expectedTableRevision: 3 })
    const partialNodes = [...mutationNodes.slice(0, -1), { ...setStatus, data: { ...setStatus.data, arguments: { ...setStatus.data.arguments, statusId: submitted.statusId } } }]
    const partialWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 保留前写效果', variables: [], nodes: [...partialNodes, node('open', 'open_page', { url: site }), node('missing', 'click_element', { selector: '#never-present', timeout: .3 }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [...mutationEdges, edge('status', 'open'), edge('open', 'missing'), edge('missing', 'end')] })
    const statusRevisionBeforeFailure = (await sourceRecord()).statusRevision
    const partial = await run(partialWorkflow.id, environment, [], {}, 'failed', twoInputs)
    const kept = await sourceRecord()
    assert.equal(kept.values.find(value => value.fieldId === source.fieldId).value, 'task-second')
    assert.equal(kept.contentRevision, humanRevision + 2)
    assert.equal(kept.statusId, submitted.statusId)
    assert.equal(kept.statusRevision, statusRevisionBeforeFailure + 1)
    assert.equal(partial.attempts.find(attempt => attempt.nodeId === 'status').status, 'succeeded')
    assert.equal(partial.attempts.find(attempt => attempt.nodeId === 'missing').status, 'failed')
    const mixedWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 初始与新建混合关联', variables: [], nodes: [readInputs(), node('login', 'open_page', { url: site + '/login' }), node('create', 'project_data', { operation: 'createRecord', variableName: 'created', tableGrant: grant(target, 'createRecord'), arguments: { tableId: target.table.tableId, datasetGeneration: target.table.datasetGeneration, values: { [target.fieldId]: 'mixed-link' } } }), node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: "{created['ref']['recordKey']['value']}", recordTargets: [{ recordRef: "{frozen[0]['recordRef']}", expectedLinkRevision: "{frozen[0]['linkRevision']}", replaceAllowed: false }, { recordRef: "{created['ref']}", expectedLinkRevision: "{created['linkRevision']}", replaceAllowed: false }] } })], edges: [edge('inputs', 'login'), edge('login', 'create'), edge('create', 'end')] })
    const mixed = await run(mixedWorkflow.id, environment, [], {}, 'succeeded', twoInputs)
    const linkedSource = await sourceRecord()
    const mixedRows = (await api(`${prefix}/tables/${target.table.tableId}/records?datasetGeneration=${target.table.datasetGeneration}`)).items
    assert.equal(mixedRows.find(row => row.values[0].value === 'mixed-link').currentEnvironmentId, linkedSource.currentEnvironmentId)
    assert.ok(linkedSource.currentEnvironmentId)
    const beforeEnvironments = (await api(prefix + '/environments')).total
    const unlinked = await run(mixedWorkflow.id, environment, [], {}, 'failed', twoInputs, null, { automation: mixed.automation })
    assert.equal(unlinked.attempts.find(attempt => attempt.nodeId === 'end')?.status, 'failed', JSON.stringify(unlinked.attempts))
    assert.equal((await sourceRecord()).currentEnvironmentId, linkedSource.currentEnvironmentId, 'an End cannot replace another environment without explicit authorization')
    assert.equal((await api(prefix + '/environments')).total, beforeEnvironments + 1, 'the saved environment must survive failed association')
    const afterUnlinked = (await api(`${prefix}/tables/${target.table.tableId}/records?datasetGeneration=${target.table.datasetGeneration}`)).items.filter(row => row.values[0].value === 'mixed-link')
    assert.equal(afterUnlinked.length, 2)
    assert.equal(afterUnlinked.filter(row => row.currentEnvironmentId === null).length, 1, 'failed association must not partially link the newly created target')
    const operations = (await api(prefix + '/operations?pageSize=200')).items
    const save = operations.find(operation => operation.idempotencyKey?.startsWith('end-save:') && operation.result?.phase === 'saved_unlinked')
    assert.ok(save, 'the original save result must be queryable')
    const savedId = save.result.saved.environmentId
    assert.notEqual(savedId, linkedSource.currentEnvironmentId)
    const beforeRepair = await api(`${prefix}/tasks/${unlinked.task.taskId}/node-attempts`)
    const environmentBeforeRepair = await api(`${prefix}/environments/${savedId}`)
    const repaired = await api(`${prefix}/environment-operations/${save.operationId}/repair`, { recordTargets: [{ recordRef: linkedSource.ref, expectedLinkRevision: linkedSource.linkRevision, replaceAllowed: true }] })
    assert.equal(repaired.outcome.phase, 'completed')
    assert.equal((await sourceRecord()).currentEnvironmentId, savedId)
    assert.equal((await api(prefix + '/environments')).total, beforeEnvironments + 1)
    assert.deepEqual((await api(`${prefix}/environments/${savedId}`)).environment, environmentBeforeRepair.environment, 'repair must not publish another environment generation')
    assert.deepEqual(await api(`${prefix}/tasks/${unlinked.task.taskId}/node-attempts`), beforeRepair, 'repair must not execute nodes again')
    assert.equal((await api(`${prefix}/tasks/${unlinked.task.taskId}`)).run.status, 'failed', 'repair cannot rewrite the historical Run outcome')

    const updateWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 旧候选发布保护', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'update', expectedContentGeneration: 1 } })], edges: [edge('open', 'end')] })
    const fixed = { source: 'fixedEnvironment', environmentId: savedId, proxyOverride: { mode: 'none' }, modelProviderId: null }
    const updated = await run(updateWorkflow.id, fixed)
    const published = await api(`${prefix}/environments/${savedId}`)
    const staleSave = await run(updateWorkflow.id, fixed, [], {}, 'failed', { inputs: [] }, null, { automation: updated.automation })
    assert.equal(staleSave.attempts.find(attempt => attempt.nodeId === 'end').error.code, 'SAVE_GENERATION_CONFLICT')
    assert.deepEqual((await api(`${prefix}/environments/${savedId}`)).environment, published.environment, 'a stale expected generation cannot overwrite newer content')
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
    // A failed run preserves its work copy for inspection; explicitly discard it
    // through the same End command offered by the task page before archiving.
    for (const terminal of [failed, conflicted, partial, staleSave]) {
      const detail = await api(`${prefix}/tasks/${terminal.task.taskId}`)
      const instance = (await api(`${prefix}/environment-instances?taskId=${terminal.task.taskId}`)).items[0]
      assert.ok(instance)
      const cleaned = await api(`${prefix}/tasks/${terminal.task.taskId}/end`, { taskId: terminal.task.taskId, runId: terminal.task.runId, instanceId: instance.instanceId, expectedUseGeneration: instance.instanceUseGeneration, executionGeneration: detail.run.executionGeneration, retainEnvironment: { enabled: false } })
      assert.equal(cleaned.outcome.complete, true)
    }
    const impact = await api(prefix + '/lifecycle-impact?action=archive')
    const archived = await api(prefix + '/archive', { impactRevision: impact.impactRevision, expectedManagementRevision: (await api(prefix)).managementRevision })
    for (let attempt = 0; attempt < 100; attempt++) {
      const operation = await api(`${prefix}/operations/${archived.operation.operationId}`)
      if (operation.status === 'succeeded') break
      assert.notEqual(operation.status, 'failed', JSON.stringify(operation))
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    assert.equal((await api(prefix)).lifecycleState, 'archived')
    const restored = await api(prefix + '/restore', { expectedManagementRevision: (await api(prefix)).managementRevision })
    for (let attempt = 0; attempt < 100; attempt++) {
      const operation = await api(`${prefix}/operations/${restored.operation.operationId}`)
      if (operation.status === 'succeeded') break
      assert.notEqual(operation.status, 'failed', JSON.stringify(operation))
      await new Promise(resolve => setTimeout(resolve, 500))
    }
    assert.equal((await api(prefix)).lifecycleState, 'active')
    return { projectId: project.projectId, environmentId, logLoad: { logCount, logPages, elapsedMs: Math.round(elapsedMs), logsPerMinute: Math.round(logCount * 60_000 / elapsedMs), scope: 'real worker throughput and server pagination; no renderer memory claim' }, taskIds: [first.task.taskId, second.task.taskId, loaded.task.taskId], checks: ['Studio HTTP saved graph', 'real browser and UUID parameters', 'cross-table query/condition/create', 'manual checkpoint continues without replay', 'End closes, saves and links', 'second automation restores login', '1000 worker logs and paginated retrieval', 'real browser timeout and original-input follow-up succeeds', 'two inputs are frozen and reclaimed after release', 'task writes advance their own cursor', 'human newer content defeats stale worker write', 'later browser failure preserves committed content and status', 'End links initial and newly created records', 'unauthorized replacement preserves prior environment', 'saved_unlinked repair does not save or run again', 'stale save generation cannot replace published content', 'statistics drilldown reaches real task', 'archive and restore preserve executed project'] }
  } finally {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  }
}
