// Real packaged app/API/worker/browser acceptance; not a native-input UI test.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, realpath, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { launchElectron, waitFor, wait } from '../../../scripts/electron-cdp.mjs'
import { stop } from '../../../scripts/smoke-sidecar.mjs'
import { projectSmokeOptions } from '../../../scripts/smoke-project-management.mjs'

projectSmokeOptions([]) // Fail closed on service/renderer/picker test substitutions.
const root = resolve(import.meta.dirname, '../../..')
const kernel = process.env.AUTOFLOW_B1_KERNEL_DIR
assert.ok(kernel, 'AUTOFLOW_B1_KERNEL_DIR must identify the installed real kernel directory')
const output = await mkdtemp(join(import.meta.dirname, 'packaged-end-'))
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-packaged-end-')))
const appPath = join(root, 'apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow')
const report = { head: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), output, workspace, appPath, startedAt: new Date().toISOString(), requests: [], sessions: [], tasks: [], verified: false }
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'reduce' } }))
await mkdir(join(workspace, 'data/kernels'), { recursive: true })
execFileSync('cp', ['-cR', kernel, join(workspace, 'data/kernels', basename(kernel))])
const server = createServer((req, res) => {
  const signedIn = (req.headers.cookie ?? '').includes('session=packaged-end-login')
  report.requests.push({ path: req.url, signedIn })
  if (req.url === '/login') res.setHeader('Set-Cookie', 'session=packaged-end-login; Path=/; Max-Age=3600; HttpOnly; SameSite=Lax')
  res.setHeader('Content-Type', 'text/html; charset=utf-8')
  res.end(`<body><p id="state">${signedIn || req.url === '/login' ? 'signed-in' : 'signed-out'}</p></body>`)
})
await new Promise(resolveReady => server.listen(0, '127.0.0.1', resolveReady))
const site = `http://127.0.0.1:${server.address().port}`
let desktop, service
async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`], cliArgs: ['--executable', appPath] })
  service = await waitFor(desktop.cdp, '(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==="ready"?r.sidecar:null})()', 'packaged sidecar', 60_000)
  await waitFor(desktop.cdp, 'document.body.innerText.includes("本地服务正常")', 'connected application')
  report.sessions.push({ pid: desktop.child.pid, debugOrigin: desktop.debugOrigin, instanceId: service.instanceId })
}
function processSnapshot() {
  return execFileSync('ps', ['-axo', 'pid=,ppid=,lstart=,command='], { encoding: 'utf8' }).split('\n').flatMap(line => {
    const match = line.match(/^\s*(\d+)\s+(\d+)\s+(\S+\s+\S+\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\d+)\s+(.*)$/)
    return match ? [{ pid: Number(match[1]), parent: Number(match[2]), birth: match[3].replace(/\s+/g, ' '), inWorkspace: match[4].includes(workspace) }] : []
  })
}
async function close() {
  if (!desktop) return
  const { child, cdp, debugOrigin } = desktop
  const before = processSnapshot()
  const owned = new Set([child.pid])
  let previousSize
  do {
    previousSize = owned.size
    for (const item of before) if (owned.has(item.parent) || item.inWorkspace) owned.add(item.pid)
  } while (owned.size !== previousSize)
  const identities = before.filter(item => owned.has(item.pid))
  assert.ok(identities.some(item => item.pid === child.pid), 'owned app identity must be observable before exit')
  cdp.close()
  await stop(child)
  assert.ok(child.exitCode !== null || child.signalCode !== null, 'owned application must exit')
  const listening = await fetch(`${debugOrigin}/json/list`, { signal: AbortSignal.timeout(1500) }).then(() => true, () => false)
  assert.equal(listening, false, 'owned debug listener must close')
  const alive = await fetch(`${service.baseUrl}/openapi.json`, { signal: AbortSignal.timeout(1500) }).then(() => true, () => false)
  assert.equal(alive, false, 'owned sidecar listener must close')
  const cleanupDeadline = Date.now() + 5000
  let remaining
  do {
    remaining = processSnapshot().filter(item => item.inWorkspace || identities.some(prior => prior.pid === item.pid && prior.birth === item.birth))
    if (!remaining.length) break
    await wait(100)
  } while (Date.now() < cleanupDeadline)
  report.sessions.at(-1).processCleanup = { identities, remaining }
  assert.deepEqual(remaining, [], 'owned processes must exit, not merely close listening ports')
  report.sessions.at(-1).closed = true
  desktop = undefined
}
async function api(path, { method = 'GET', body, status = 200, prefix = '/api/v1' } = {}) {
  const response = await fetch(`${service.baseUrl}${prefix}${path}`, { method, headers: { 'x-autoflow-token': service.token, 'Content-Type': 'application/json', 'Idempotency-Key': randomUUID() }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(20_000) })
  const value = await response.json()
  assert.equal(response.status, status, `${method} ${path}: ${JSON.stringify(value)}`)
  return value
}
async function showTask(projectId, taskId, label) {
  await desktop.cdp.evaluate(`location.hash=${JSON.stringify(`#/projects/${projectId}/runs/tasks/${taskId}/logs`)}`)
  await waitFor(desktop.cdp, 'document.body.innerText.includes("End 已完成")', 'persistent End result')
  const text = await desktop.cdp.evaluate('document.body.innerText')
  const { data } = await desktop.cdp.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(output, `${label}.txt`), text, { flag: 'wx' })
  await writeFile(join(output, `${label}.png`), Buffer.from(data, 'base64'), { flag: 'wx' })
}
try {
  await launch()
  const project = await api('/projects', { method: 'POST', status: 201, body: { name: '打包 End 登录保留验收', description: '本次专属临时项目，真实本地网页与生产worker' } })
  report.projectId = project.projectId
  const profile = await api('/profiles', { method: 'POST', status: 201, body: { name: '打包 End 专属配置', description: '', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [], browserVersion: basename(kernel).replace('chromium-', ''), browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null } })
  const prefix = `/projects/${project.projectId}`
  let saved
  for (let index = 0; index < 2; index += 1) {
    const steps = [
      ['page', 'open_page', { url: `${site}/${index ? 'status' : 'login'}`, timeout: 15 }],
      ['read', 'get_element_info', { selector: '#state', attribute: 'text', variableName: 'session_state', timeout: 5 }],
      ['end', 'project_end', { retainEnvironment: !index, name: '打包真实登录', inputIds: [] }],
      ['forbidden', 'open_page', { url: `${site}/forbidden`, timeout: 5 }],
    ]
    const workflow = await api('/workflows', { prefix: '/api', method: 'POST', status: 201, body: { id: randomUUID(), clientRequestId: randomUUID(), projectId: project.projectId, name: index ? '打包环境登录复用' : '打包 End 配置核验', nodes: steps.map(([id, type, config], n) => ({ id, type, position: { x: n * 250, y: 100 }, data: { moduleType: type, label: type, config } })), edges: steps.slice(1).map(([id], n) => ({ id: `edge-${n}`, source: steps[n][0], target: id })), variables: [] } })
    const automation = await api(`${prefix}/automations`, { method: 'POST', status: 201, body: { name: index ? '复用登录' : '保存登录', description: '', workflowId: workflow.id, inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: { ...(index ? { source: 'fixedEnvironment', environmentId: saved.environmentId } : { source: 'newFromProfile', profileId: profile.id }), proxyOverride: { mode: 'none' }, modelProviderId: null }, runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 60, manualDeadlineSeconds: 300 } } })
    const accepted = await api(`${prefix}/automations/${automation.automationId}/batches`, { method: 'POST', status: 202, body: { expectedAutomationRevision: automation.managementRevision, parameters: {}, maxTasks: 1, concurrency: 1 } })
    const batchId = accepted.operation.result.batch.batchId
    let detail
    const deadline = Date.now() + 90_000
    while (Date.now() < deadline) {
      const tasks = await api(`${prefix}/tasks?batchId=${batchId}&page=1&pageSize=10`)
      if (tasks.items.length) {
        detail = await api(`${prefix}/tasks/${tasks.items[0].taskId}`)
        if (['succeeded', 'failed', 'interrupted', 'cancelled'].includes(detail.task.status)) break
      }
      await wait(250)
    }
    assert.equal(detail?.task.status, 'succeeded', JSON.stringify(detail))
    assert.equal(detail.end?.phase, 'completed', JSON.stringify(detail))
    if (!index) saved = detail.end.outcome.saved
    report.tasks.push({ workflowId: workflow.id, automationId: automation.automationId, ...detail })
    await showTask(project.projectId, detail.task.taskId, `task-${index + 1}`)
    if (!index) {
      await close()
      await launch()
      const restored = await api(`${prefix}/tasks/${detail.task.taskId}`)
      assert.deepEqual(restored.end, detail.end, 'End persistent result must survive full application restart')
      await showTask(project.projectId, detail.task.taskId, 'task-1-after-restart')
    }
  }
  assert.ok(report.requests.some(req => req.path === '/status' && req.signedIn), 'new run must send the cookie retained by the previous real browser')
  assert.ok(!report.requests.some(req => req.path === '/forbidden'), 'End must stop downstream HTTP effects')
  report.verified = true
} catch (error) {
  report.error = String(error.stack ?? error)
  process.exitCode = 1
} finally {
  await close().catch(error => { report.cleanupError = String(error); report.verified = false; process.exitCode = 1 })
  await new Promise(resolveClosed => server.close(resolveClosed))
  report.finishedAt = new Date().toISOString()
  await writeFile(join(output, 'result.json'), JSON.stringify(report, null, 2), { flag: 'wx' })
  console.log(JSON.stringify({ output, workspace, verified: report.verified, error: report.error, cleanupError: report.cleanupError }))
}
