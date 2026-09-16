import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

describe('自定义模块写请求身份', () => {
  let restore: () => void

  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValue('stable-request') })
  })

  afterEach(() => {
    restore?.()
    vi.unstubAllGlobals()
  })

  it('创建响应未知时复用请求身份并保留 snake_case 业务字段', async () => {
    const bodies: Record<string, unknown>[] = []
    let attempt = 0
    const { configureStudioConnection } = await import('../api/config')
    restore = configureStudioConnection('http://studio.test', async (_input, init) => {
      bodies.push(JSON.parse(String(init?.body)))
      if (attempt++ === 0) throw new TypeError('network response lost')
      return Response.json({ id: 'module-1', name: 'reusable', display_name: '复用模块', revision: 1 }, { status: 201 })
    })
    const { customModulesApi } = await import('../api')
    const payload = { name: 'reusable', display_name: '复用模块', workflow: { nodes: [], edges: [] } }

    expect((await customModulesApi.create(payload)).success).toBe(false)
    expect((await customModulesApi.create(payload)).success).toBe(true)

    expect(bodies).toEqual([
      { ...payload, clientRequestId: 'stable-request' },
      { ...payload, clientRequestId: 'stable-request' },
    ])
  })

  it('更新复用未知响应的请求身份，并在成功后采用响应 revision', async () => {
    const bodies: Record<string, unknown>[] = []
    let updateAttempt = 0
    const { configureStudioConnection } = await import('../api/config')
    restore = configureStudioConnection('http://studio.test', async (_input, init) => {
      if (init?.method === 'PUT') {
        const body = JSON.parse(String(init.body))
        bodies.push(body)
        if (updateAttempt++ === 0) throw new TypeError('network response lost')
        return Response.json({ id: 'module-1', name: 'new_name', display_name: '新名称', revision: bodies.length === 2 ? 8 : 9 })
      }
      return Response.json({ id: 'module-1', name: 'old_name', display_name: '旧名称', revision: 7 })
    })
    const { customModulesApi } = await import('../api')
    await customModulesApi.get('module-1')

    expect((await customModulesApi.update('module-1', { display_name: '新名称' })).success).toBe(false)
    expect((await customModulesApi.update('module-1', { display_name: '新名称' })).success).toBe(true)
    expect((await customModulesApi.update('module-1', { display_name: '再次更新' })).success).toBe(true)

    expect(bodies.map(body => body.expectedRevision)).toEqual([7, 7, 8])
    expect(bodies.slice(0, 2).map(body => body.clientRequestId)).toEqual(['stable-request', 'stable-request'])
    expect(bodies[0].display_name).toBe('新名称')
  })

  it('删除携带已读取模块的 expectedRevision，并在响应未知时复用请求身份', async () => {
    const requests: string[] = []
    let deleteAttempt = 0
    const { configureStudioConnection } = await import('../api/config')
    restore = configureStudioConnection('http://studio.test', async (input, init) => {
      requests.push(`${init?.method || 'GET'} ${String(input)}`)
      if (init?.method === 'DELETE' && deleteAttempt++ === 0) throw new TypeError('network response lost')
      if (init?.method === 'DELETE') return Response.json({ success: true })
      return Response.json({ id: 'module-1', name: 'reusable', display_name: '复用模块', revision: 6 })
    })
    const { customModulesApi } = await import('../api')
    await customModulesApi.get('module-1')

    expect((await customModulesApi.delete('module-1')).success).toBe(false)
    expect((await customModulesApi.delete('module-1')).success).toBe(true)
    expect(requests.slice(-2)).toEqual([
      'DELETE http://studio.test/api/custom-modules/module-1?expectedRevision=6&clientRequestId=stable-request',
      'DELETE http://studio.test/api/custom-modules/module-1?expectedRevision=6&clientRequestId=stable-request',
    ])
  })

  it('导入与复制写请求提供真实后端必需的请求身份', async () => {
    const bodies: Array<{ url: string; body: Record<string, unknown> }> = []
    const { configureStudioConnection } = await import('../api/config')
    restore = configureStudioConnection('http://studio.test', async (input, init) => {
      const body = JSON.parse(String(init?.body))
      bodies.push({ url: String(input), body })
      return Response.json({ id: `module-${bodies.length}`, name: body.new_name || body.name, display_name: '模块', revision: 1 }, { status: 201 })
    })
    const { customModulesApi } = await import('../api')

    await customModulesApi.importModule({ name: 'imported', display_name: '导入模块', workflow: { nodes: [], edges: [] } })
    await customModulesApi.duplicate('module-1', 'copied_name')

    expect(bodies.map(({ url, body }) => ({ url, body }))).toEqual([
      {
        url: 'http://studio.test/api/custom-modules/import',
        body: { name: 'imported', display_name: '导入模块', workflow: { nodes: [], edges: [] }, clientRequestId: 'stable-request' },
      },
      {
        url: 'http://studio.test/api/custom-modules/module-1/duplicate',
        body: { new_name: 'copied_name', clientRequestId: 'stable-request' },
      },
    ])
  })
})
