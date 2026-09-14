import { expect, it } from 'vitest'
import { credentialApi } from '../api'
import { configureStudioConnection } from '../api/config'
const operations = [
  { name: 'upsert', call: () => credentialApi.upsert('fixture', { value: 'dummy-only' }), valid: { success: true, name: 'fixture' } },
  { name: 'rename', call: () => credentialApi.rename('fixture', 'next'), valid: { success: true } },
  { name: 'delete', call: () => credentialApi.delete('fixture'), valid: { success: true } },
]
for (const operation of operations) {
  it.each([null, {}, { success: 'true' }, { success: true, error: '未完成' }])(`${operation.name} rejects malformed receipt %j`, async body => {
    const restore = configureStudioConnection('http://credentials.fixture', async () => Response.json(body))
    try { expect((await operation.call()).success).toBe(false) } finally { restore() }
  })
  it(`${operation.name} accepts its confirmed receipt`, async () => {
    const restore = configureStudioConnection('http://credentials.fixture', async () => Response.json(operation.valid))
    try { expect((await operation.call()).data).toMatchObject(operation.valid) } finally { restore() }
  })
  it(`${operation.name} rejects an old connection confirmation`, async () => {
    let resolve!: (value: Response) => void
    const restore = configureStudioConnection('http://credentials.fixture', () => new Promise(done => { resolve = done }))
    let restoreNext = () => {}
    try {
      const pending = operation.call()
      restoreNext = configureStudioConnection('http://next.fixture', async () => Response.json({}))
      resolve(Response.json(operation.valid))
      expect(await pending).toMatchObject({ success: false })
    } finally { restoreNext(); restore() }
  })
}
it.each([{ success: true }, { success: true, name: 1 }, { success: true, name: 'another' }])('upsert requires confirmation of the requested name %j', async body => {
  const restore = configureStudioConnection('http://credentials.fixture', async () => Response.json(body))
  try { expect((await credentialApi.upsert('fixture', { value: '' })).success).toBe(false) } finally { restore() }
})
