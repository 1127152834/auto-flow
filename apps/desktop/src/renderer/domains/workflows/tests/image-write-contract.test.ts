import { expect, it, vi } from 'vitest'
import { imageAssetApi } from '../api'
import { configureStudioConnection } from '../api/config'
const asset = { id: 'image', name: 'image.png', originalName: 'image.png', size: 1, uploadedAt: '', folder: '', extension: 'png' }
const operations = [
  { name: 'upload', call: () => imageAssetApi.upload(new File(['x'], 'image.png')), valid: { asset } },
  { name: 'delete', call: () => imageAssetApi.delete('image'), valid: { success: true } },
  { name: 'rename', call: () => imageAssetApi.rename('image', 'new.png'), valid: { success: true, asset } },
  { name: 'create-folder', call: () => imageAssetApi.createFolder('new'), valid: { success: true, path: 'new' } },
  { name: 'rename-folder', call: () => imageAssetApi.renameFolder('old', 'new'), valid: { success: true, newPath: 'new' } },
  { name: 'delete-folder', call: () => imageAssetApi.deleteFolder('old'), valid: { success: true, deletedCount: 0 } },
  { name: 'move', call: () => imageAssetApi.moveAsset('image'), valid: { success: true, newFolder: '' } },
]
for (const operation of operations) {
  it.each([null, {}, { success: 'true' }, { success: false, error: '拒绝操作' }])(`${operation.name} rejects an unconfirmed receipt %j`, async body => {
    const restore = configureStudioConnection('http://images.fixture', async () => Response.json(body))
    try { expect((await operation.call()).success).toBe(false) } finally { restore() }
  })
  it(`${operation.name} accepts its documented receipt`, async () => {
    const restore = configureStudioConnection('http://images.fixture', async () => Response.json(operation.valid))
    try {
      const result = await operation.call()
      expect(result.success).toBe(true)
      expect(result.data).toMatchObject(operation.valid)
      if (result.data && 'asset' in result.data) expect(result.data.asset.path).toBeNull()
    } finally { restore() }
  })
}
it('does not accept malformed image metadata as an uploaded asset', async () => {
  const fetcher = vi.fn(async () => Response.json({ asset: { ...asset, size: -1 } }))
  const restore = configureStudioConnection('http://images.fixture', fetcher)
  try { expect((await imageAssetApi.upload(new File(['x'], 'image.png'))).success).toBe(false) } finally { restore() }
})
it.each([
  ['create-folder', { success: true, path: 1 }],
  ['rename-folder', { success: true, newPath: 1 }],
  ['move', { success: true, newFolder: false }],
  ['delete-folder', { success: true, deletedCount: -1 }],
  ['delete-folder', { success: true, deletedCount: 1.5 }],
  ['delete-folder', { success: true, deletedCount: '1' }],
  ['delete', { success: true, error: '未完成删除' }],
] as const)('rejects contradictory or mistyped %s receipt %j', async (name, body) => {
  const restore = configureStudioConnection('http://images.fixture', async () => Response.json(body))
  try { expect((await operations.find(operation => operation.name === name)!.call()).success).toBe(false) } finally { restore() }
})
