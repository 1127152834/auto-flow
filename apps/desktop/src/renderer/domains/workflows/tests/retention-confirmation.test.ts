import { expect, it } from 'vitest'
import { retentionApi } from '../api'
import { retentionDefaults } from '../lib/retentionContract'
import { configureStudioConnection } from '../api/config'
const usage = { recordings: { count: 0, sizeMB: 0 }, data: { count: 0, sizeMB: 0 } }
const operations = [
  { name: 'load', call: () => retentionApi.getConfig(), valid: { success: true, config: retentionDefaults, usage } },
  { name: 'save', call: () => retentionApi.setConfig(retentionDefaults), valid: { success: true, config: retentionDefaults } },
  { name: 'usage', call: () => retentionApi.usage(), valid: { success: true, usage } },
  { name: 'cleanup', call: () => retentionApi.cleanup(), valid: { success: true, recordings: { removed: 0, freedMB: 0 }, data: { removed: 0, freedMB: 0 } } },
]
for (const operation of operations) {
  it.each([null, {}, { success: true }, { success: 'true' }, { success: true, error: '未完成' }])(`${operation.name} rejects incomplete receipt %j`, async body => {
    const restore = configureStudioConnection('http://retention.fixture', async () => Response.json(body))
    try { expect((await operation.call()).success).toBe(false) } finally { restore() }
  })
  it(`${operation.name} accepts explicit typed confirmation`, async () => {
    const restore = configureStudioConnection('http://retention.fixture', async () => Response.json(operation.valid))
    try { expect((await operation.call()).data).toMatchObject(operation.valid) } finally { restore() }
  })
  it(`${operation.name} rejects receipt from old connection`, async () => {
    let resolve!: (value: Response) => void
    const restore = configureStudioConnection('http://retention.fixture', () => new Promise(done => { resolve = done }))
    let next = () => {}
    try { const pending = operation.call(); next = configureStudioConnection('http://next.fixture', async () => Response.json({})); resolve(Response.json(operation.valid)); expect((await pending).success).toBe(false) }
    finally { next(); restore() }
  })
}
it.each([-1, 0.5, '2', null])('rejects invalid deletion count %j', async count => {
  const restore = configureStudioConnection('http://retention.fixture', async () => Response.json({ success: true, recordings: { removed: count, freedMB: 0 }, data: { removed: 0, freedMB: 0 } }))
  try { expect((await retentionApi.cleanup()).success).toBe(false) } finally { restore() }
})
