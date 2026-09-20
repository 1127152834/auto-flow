import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { parseArgs } from 'node:util'
import { assertOutsideHistory } from './project-smoke-output.mjs'
import { stop, waitForReady } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')

export function projectSmokeOptions(args) {
  const injected = Object.keys(process.env).find(key => process.env[key] && (key.startsWith('AUTOFLOW_QA_') || key === 'AUTOFLOW_PM4_QA' || key === 'ELECTRON_RENDERER_URL'))
  assert.ok(!injected, `production smoke forbids injected environment: ${injected}`)
  const { values, tokens } = parseArgs({ args, options: {
    executable: { type: 'string' }, 'output-dir': { type: 'string' },
  }, tokens: true })
  assert.equal(new Set(tokens.map(token => token.name)).size, tokens.length, 'duplicate option')
  for (const [name, value] of Object.entries(values)) assert.ok(value.trim(), `--${name} requires a value`)
  return values
}

// The caller supplies a service belonging to a disposable workspace it created.
// The same assertions run against source Python and the bundled sidecar.
export async function checkProjectManagement(baseUrl, token, existingProject) {
  const checks = []
  async function api(path, { method = 'GET', body, key = randomUUID(), status } = {}) {
    const response = await fetch(`${baseUrl}/api/v1${path}`, {
      method, headers: { 'x-autoflow-token': token, 'content-type': 'application/json', 'Idempotency-Key': key },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(20_000),
    })
    const result = await response.json()
    if (status) assert.equal(response.status, status, `${method} ${path}: ${JSON.stringify(result)}`)
    else assert.ok(response.ok, `${method} ${path}: ${response.status} ${JSON.stringify(result)}`)
    return result
  }
  const project = existingProject ?? await api('/projects', { method: 'POST', body: { name: 'PM9 中文 空格项目', description: '发行验收' } })
  const prefix = `/projects/${project.projectId}`
  const neighbour = await api('/projects', { method: 'POST', body: { name: 'PM9 隔离项目' } })
  const table = await api(`${prefix}/tables`, { method: 'POST', body: { name: '中文 数据表', sourceKind: 'local' } })
  const tablePath = `${prefix}/tables/${table.tableId}`
  const field = (await api(`${tablePath}/fields`, { method: 'POST', body: {
    definition: { key: 'name', name: '名称', type: 'string', required: false, validation: {} },
    sourceColumnPolicy: 'localOnly', expectedTableRevision: table.tableRevision,
  } })).field
  const fieldId = field.ref.fieldId
  const recordKey = randomUUID()
  const body = { datasetGeneration: table.datasetGeneration, values: [{ fieldId, value: '中文/空格 ' + '长文本'.repeat(100) }] }
  const record = await api(`${tablePath}/records`, { method: 'POST', body, key: recordKey })
  assert.deepEqual(await api(`${tablePath}/records`, { method: 'POST', body, key: recordKey }), record)
  assert.deepEqual((await api(`${prefix}/operations/by-idempotency-key/${recordKey}`)).result, record)
  const recordPath = `${tablePath}/records/${Buffer.from(record.ref.recordKey.value).toString('base64url')}`
  const recordIdentity = { datasetGeneration: table.datasetGeneration, recordKeyType: record.ref.recordKey.type }
  const changed = await api(recordPath, { method: 'PATCH', body: { ...recordIdentity, expectedContentRevision: record.contentRevision, values: [{ fieldId, value: '已修改' }] } })
  assert.equal(changed.contentRevision, record.contentRevision + 1)
  const conflict = await api(recordPath, { method: 'PATCH', status: 409, body: { ...recordIdentity, expectedContentRevision: record.contentRevision, values: [{ fieldId, value: '过期写入' }] } })
  assert.equal(conflict.error.code, 'REVISION_CONFLICT')
  const page = await api(`${tablePath}/records?datasetGeneration=${table.datasetGeneration}&pageSize=1`)
  assert.equal(page.total, 1)
  assert.equal(page.items[0].values[0].value, '已修改')
  await api(`/projects/${neighbour.projectId}/tables/${table.tableId}`, { status: 404 })
  checks.push('real project/table/field/record CRUD, typed identity, long Chinese text, CAS, original-key recovery and project isolation')

  async function settle(operation, path = `${prefix}/operations/${operation.operationId}`) {
    for (let attempt = 0; attempt < 100; attempt++) {
      const current = await api(path)
      if (current.status === 'succeeded') return current
      assert.notEqual(current.status, 'failed', JSON.stringify(current))
      await new Promise(resolveWait => setTimeout(resolveWait, 100))
    }
    throw new Error(`operation did not settle: ${operation.operationId}`)
  }
  const impact = await api(`${prefix}/lifecycle-impact?action=archive`)
  const archiveKey = randomUUID()
  const archiveBody = { impactRevision: impact.impactRevision, expectedManagementRevision: project.managementRevision }
  const archived = await api(`${prefix}/archive`, { method: 'POST', key: archiveKey, body: archiveBody })
  await settle(archived.operation)
  assert.equal((await api(`${prefix}/archive`, { method: 'POST', key: archiveKey, body: archiveBody })).operation.operationId, archived.operation.operationId)
  const archivedProject = await api(prefix)
  assert.equal(archivedProject.lifecycleState, 'archived')
  await api(`${prefix}/tables`, { method: 'POST', status: 409, body: { name: '归档时不得写入' } })
  const restored = await api(`${prefix}/restore`, { method: 'POST', body: { expectedManagementRevision: archivedProject.managementRevision } })
  await settle(restored.operation)
  assert.equal((await api(prefix)).lifecycleState, 'active')
  assert.equal((await api(tablePath)).recordCount, 1)
  checks.push('archive blocks writes, repeat command recovers one operation, restore preserves data')

  // Delete only the extra empty project; retain the populated one to verify restart and UI.
  const other = `/projects/${neighbour.projectId}`
  const otherImpact = await api(`${other}/lifecycle-impact?action=archive`)
  const otherArchive = await api(`${other}/archive`, { method: 'POST', body: { impactRevision: otherImpact.impactRevision, expectedManagementRevision: neighbour.managementRevision } })
  await settle(otherArchive.operation, `${other}/operations/${otherArchive.operation.operationId}`)
  const archivedNeighbour = await api(other)
  const deletion = await api(`${other}/lifecycle-impact?action=delete`)
  await api(other, { method: 'DELETE', status: 422, body: { confirmationName: '错误名字', impactRevision: deletion.impactRevision, expectedManagementRevision: archivedNeighbour.managementRevision } })
  const deleteKey = randomUUID()
  const deleted = await api(other, { method: 'DELETE', key: deleteKey, body: { confirmationName: neighbour.name, impactRevision: deletion.impactRevision, expectedManagementRevision: archivedNeighbour.managementRevision } })
  // Project-scoped lookups disappear with the project; its receipt survives at workspace scope.
  const receipt = await settle(deleted.operation, `/workspace/operations/by-idempotency-key/${deleteKey}`)
  assert.equal(receipt.result.deleted, true)
  assert.equal(receipt.result.target.projectId, neighbour.projectId)
  for (let attempt = 0; attempt < 100; attempt++) {
    const result = await api('/projects')
    if (!result.items.some(item => item.projectId === neighbour.projectId)) break
    assert.ok(attempt < 99, 'deleted project remains visible')
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  assert.equal((await api(tablePath)).recordCount, 1)
  checks.push('wrong deletion name rejected; safe deletion preserves neighbouring project records')
  return { checks, projectId: project.projectId, tableId: table.tableId, tablePath, boundary: 'production HTTP management chain; no workflow execution, browser, Sheets live or native file picker claimed' }
}

export async function main(args = process.argv.slice(2)) {
  const options = projectSmokeOptions(args)
  if (options['output-dir']) await assertOutsideHistory(join(root, 'docs/migration/project-management-pm1-qa'), options['output-dir'])
  const directory = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm9 中文 空格-')))
  const token = randomUUID()
  let child
  let report = { status: 'failed', platform: process.platform, arch: process.arch, packaged: Boolean(options.executable), startedAt: new Date().toISOString() }
  async function launch() {
    const command = options.executable ? [resolve(options.executable)] : ['uv', 'run', '--directory', 'apps/backend', 'python', '-m', 'autoflow']
    child = spawn(command[0], [...command.slice(1), '--instance-id', randomUUID(), '--data-dir', directory, '--port', '0'], {
      cwd: root, env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token }, stdio: ['ignore', 'pipe', 'inherit'],
    })
    const ready = await waitForReady(child, 60_000)
    return `http://127.0.0.1:${ready.port}`
  }
  try {
    const baseUrl = await launch()
    report = { ...report, ...await checkProjectManagement(baseUrl, token) }
    await stop(child)
    const restartedUrl = await launch()
    const response = await fetch(`${restartedUrl}/api/v1${report.tablePath}`, { headers: { 'x-autoflow-token': token }, signal: AbortSignal.timeout(20_000) })
    assert.equal(response.status, 200)
    assert.equal((await response.json()).recordCount, 1)
    report.checks.push('restarted production sidecar retains the same project and record')
    report.status = 'passed'
  } catch (error) {
    report.error = String(error.stack ?? error)
    throw error
  } finally {
    await stop(child)
    await rm(directory, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 })
    if (options['output-dir']) {
      await mkdir(options['output-dir'], { recursive: true })
      await writeFile(join(options['output-dir'], 'project-api.json'), JSON.stringify(report, null, 2))
    }
    console.log(JSON.stringify(report, null, 2))
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await main()
