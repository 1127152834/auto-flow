import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { createServer } from 'node:http'
import { observeInstanceSeed } from './smoke-profile-test-browser.mjs'

// Real Studio HTTP -> project batch -> child worker -> browser -> data/End.
export async function checkProjectRuntime(baseUrl, token, browserVersion, hooks = {}) {
  const server = createServer((request, response) => {
    if (request.url === '/login') response.setHeader('Set-Cookie', ['pm9=logged-in; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax', 'pm9-session=1; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax'])
    if (request.url === '/unsaved-session') response.setHeader('Set-Cookie', 'pm9-session=9; Path=/; HttpOnly; Max-Age=3600; SameSite=Lax')
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
    response.end(`<output id="account">001</output><output id="auth">${request.headers.cookie?.includes('pm9=logged-in') ? 'signed-in' : 'signed-out'}</output><output id="session">${request.headers.cookie?.split('; ').find(value => value.startsWith('pm9-session='))?.slice('pm9-session='.length) ?? 'missing'}</output>`)
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
    const first = await run(workflow.id, { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }, [{ parameterId: parameter, name: '后缀', type: 'string', required: true }], { [parameter]: '中文' })
    assert.equal(first.resumedManualItems, 1)
    assert.equal(first.outputs.find(output => output.name === 'humanConfirmation')?.value, 'human-verified')
    assert.equal(first.attempts.some(attempt => attempt.nodeId === 'alternate'), false)
    const records = await api(`${prefix}/tables/${target.table.tableId}/records?datasetGeneration=${target.table.datasetGeneration}`)
    assert.equal(records.total, 1)
    assert.equal(records.items[0].values[0].value, '001-中文')
    const environmentId = records.items[0].currentEnvironmentId
    assert.ok(environmentId)
    const readLogin = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 登录复用', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#auth', attribute: 'text', variableName: 'login' }), node('session', 'get_element_info', { selector: '#session', attribute: 'text', variableName: 'session' }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'read'), edge('read', 'session'), edge('session', 'end')] })
    const second = await run(readLogin.id, { source: 'fixedEnvironment', environmentId, proxyOverride: { mode: 'none' }, modelProviderId: null })
    assert.equal(second.outputs.find(output => output.name === 'login')?.value, 'signed-in')
    assert.equal(second.outputs.find(output => output.name === 'session')?.value, '1')
    const savedBeforeDiscard = (await api(`${prefix}/environments/${environmentId}`)).environment
    const savedEnvironmentCount = (await api(prefix + '/environments')).total
    const changedSession = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 修改会话但不保存', variables: [], nodes: [node('change', 'open_page', { url: site + '/unsaved-session' }), node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: '#session', attribute: 'text', variableName: 'session' }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('change', 'open'), edge('open', 'read'), edge('read', 'end')] })
    const unretained = []
    const changed = await run(changedSession.id, { source: 'fixedEnvironment', environmentId, proxyOverride: { mode: 'none' }, modelProviderId: null })
    assert.equal(changed.outputs.find(output => output.name === 'session')?.value, '9', 'the real browser work copy must actually change before discard')
    const restoredSession = await run(readLogin.id, {}, [], {}, 'succeeded', { inputs: [] }, null, { automation: second.automation })
    assert.equal(restoredSession.outputs.find(output => output.name === 'session')?.value, '1', 'later fixed restore must read the saved session, not the discarded work copy')
    assert.equal(restoredSession.outputs.find(output => output.name === 'login')?.value, 'signed-in')
    for (const result of [changed, restoredSession]) {
      let instance
      for (let attempt = 0; attempt < 100; attempt++) {
        instance = (await api(`${prefix}/environment-instances?taskId=${result.task.taskId}`)).items[0]
        if (instance?.state === 'cleaned') break
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      assert.equal(instance?.state, 'cleaned', 'End without retention cleans its work copy by default')
      assert.equal(instance.sourceContentGeneration, savedBeforeDiscard.ref.contentGeneration)
      unretained.push({ taskId: result.task.taskId, instanceId: instance.instanceId, state: instance.state })
    }
    assert.notEqual(unretained[0].instanceId, unretained[1].instanceId)
    assert.deepEqual((await api(`${prefix}/environments/${environmentId}`)).environment, savedBeforeDiscard, 'no-retention End must not publish or revise the saved environment')
    assert.equal((await api(prefix + '/environments')).total, savedEnvironmentCount, 'no-retention End must not silently save another environment')
    const noAutomaticSave = { status: 'passed', savedEnvironmentCount, environmentId, savedGeneration: savedBeforeDiscard.ref.contentGeneration, modifiedSession: '9', restoredSession: '1', instances: unretained, scope: 'actual fixed-environment browser work copy changes its persistent cookie, succeeds without save, is cleaned, then a new Task restores the old saved value and unchanged environment facts' }
    await hooks.verifyUnretained?.(project.projectId, noAutomaticSave)
    const selectorParameter = randomUUID()
    const failureWorkflow = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 失败后续', variables: [], nodes: [node('open', 'open_page', { url: site + '/account' }), node('read', 'get_element_info', { selector: `{${selectorParameter}}`, attribute: 'text', variableName: 'account', timeout: .3 }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'read'), edge('read', 'end')] })
    const inputPlan = { inputs: [{ inputId: randomUUID(), alias: '来源', tableId: source.table.tableId, datasetGeneration: source.table.datasetGeneration, mode: 'independent', required: true, fieldBindings: [{ inputFieldId: randomUUID(), inputFieldAlias: '编号', fieldRef: { projectId: project.projectId, tableId: source.table.tableId, datasetGeneration: source.table.datasetGeneration, fieldId: source.fieldId } }], filter: { type: 'all', items: [] }, orderBy: [{ systemField: 'recordKey', direction: 'asc' }] }] }
    const environment = { source: 'newFromProfile', profileId: profile.id, proxyOverride: { mode: 'none' }, modelProviderId: null }
    const profileSpec = { name: 'PM9 身份冻结', browserVersion, headless: true, userAgent: 'AutoFlow-PM9-frozen', locale: 'en-US', timezone: 'UTC' }
    const frozenProfile = await api('/api/v1/profiles', profileSpec)
    const profileEnvironment = { ...environment, profileId: frozenProfile.id }
    const profileDocument = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 Profile冻结', variables: [], nodes: [node('open', 'open_page', { url: site + '/profile' }), node('observe', 'get_element_info', { selector: '#profile-observation', attribute: 'text', variableName: 'observation' }), node('pause-profile', 'project_manual', { reason: '首个Task等待时编辑Profile与根文档', timeoutSeconds: 60 }), node('end', 'project_end', { retainEnvironment: { enabled: false } })], edges: [edge('open', 'observe'), edge('observe', 'pause-profile'), edge('pause-profile', 'end')] })
    let newSeed
    const seedObservations = []
    const profileBatch = await run(profileDocument.id, profileEnvironment, [], {}, 'succeeded', { inputs: [] }, null, { maxTasks: 2, beforeResume: async item => {
      const observation = await observeInstanceSeed(item.instanceId)
      if (observation) assert.equal(observation.seed, frozenProfile.fingerprintSeed)
      seedObservations.push(observation)
      if (newSeed !== undefined) return
      await api(`/api/v1/profiles/${frozenProfile.id}`, { ...profileSpec, userAgent: 'AutoFlow-PM9-edited', locale: 'fr-FR', timezone: 'Europe/Paris' }, 'PUT')
      newSeed = (await api(`/api/v1/profiles/${frozenProfile.id}/regenerate-fingerprint`, {})).fingerprintSeed
      assert.notEqual(newSeed, frozenProfile.fingerprintSeed)
      const changed = structuredClone(profileDocument)
      changed.nodes.find(node => node.id === 'observe').data.variableName = 'newObservation'
      await api(`/api/workflows/${changed.id}`, { ...changed, expectedRevision: changed.revision, clientRequestId: randomUUID() }, 'PUT')
    } })
    const observed = []
    for (const task of profileBatch.tasks) {
      const outputs = (await api(`${prefix}/tasks/${task.taskId}/outputs`)).items
      assert.equal(outputs.some(output => output.name === 'newObservation'), false, 'new root content must not enter old batch')
      observed.push(JSON.parse(outputs.find(output => output.name === 'observation').value))
    }
    assert.equal(observed.length, 2)
    assert.deepEqual(observed[0], observed[1], 'same frozen profile has identical browser-visible identity')
    assert.equal(observed[0].userAgent, profileSpec.userAgent)
    assert.equal(observed[0].language, 'en-US')
    assert.equal(observed[0].timezone, 'UTC')
    const freshProfileBatch = await run(profileDocument.id, profileEnvironment, [], {}, 'succeeded', { inputs: [] }, null, { automation: profileBatch.automation, beforeResume: async item => {
      const observation = await observeInstanceSeed(item.instanceId)
      if (observation) assert.equal(observation.seed, newSeed)
      seedObservations.push(observation)
    } })
    const freshObservation = JSON.parse(freshProfileBatch.outputs.find(output => output.name === 'newObservation').value)
    assert.equal(freshObservation.userAgent, 'AutoFlow-PM9-edited')
    assert.equal(freshObservation.language, 'fr-FR')
    assert.equal(freshObservation.timezone, 'Europe/Paris')
    const profileFreeze = { status: 'passed', taskIds: profileBatch.tasks.map(task => task.taskId), freshTaskId: freshProfileBatch.task.taskId, originalSeed: frozenProfile.fingerprintSeed, newSeed, seedObservations, seedObservationScope: process.platform === 'darwin' ? 'actual disposable instance browser argv at manual barrier' : 'native argv seed proof pending on this platform', canvasChanged: freshObservation.canvasHash !== observed[0].canvasHash, frozenObservation: observed[0], freshObservation, checks: ['old batch second Task preserves original root document and browser-visible UA/locale/timezone/canvas after public Profile edit and seed reset', 'fresh explicit batch observes new root document and changed Profile identity'] }
    const parallelTable = await table('并行循环结果')
    const parallelWrite = (id, value) => node(id, 'project_data', { operation: 'createRecord', variableName: 'saved', tableGrant: grant(parallelTable, 'createRecord'), arguments: { tableId: parallelTable.table.tableId, datasetGeneration: parallelTable.table.datasetGeneration, values: { [parallelTable.fieldId]: value } } })
    const parallelDocument = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 并行循环隔离', variables: [], nodes: [
      node('fork', 'set_variable', { variableName: 'started', variableValue: 'yes', parallel: { joinNodeId: 'end', outputs: { left: { saved: 'leftSaved' }, right: { saved: 'rightSaved' } } } }),
      node('left', 'loop', { count: 2, indexVariable: 'index' }), parallelWrite('left-write', 'A-{index}'),
      node('right', 'loop', { count: 3, indexVariable: 'index' }), parallelWrite('right-write', 'B-{index}'),
      node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: '并行声明输出', recordTargets: ['leftSaved', 'rightSaved'].map(name => ({ recordRef: `{${name}['ref']}`, expectedLinkRevision: `{${name}['linkRevision']}`, replaceAllowed: false })) } }),
    ], edges: [edge('fork', 'left'), edge('fork', 'right'), edge('left', 'left-write', 'loop'), edge('right', 'right-write', 'loop'), edge('left', 'end', 'done'), edge('right', 'end', 'done')] })
    const parallelRun = await run(parallelDocument.id, environment)
    const parallelRows = (await api(`${prefix}/tables/${parallelTable.table.tableId}/records?datasetGeneration=${parallelTable.table.datasetGeneration}`)).items
    assert.deepEqual(parallelRows.map(row => row.values[0].value).sort(), ['A-0', 'A-1', 'B-0', 'B-1', 'B-2'])
    assert.deepEqual(parallelRows.filter(row => row.currentEnvironmentId).map(row => row.values[0].value).sort(), ['A-1', 'B-2'], 'only declared final branch records are linked')
    assert.equal(new Set(parallelRows.filter(row => row.currentEnvironmentId).map(row => row.currentEnvironmentId)).size, 1)
    assert.equal(parallelRun.attempts.filter(item => item.nodeId === 'end').length, 1)
    const parallelEvents = (await api(`${prefix}/tasks/${parallelRun.task.taskId}/events?afterSequence=0&pageSize=200`)).items
    for (const [id, count] of [['left-write', 2], ['right-write', 3]]) {
      const starts = parallelEvents.filter(event => event.kind === 'nodeAttempt' && event.nodeId === id && event.payload.status === 'started')
      assert.equal(starts.length, count)
      assert.equal(new Set(starts.map(event => event.nodeVisitId)).size, count, 'each loop side effect has its own visit')
    }
    const manualParallelDocument = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 并行人工队列', variables: [], nodes: [
      parallelWrite('before-fork', 'before-manual'),
      node('fork', 'set_variable', { variableName: 'started', variableValue: 'yes', parallel: { joinNodeId: 'joined', outputs: { 'manual-left': { local: 'leftResult' }, 'manual-right': { local: 'rightResult' } } } }),
      node('manual-left', 'project_manual', { reason: '左分支', timeoutSeconds: 60 }), node('manual-right', 'project_manual', { reason: '右分支', timeoutSeconds: 60 }),
      node('after-left', 'set_variable', { variableName: 'local', variableValue: 'left' }), node('after-right', 'set_variable', { variableName: 'local', variableValue: 'right' }),
      node('joined', 'set_variable', { variableName: 'joined', variableValue: '{leftResult}/{rightResult}' }),
      node('end', 'project_end', { retainEnvironment: { enabled: false } }),
    ], edges: [edge('before-fork', 'fork'), edge('fork', 'manual-left'), edge('fork', 'manual-right'), edge('manual-left', 'after-left'), edge('manual-right', 'after-right'), edge('after-left', 'joined'), edge('after-right', 'joined'), edge('joined', 'end')] })
    const manualOrder = []
    const manualParallelRun = await run(manualParallelDocument.id, environment, [], {}, 'succeeded', { inputs: [] }, null, { beforeResume: async item => {
      const items = (await api(prefix + '/manual-items')).items.filter(other => other.taskId === item.taskId)
      assert.equal(items.filter(other => other.status === 'waiting').length, 1, 'one persistent live checkpoint per Task')
      const attempts = (await api(`${prefix}/tasks/${item.taskId}/node-attempts`)).items
      assert.equal(attempts.some(attempt => ['after-left', 'after-right', 'joined', 'end'].includes(attempt.nodeId)), false, 'queued manual handoff precedes ordinary branch work')
      manualOrder.push(item.manualItemId)
    } })
    assert.equal(manualParallelRun.resumedManualItems, 2)
    assert.equal(new Set(manualOrder).size, 2)
    assert.equal(manualParallelRun.outputs.find(output => output.name === 'joined')?.value, 'left/right')
    for (const id of ['after-left', 'after-right', 'joined', 'end']) assert.equal(manualParallelRun.attempts.filter(item => item.nodeId === id).length, 1)
    const stoppedParallelRun = await run(manualParallelDocument.id, environment, [], {}, 'cancelled', { inputs: [] }, null, { stopAtManual: true, automation: manualParallelRun.automation })
    assert.equal(stoppedParallelRun.attempts.some(attempt => ['after-left', 'after-right', 'joined', 'end'].includes(attempt.nodeId)), false)
    const stoppedManualItems = (await api(prefix + '/manual-items')).items.filter(item => item.taskId === stoppedParallelRun.task.taskId)
    assert.equal(stoppedManualItems.length, 1, 'stopping discards the queued checkpoint')
    assert.equal(stoppedManualItems[0].status, 'cancelled')
    const manualRows = (await api(`${prefix}/tables/${parallelTable.table.tableId}/records?datasetGeneration=${parallelTable.table.datasetGeneration}`)).items.filter(row => row.values[0].value === 'before-manual')
    assert.equal(manualRows.length, 2, 'both pre-fork writes survive, including the cancelled Task')
    assert.ok(manualRows.every(row => row.currentEnvironmentId === null))
    const parallel = { status: 'passed', loopTaskId: parallelRun.task.taskId, manualTaskId: manualParallelRun.task.taskId, stoppedTaskId: stoppedParallelRun.task.taskId, loopValues: parallelRows.map(row => row.values[0].value).sort(), linkedValues: parallelRows.filter(row => row.currentEnvironmentId).map(row => row.values[0].value).sort(), manualItems: manualOrder.length, retainedPreForkWrites: manualRows.length, checks: ['same-name loop variables isolated; exact 2/3 values and distinct public event visit IDs', 'only declared last outputs linked by one End', 'two live manual checkpoints serialized before ordinary branch work and join runs once', 'stop discards queued manual, prevents branch/join/End and retains committed pre-fork record'] }
    // Freeze is observed through a real manual barrier after prepare. No in-process worker hooks.
    const childTable = await table('子流程冻结结果')
    const childWrite = id => node(id, 'project_data', { operation: 'createRecord', variableName: 'saved', tableGrant: grant(childTable, 'createRecord'), arguments: { tableId: childTable.table.tableId, datasetGeneration: childTable.table.datasetGeneration, values: { [childTable.fieldId]: '{value}' } } })
    const childDocument = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 打包冻结子流程', variables: [], nodes: [
      node('open', 'open_page', { url: site + '/account' }),
      node('private', 'set_variable', { variableName: 'privateValue', variableValue: 'parent-only' }),
      node('freeze-barrier', 'project_manual', { reason: '准备后编辑源子流程', timeoutSeconds: 60 }),
      node('first-call', 'subflow', { subflowGroupId: 'child', inputs: { value: 'frozen-first' }, outputs: { saved: 'firstSaved' } }),
      node('second-call', 'subflow', { subflowGroupId: 'child', inputs: { value: 'frozen-second' }, outputs: { saved: 'secondSaved' } }),
      node('inspect-parent', 'set_variable', { variableName: 'parentAfterCalls', variableValue: '{privateValue}' }),
      node('end', 'project_end', { retainEnvironment: { enabled: true, mode: 'saveAs', name: "{firstSaved['ref']['recordKey']['value']}", recordTargets: ['firstSaved', 'secondSaved'].map(name => ({ recordRef: `{${name}['ref']}`, expectedLinkRevision: `{${name}['linkRevision']}`, replaceAllowed: false })) } }),
      node('child', 'subflow_header', { subflowName: '冻结子图' }),
      node('child-private', 'set_variable', { variableName: 'privateValue', variableValue: 'child-only' }), childWrite('child-write'),
    ], edges: [edge('open', 'private'), edge('private', 'freeze-barrier'), edge('freeze-barrier', 'first-call'), edge('first-call', 'second-call'), edge('second-call', 'inspect-parent'), edge('inspect-parent', 'end'), edge('child', 'child-private'), edge('child-private', 'child-write')] })
    let editedChild = false
    const subflow = await run(childDocument.id, environment, [], {}, 'succeeded', { inputs: [] }, null, { maxTasks: 2, expectedVisits: { 'child-private': 2, 'child-write': 2 }, beforeResume: async () => {
      if (editedChild) return
      const changed = structuredClone(childDocument)
      changed.nodes.find(node => node.id === 'child-write').data.arguments.values[childTable.fieldId] = 'must-not-replace-frozen-content'
      const saved = await api(`/api/workflows/${changed.id}`, { ...changed, expectedRevision: changed.revision, clientRequestId: randomUUID() }, 'PUT')
      assert.equal(saved.revision, changed.revision + 1)
      editedChild = true
    } })
    assert.equal(editedChild, true)
    assert.equal(subflow.resumedManualItems, 2)
    const childRecords = await api(`${prefix}/tables/${childTable.table.tableId}/records?datasetGeneration=${childTable.table.datasetGeneration}`)
    assert.deepEqual(childRecords.items.map(record => record.values[0].value).sort(), ['frozen-first', 'frozen-first', 'frozen-second', 'frozen-second'])
    assert.ok(childRecords.items.every(record => record.currentEnvironmentId))
    assert.equal(new Set(childRecords.items.map(record => record.currentEnvironmentId)).size, 2)
    for (const task of subflow.tasks) {
      const outputs = (await api(`${prefix}/tasks/${task.taskId}/outputs`)).items
      assert.equal(outputs.find(output => output.name === 'parentAfterCalls')?.value, 'parent-only')
      const attempts = (await api(`${prefix}/tasks/${task.taskId}/node-attempts`)).items
      const writes = attempts.filter(attempt => attempt.nodeId === 'child-write')
      assert.equal(writes.length, 2)
      assert.equal(new Set(writes.map(attempt => attempt.nodeVisitId)).size, 2)
      assert.ok(writes.every(attempt => attempt.status === 'succeeded'))
    }
    const cancelTable = await table('子流程取消保留')
    const cancelWrite = (id, value) => node(id, 'project_data', { operation: 'createRecord', variableName: id, tableGrant: grant(cancelTable, 'createRecord'), arguments: { tableId: cancelTable.table.tableId, datasetGeneration: cancelTable.table.datasetGeneration, values: { [cancelTable.fieldId]: value } } })
    const cancelDocument = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 打包子流程取消', variables: [], nodes: [
      node('open', 'open_page', { url: site + '/account' }), node('call', 'subflow', { subflowGroupId: 'child', inputs: {}, outputs: {} }), node('end', 'project_end', { retainEnvironment: { enabled: false } }),
      node('child', 'subflow_header', { subflowName: '取消子图' }), cancelWrite('committed', 'before-cancel'), node('cancel-barrier', 'project_manual', { reason: '子流程内取消父批次', timeoutSeconds: 60 }), cancelWrite('forbidden-later', 'must-not-write'),
    ], edges: [edge('open', 'call'), edge('call', 'end'), edge('child', 'committed'), edge('committed', 'cancel-barrier'), edge('cancel-barrier', 'forbidden-later')] })
    const cancelledSubflow = await run(cancelDocument.id, environment, [], {}, 'cancelled', { inputs: [] }, null, { stopAtManual: true })
    assert.equal(cancelledSubflow.resumedManualItems, 0)
    const retained = await api(`${prefix}/tables/${cancelTable.table.tableId}/records?datasetGeneration=${cancelTable.table.datasetGeneration}`)
    assert.deepEqual(retained.items.map(record => record.values[0].value), ['before-cancel'])
    assert.equal(retained.items[0].currentEnvironmentId, null)
    assert.equal(cancelledSubflow.attempts.some(attempt => ['forbidden-later', 'end'].includes(attempt.nodeId)), false)
    const cancelledManual = (await api(prefix + '/manual-items')).items.filter(item => item.taskId === cancelledSubflow.task.taskId)
    assert.equal(cancelledManual.length, 1)
    assert.equal(cancelledManual[0].status, 'cancelled')
    // A broader parent grant must not be inherited by a narrower child declaration.
    const scopedTable = await table('子流程字段权限')
    const parentField = (await api(`${prefix}/tables/${scopedTable.table.tableId}/fields`, { definition: { key: 'parent', name: '仅父流程', type: 'string', required: false, validation: {} }, sourceColumnPolicy: 'localOnly', expectedTableRevision: (await api(`${prefix}/tables/${scopedTable.table.tableId}`)).tableRevision })).field.ref.fieldId
    const scopedWrite = (id, declaredFields, value) => node(id, 'project_data', { operation: 'createRecord', variableName: id, tableGrant: { ...grant(scopedTable, 'createRecord'), fieldIds: declaredFields }, arguments: { tableId: scopedTable.table.tableId, datasetGeneration: scopedTable.table.datasetGeneration, values: { [parentField]: value } } })
    const scopedDocument = await api('/api/workflows', { id: randomUUID(), clientRequestId: randomUUID(), name: 'PM9 打包子流程权限收窄', variables: [], nodes: [
      node('open', 'open_page', { url: site + '/account' }), scopedWrite('parent-write', [parentField], 'parent-owned'), node('call', 'subflow', { subflowGroupId: 'child', inputs: {}, outputs: {} }), node('end', 'project_end', { retainEnvironment: { enabled: false } }),
      node('child', 'subflow_header', { subflowName: '受限子图' }), scopedWrite('child-denied', [scopedTable.fieldId], 'must-not-borrow-parent-field'),
    ], edges: [edge('open', 'parent-write'), edge('parent-write', 'call'), edge('call', 'end'), edge('child', 'child-denied')] })
    const deniedSubflow = await run(scopedDocument.id, environment, [], {}, 'failed')
    assert.equal(deniedSubflow.attempts.find(attempt => attempt.nodeId === 'parent-write')?.status, 'succeeded')
    assert.equal(deniedSubflow.attempts.find(attempt => attempt.nodeId === 'child-denied')?.error?.code, 'CAPABILITY_SCOPE_DENIED')
    assert.equal(deniedSubflow.attempts.some(attempt => attempt.nodeId === 'end'), false)
    const scopedRecords = await api(`${prefix}/tables/${scopedTable.table.tableId}/records?datasetGeneration=${scopedTable.table.datasetGeneration}`)
    assert.equal(scopedRecords.total, 1)
    assert.equal(scopedRecords.items[0].values.find(value => value.fieldId === parentField)?.value, 'parent-owned')
    const subflows = { status: 'passed', frozenTaskIds: subflow.tasks.map(task => task.taskId), cancelledTaskId: cancelledSubflow.task.taskId, deniedTaskId: deniedSubflow.task.taskId, deniedCode: 'CAPABILITY_SCOPE_DENIED', sourceEditedAfterPrepare: editedChild, recordsAfterTwoTasks: childRecords.total, retainedAfterCancel: retained.total, checks: ['two tasks use frozen child after public document edit at live manual barrier', 'two calls export separate records and keep parent private variable', 'root End links both outputs for each task', 'public parent batch stop cancels child checkpoint, prevents later write/End and retains committed record', 'child cannot borrow parent field permission; parent committed record survives the denied child write'] }
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
    assert.equal(repeatDetails[1].inputSnapshot.inputs[1].contentRevision, repeatDetails[0].inputSnapshot.inputs[1].contentRevision, 'unchanged companion content must remain reusable')
    assert.equal(repeatDetails[1].inputSnapshot.inputs[1].statusRevision, repeatDetails[0].inputSnapshot.inputs[1].statusRevision, 'unchanged companion status must remain reusable')
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
    // The scheduler cleans terminal instances unless a failed save preserved
    // the work copy. Explicitly discard only that retained copy.
    for (const terminal of [failed, conflicted, partial, staleSave, cancelledSubflow, deniedSubflow]) {
      let instance
      for (let attempt = 0; attempt < 100; attempt++) {
        instance = (await api(`${prefix}/environment-instances?taskId=${terminal.task.taskId}`)).items[0]
        if (['cleaned', 'retained_unsaved'].includes(instance?.state)) break
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      assert.ok(instance, `terminal task ${terminal.task.taskId} must have an instance`)
      if (instance.state === 'retained_unsaved') {
        const detail = await api(`${prefix}/tasks/${terminal.task.taskId}`)
        const discarded = await api(`${prefix}/tasks/${terminal.task.taskId}/end`, { taskId: terminal.task.taskId, runId: terminal.task.runId, instanceId: instance.instanceId, expectedUseGeneration: instance.instanceUseGeneration, executionGeneration: detail.run.executionGeneration, retainEnvironment: { enabled: false } })
        assert.equal(discarded.outcome.complete, true)
        instance = (await api(`${prefix}/environment-instances?taskId=${terminal.task.taskId}`)).items[0]
      }
      assert.equal(instance.state, 'cleaned', `terminal task ${terminal.task.taskId} must be reclaimed before archive`)
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
    return { projectId: project.projectId, environmentId, subflows, profileFreeze, parallel, noAutomaticSave, logLoad: { logCount, logPages, elapsedMs: Math.round(elapsedMs), logsPerMinute: Math.round(logCount * 60_000 / elapsedMs), scope: 'real worker throughput and server pagination; no renderer memory claim' }, taskIds: [first.task.taskId, second.task.taskId, loaded.task.taskId], checks: ['Studio HTTP saved graph', 'real browser and UUID parameters', 'cross-table query/condition/create', 'manual checkpoint continues without replay', 'End closes, saves and links', 'second automation restores login', '1000 worker logs and paginated retrieval', 'real browser timeout and original-input follow-up succeeds', 'two inputs are frozen and reclaimed after release', 'task writes advance their own cursor', 'human newer content defeats stale worker write', 'later browser failure preserves committed content and status', 'End links initial and newly created records', 'unauthorized replacement preserves prior environment', 'saved_unlinked repair does not save or run again', 'stale save generation cannot replace published content', 'statistics drilldown reaches real task', 'archive and restore preserve executed project'] }
  } finally {
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  }
}
