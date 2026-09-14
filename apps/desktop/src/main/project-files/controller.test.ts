// @vitest-environment node
import { lstat, mkdtemp, mkdir, realpath, symlink, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it, vi } from 'vitest'
import { ProjectFilesController, type ProjectFilesDependencies } from './controller'

const projectId = '726a0f9e-a0e7-4b83-9794-b8d5946825e0'
const host = { state: 'ready' as const, baseUrl: 'http://127.0.0.1:43127', hostToken: 'host-token', dataDir: '/workspace/data' }
const mainFrame = {}
const event = { sender: { id: 7, mainFrame }, senderFrame: mainFrame }

async function setup(overrides: Partial<ProjectFilesDependencies> = {}) {
  const root = await mkdtemp(join(tmpdir(), 'autoflow-project-files-'))
  const input = join(root, '客户 数据.xlsx')
  await writeFile(input, 'xlsx fixture')
  let uuidIndex = 0
  const uuids = ['4cc4bd80-8f6a-48a7-a989-748e43a45389', '3b6bc274-3d0d-4a14-a1ce-c5ce07a6d53c']
  const dependencies: ProjectFilesDependencies = {
    allowedSenderId: 7,
    getHostStatus: () => host,
    showOpenDialog: vi.fn(async () => ({ canceled: false, filePaths: [input] })),
    showSaveDialog: vi.fn(async () => ({ canceled: false, filePath: join(root, '结果 数据.xlsx') })),
    register: vi.fn(async () => undefined),
    now: () => new Date('2026-09-13T12:00:00.000Z'),
    randomUUID: () => uuids[uuidIndex++] ?? crypto.randomUUID(),
    ...overrides,
  }
  return { root, input, dependencies, controller: new ProjectFilesController(dependencies) }
}

