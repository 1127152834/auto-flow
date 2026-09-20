import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { waitFor } from './electron-cdp.mjs'

// Only called with the smoke runner's disposable workspace and real HTTP service.
export async function checkProjectVolume(sidecar, cdp, click, runtime) {
  async function api(path, body) {
    const response = await fetch(sidecar.baseUrl + '/api/v1' + path, { method: body ? 'POST' : 'GET', headers: { 'x-autoflow-token': sidecar.token, 'Idempotency-Key': randomUUID(), 'content-type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(60_000) })
    const result = await response.json()
    assert.ok(response.ok, JSON.stringify(result))
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
  const table = await api(prefix + '/tables', { name: 'PM9 一万行容量', sourceKind: 'local' })
  const base = `${prefix}/tables/${table.tableId}`
  const field = (await api(base + '/fields', { definition: { key: 'code', name: '编号', type: 'string', required: false, validation: {} }, expectedTableRevision: table.tableRevision, sourceColumnPolicy: 'localOnly' })).field
  const started = performance.now()
  // Five producers exercise normal writes without exhausting the HTTP thread pool.
  let next = 0
  await Promise.all(Array.from({ length: 5 }, async () => {
    while (next < 10_000) {
      const index = ++next
      await api(base + '/records', { datasetGeneration: table.datasetGeneration, values: [{ fieldId: field.ref.fieldId, value: String(index).padStart(6, '0') }] })
    }
  }))
  assert.equal((await api(base)).recordCount, 10_000)
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
  return { records: 10_000, renderedRecordRows: 50, logRows: runtime.logLoad.logCount, seedMs, logPageMs, recordPageMs: pageMs, twoFramesMs: Math.round(frameMs), heapBytes: { before: heapBefore, withLogs: heapWithLogs, recordPageSamples: heapSamples, recordPageGrowth: heapSamples.at(-1) - heapSamples[0] }, scope: 'one disposable production Electron run; retained query pages included, no sustained-load or leak-free claim' }
}
