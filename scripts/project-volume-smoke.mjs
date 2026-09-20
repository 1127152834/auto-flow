import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { join, resolve } from 'node:path'
import { promisify } from 'node:util'
import { waitFor } from './electron-cdp.mjs'
import { checkConcurrentRecordWrites } from './smoke-project-management.mjs'

// Only called with the smoke runner's disposable workspace and real HTTP service.
export async function checkProjectVolume(sidecar, cdp, click, runtime, workspace) {
  async function api(path, body, key = randomUUID()) {
    const response = await fetch(sidecar.baseUrl + '/api/v1' + path, { method: body ? 'POST' : 'GET', headers: { 'x-autoflow-token': sidecar.token, 'Idempotency-Key': key, 'content-type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(60_000) })
    const result = await response.json()
    if (!response.ok) throw new Error(`${body ? 'POST' : 'GET'} ${path}: ${JSON.stringify(result)}`, { cause: { status: response.status, code: result.error?.code } })
    return result
  }
  await cdp.command('Performance.enable')
  async function heap() {
    await cdp.command('HeapProfiler.collectGarbage')
    return (await cdp.command('Performance.getMetrics')).metrics.find(metric => metric.name === 'JSHeapUsedSize').value
  }
  const heapBefore = await heap()
  const route = `#/projects/${runtime.projectId}/runs/tasks/${runtime.taskIds[2]}/logs`
  await cdp.evaluate(`location.hash=${JSON.stringify(route)}`)
  const rows = `document.querySelectorAll('[aria-label="任务日志"] tbody tr').length`
  await waitFor(cdp, `${rows}===200`, 'first bounded log page')
  const logPageMs = []
  for (let count = 200; count < runtime.logLoad.logCount; count += 200) {
    const started = performance.now()
    await click('加载更多日志')
    await waitFor(cdp, `${rows}===${Math.min(count + 200, runtime.logLoad.logCount)}`, 'next durable log page')
    logPageMs.push(Math.round(performance.now() - started))
  }
  const heapWithLogs = await heap()
  await cdp.evaluate(`location.hash=${JSON.stringify('#/projects/' + runtime.projectId + '/overview')}`)
  const prefix = `/projects/${runtime.projectId}`
  const started = performance.now()
  const { table, ...concurrentWrites } = await checkConcurrentRecordWrites((path, options = {}) => api(path, options.body, options.key), prefix, 10_000)
  const seedMs = Math.round(performance.now() - started)
  await cdp.evaluate(`location.hash=${JSON.stringify('#/projects/' + runtime.projectId + '/data/' + table.tableId + '/records')}`)
  const recordRows = `document.querySelectorAll('[data-record-open]').length`
  await waitFor(cdp, `${recordRows}===50 && document.body.innerText.includes('1–50 / 10000')`, '10000 records render one server page')
  const pageMs = [], heapSamples = [await heap()]
  for (let page = 2; page <= 11; page++) {
    const started = performance.now()
    await click('下一页')
    await waitFor(cdp, `${recordRows}===50 && document.body.innerText.includes('${(page - 1) * 50 + 1}–${page * 50} / 10000')`, 'server record pagination')
    pageMs.push(Math.round(performance.now() - started))
    if (page === 6 || page === 11) heapSamples.push(await heap())
  }
  const frameMs = await cdp.evaluate(`new Promise(resolve=>{const start=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(performance.now()-start)))})`)
  assert.ok(frameMs < 5000, `renderer failed to respond for ${frameMs}ms`)
  // Separate synthetic input from the real worker evidence above. The helper
  // writes only this runner's disposable workspace through the existing repository.
  const logPath = `${prefix}/tasks/${runtime.taskIds[2]}/logs`
  let cursor = 0
  for (;;) {
    const page = await api(`${logPath}?afterSequence=${cursor}&pageSize=200`)
    cursor = page.afterSequence
    if (!page.hasMore) break
  }
  const root = resolve(import.meta.dirname, '..')
  const python = join(root, 'apps/backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const producer = promisify(execFile)(python, ['-X', 'utf8', join(root, 'scripts/emit-pm9-log-load.py'), workspace, runtime.taskIds[2]], { cwd: join(root, 'apps/backend'), encoding: 'utf-8', timeout: 75_000 }).then(value => ({ report: JSON.parse(value.stdout) }), error => ({ error: String(error) }))
  const synthetic = { samples: [], received: 0, scope: '60-second synthetic repository input; real HTTP pagination and renderer interaction during ingestion, not worker throughput or long-duration leak proof' }
  const seen = new Set()
  async function readSynthetic() {
    for (;;) {
      const page = await api(`${logPath}?afterSequence=${cursor}&pageSize=200`)
      assert.ok(page.items.length <= 200)
      for (const item of page.items) {
        assert.ok(item.message.startsWith('PM9 synthetic cadence '))
        assert.ok(!seen.has(item.eventId), 'synthetic pagination must not repeat')
        seen.add(item.eventId)
      }
      cursor = page.afterSequence
      if (!page.hasMore) break
    }
  }
  try {
    for (let page = 12; page <= 21; page++) {
      await new Promise(resolveWait => setTimeout(resolveWait, 6000))
      const started = performance.now()
      await readSynthetic()
      const readMs = performance.now() - started
      const interaction = performance.now()
      await click('下一页')
      await waitFor(cdp, `${recordRows}===50 && document.body.innerText.includes('${(page - 1) * 50 + 1}–${page * 50} / 10000')`, 'record pagination during synthetic log ingestion')
      synthetic.samples.push({ received: seen.size, logReadMs: Math.round(readMs), pageMs: Math.round(performance.now() - interaction), heapBytes: await heap() })
    }
    const outcome = await producer
    assert.ok(!outcome.error, outcome.error)
    synthetic.producer = outcome.report
    assert.equal(outcome.report.emitted, 1000)
    assert.ok(outcome.report.maxBatchLagMs < 5000, 'producer failed to maintain the scheduled input cadence')
    await readSynthetic()
    assert.equal(seen.size, 1000)
    synthetic.received = seen.size
  } finally {
    await producer
  }
  return { synthetic, concurrentWrites, records: 10_000, seedMode: 'five concurrent single-record HTTP writers', renderedRecordRows: 50, logRows: runtime.logLoad.logCount, seedMs, logPageMs, recordPageMs: pageMs, twoFramesMs: Math.round(frameMs), heapBytes: { before: heapBefore, withLogs: heapWithLogs, recordPageSamples: heapSamples, recordPageGrowth: heapSamples.at(-1) - heapSamples[0] }, scope: 'one disposable production Electron run; retained query pages included, no sustained-load or leak-free claim' }
}