describe('controlled project Excel selection', () => {
  it('returns only an input capability after registering its trusted path', async () => {
    const context = await setup()
    await expect(context.controller.chooseExcelInput(event, projectId)).resolves.toEqual({ ok: true, value: {
      selectionToken: '4cc4bd80-8f6a-48a7-a989-748e43a45389', displayName: '客户 数据.xlsx',
      kind: 'excelInput', expiresAt: '2026-09-13T12:05:00.000Z',
    } })
    expect(context.dependencies.register).toHaveBeenCalledWith(host, expect.objectContaining({
      path: await realpath(context.input), projectId, windowId: 7, purpose: 'inspectExcel',
    }), expect.any(String))
  })

  it('returns success with null when either native dialog is cancelled', async () => {
    const input = await setup({ showOpenDialog: vi.fn(async () => ({ canceled: true, filePaths: [] })) })
    const output = await setup({ showSaveDialog: vi.fn(async () => ({ canceled: true })) })
    await expect(input.controller.chooseExcelInput(event, projectId)).resolves.toEqual({ ok: true, value: null })
    await expect(output.controller.chooseXlsxOutput(event, projectId, '结果.xlsx')).resolves.toEqual({ ok: true, value: null })
    expect(input.dependencies.register).not.toHaveBeenCalled()
    expect(output.dependencies.register).not.toHaveBeenCalled()
  })

  it('registers a new XLSX output without creating it', async () => {
    const context = await setup()
    const result = await context.controller.chooseXlsxOutput(event, projectId, '结果 数据.xlsx')
    expect(result).toEqual({ ok: true, value: {
      selectionToken: '4cc4bd80-8f6a-48a7-a989-748e43a45389', displayName: '结果 数据.xlsx',
      kind: 'xlsxOutput', expiresAt: '2026-09-13T12:05:00.000Z',
    } })
    expect(context.dependencies.register).toHaveBeenCalledWith(host, expect.objectContaining({
      projectId, windowId: 7, purpose: 'exportXlsx', path: expect.stringMatching(/结果 数据\.xlsx$/),
    }), expect.any(String))
    await expect(lstat(join(context.root, '结果 数据.xlsx'))).rejects.toMatchObject({ code: 'ENOENT' })
  })

  it('rejects untrusted frames and malformed project ids before opening a dialog', async () => {
    const context = await setup()
    await expect(context.controller.chooseExcelInput({ ...event, senderFrame: {} }, projectId)).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
    await expect(context.controller.chooseXlsxOutput({ ...event, senderFrame: {} }, projectId, '../bad.xls')).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
    await expect(context.controller.chooseExcelInput(event, '../project')).resolves.toMatchObject({ ok: false, error: { code: 'INVALID_PROJECT_ID' } })
    expect(context.dependencies.showOpenDialog).not.toHaveBeenCalled()
  })

  it('rejects service switches while the dialog or registration is in flight', async () => {
    let current = host
    const duringDialog = await setup({
      getHostStatus: () => current,
      showOpenDialog: vi.fn(async () => { current = { ...host, hostToken: 'new-token' }; return { canceled: false, filePaths: [(await setup()).input] } }),
    })
    await expect(duringDialog.controller.chooseExcelInput(event, projectId)).resolves.toMatchObject({ ok: false, error: { code: 'SERVICE_CHANGED' } })
    expect(duringDialog.dependencies.register).not.toHaveBeenCalled()

    current = host
    const duringRegistration = await setup({ getHostStatus: () => current })
    duringRegistration.dependencies.register = vi.fn(async () => { current = { ...host, baseUrl: 'http://127.0.0.1:43128' } })
    duringRegistration.controller = new ProjectFilesController(duringRegistration.dependencies)
    await expect(duringRegistration.controller.chooseExcelInput(event, projectId)).resolves.toMatchObject({ ok: false, error: { code: 'SERVICE_CHANGED' } })
  })

  it('rejects wrong extensions, symlinks, and existing output targets', async () => {
    const root = await mkdtemp(join(tmpdir(), 'autoflow-project-files-invalid-'))
    const csv = join(root, 'input.csv'); await writeFile(csv, 'csv')
    const real = join(root, 'real.xlsx'); await writeFile(real, 'xlsx')
    const link = join(root, 'link.xlsx'); await symlink(real, link)
    const existing = join(root, 'existing.xlsx'); await writeFile(existing, 'old')
    const nested = join(root, 'nested'); await mkdir(nested)
    for (const path of [csv, link]) {
      const context = await setup({ showOpenDialog: vi.fn(async () => ({ canceled: false, filePaths: [path] })) })
      await expect(context.controller.chooseExcelInput(event, projectId)).resolves.toMatchObject({ ok: false })
      expect(context.dependencies.register).not.toHaveBeenCalled()
    }
    const output = await setup({ showSaveDialog: vi.fn(async () => ({ canceled: false, filePath: existing })) })
    await expect(output.controller.chooseXlsxOutput(event, projectId, '../unsafe.xls')).resolves.toMatchObject({ ok: false, error: { code: 'INVALID_SUGGESTED_NAME' } })
    await expect(output.controller.chooseXlsxOutput(event, projectId, 'result.xlsx')).resolves.toMatchObject({ ok: false, error: { code: 'OUTPUT_ALREADY_EXISTS' } })
  })

  it('exposes one stable proof only to the registered main frame on the same host', async () => {
    let current = host
    const context = await setup({ getHostStatus: () => current })
    await expect(context.controller.getProjectFileContext(event)).resolves.toEqual({ ok: true, value: null })
    await context.controller.chooseExcelInput(event, projectId)
    const first = await context.controller.getProjectFileContext(event)
    const second = await context.controller.getProjectFileContext(event)
    expect(first).toEqual(second)
    expect(first).toEqual({ ok: true, value: { windowId: 7, windowToken: expect.any(String) } })
    expect((first as { ok: true; value: { windowToken: string } }).value.windowToken).not.toBe('4cc4bd80-8f6a-48a7-a989-748e43a45389')
    expect(context.dependencies.register).toHaveBeenCalledWith(host, expect.any(Object), (first as { ok: true; value: { windowToken: string } }).value.windowToken)

    await expect(context.controller.getProjectFileContext({ ...event, sender: { ...event.sender, id: 8 } })).resolves.toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
    current = { ...host, hostToken: 'replacement-host' }
    await expect(context.controller.getProjectFileContext(event)).resolves.toEqual({ ok: true, value: null })
  })
})
