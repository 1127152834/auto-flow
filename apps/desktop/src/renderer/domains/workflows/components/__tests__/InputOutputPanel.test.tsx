import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { findInternalIds } from '../../../../shared/testing/internal-id-scan'

const request = vi.hoisted(() => vi.fn())
const context = vi.hoisted(() => ({ projectId: undefined as string | undefined }))
vi.mock('../../api', async importOriginal => ({ ...(await importOriginal<typeof import('../../api')>()), apiRequest: request }))
vi.mock('../../api/config', async importOriginal => ({ ...(await importOriginal<typeof import('../../api/config')>()), getStudioOpenContext: () => ({ projectId: context.projectId }) }))
import { InputOutputPanel } from '../InputOutputPanel'
import { useSignatureStore } from '../../hooks/stores/signatureStore'
import { useWorkflowStore } from '../../editor-store'

const stored = (overrides: Record<string, unknown> = {}) => ({
  inputs: [{ key: 'account', name: '账号', fields: [
    { key: 'phone', name: '手机号', type: 'string', required: true, sensitive: false, sample: '13800000000' },
    { key: 'password', name: '密码', type: 'string', required: true, sensitive: true },
  ] }], ...overrides,
})
const open = (onOpenChange = vi.fn()) => { render(<InputOutputPanel open onOpenChange={onOpenChange} />); return onOpenChange }
const field = (name: string) => screen.getByRole('group', { name: `字段 ${name}` })
const state = () => useSignatureStore.getState()

beforeEach(() => { request.mockReset(); context.projectId = undefined; useSignatureStore.getState().reset(); useWorkflowStore.getState().clearWorkflow() })
afterEach(cleanup)

describe('输入与输出面板', () => {
  it('lists fields with name, type, required, sensitive and sample', () => {
    state().load(stored())
    open()
    const phone = field('手机号')
    expect((within(phone).getByLabelText('中文名') as HTMLInputElement).value).toBe('手机号')
    expect((within(phone).getByLabelText('类型') as HTMLSelectElement).value).toBe('string')
    expect((within(phone).getByLabelText('必填') as HTMLInputElement).checked).toBe(true)
    expect((within(phone).getByLabelText('样例值') as HTMLInputElement).value).toBe('13800000000')
  })

  it('adds a group and a field, suggesting the key from the Chinese name', () => {
    open()
    fireEvent.click(screen.getByRole('button', { name: '新增分组' }))
    fireEvent.change(screen.getByLabelText('分组名称'), { target: { value: '账号' } })
    fireEvent.blur(screen.getByLabelText('分组名称'))
    fireEvent.click(screen.getByRole('button', { name: '新增字段' }))
    const row = field('字段1')
    fireEvent.change(within(row).getByLabelText('中文名'), { target: { value: '手机号' } })
    fireEvent.blur(within(row).getByLabelText('中文名'))
    expect(state().inputs[0]).toMatchObject({ key: 'zhanghao', name: '账号' })
    expect(state().inputs[0].fields[0]).toMatchObject({ key: 'shoujihao', name: '手机号', type: 'string' })
    expect(state().dirty).toBe(true)
  })

  it('keeps the key of a saved field when it is renamed', () => {
    state().load(stored())
    open()
    const phone = field('手机号')
    fireEvent.change(within(phone).getByLabelText('中文名'), { target: { value: '电话' } })
    fireEvent.blur(within(phone).getByLabelText('中文名'))
    expect(state().inputs[0].fields[0]).toMatchObject({ key: 'phone', name: '电话' })
  })

  it('shows the key only under 高级 and reports duplicates in place', () => {
    state().load(stored())
    open()
    const phone = field('手机号')
    expect(within(phone).getByText('高级').closest('details')!.open).toBe(false)
    fireEvent.change(within(phone).getByLabelText('字段标识'), { target: { value: 'password' } })
    expect(within(field('密码')).getByRole('alert').textContent).toContain('重复')
    expect(state().canSave).toBe(false)
  })

  it('validates a sample against the field type and clears it when the type changes', () => {
    state().load(stored())
    open()
    const phone = field('手机号')
    fireEvent.change(within(phone).getByLabelText('类型'), { target: { value: 'number' } })
    expect(state().inputs[0].fields[0].sample).toBeUndefined()
    fireEvent.change(within(phone).getByLabelText('样例值'), { target: { value: '12' } })
    expect(state().inputs[0].fields[0].sample).toBe(12)
    expect(state().canSave).toBe(true)
  })

  it('disables the sample of a sensitive field and says why', () => {
    state().load(stored())
    open()
    const password = field('密码')
    const sample = within(password).getByLabelText('样例值') as HTMLInputElement
    expect(sample.disabled).toBe(true)
    expect(within(password).getByText('敏感字段不保存样例')).toBeTruthy()
    const phone = field('手机号')
    fireEvent.click(within(phone).getByLabelText('敏感'))
    expect((within(phone).getByLabelText('样例值') as HTMLInputElement).disabled).toBe(true)
    expect(state().inputs[0].fields[0].sample).toBeUndefined()
  })

  it('deletes fields and groups', () => {
    state().load(stored())
    open()
    fireEvent.click(screen.getByRole('button', { name: '删除字段 密码' }))
    expect(state().inputs[0].fields.map(item => item.key)).toEqual(['phone'])
    fireEvent.click(screen.getByRole('button', { name: '删除分组 账号' }))
    expect(state().inputs).toEqual([])
  })

  it('is read-only and lists the problems when the stored signature is unusable', () => {
    state().load({ inputs: [{ key: '1坏', name: '坏的', fields: [] }] })
    open()
    expect(screen.getByText(/暂时只能查看/)).toBeTruthy()
    expect(screen.getAllByText(/流程输入标识只能包含/).length).toBeGreaterThan(0)
    expect((screen.getByRole('button', { name: '新增分组' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByLabelText('分组名称').matches(':disabled')).toBe(true)
    expect(state().dirty).toBe(false)
  })

  it('is read-only when the service reported problems with the stored signature', async () => {
    state().load(stored())
    await state().refreshIssues('wf', async () => ({ success: true, data: { signatureIssues: [{ path: 'signature.inputs.0', message: '服务端发现输入重名' }] } }))
    open()
    expect(screen.getByText('服务端发现输入重名')).toBeTruthy()
    expect(within(field('手机号')).getByLabelText('中文名').matches(':disabled')).toBe(true)
  })

  it('shows outputs read-only from the End and write-back nodes', () => {
    useWorkflowStore.setState({ nodes: [
      { id: 'n1', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'project_end', label: '结束', businessResult: 'succeeded' } },
      { id: 'n2', type: 'moduleNode', position: { x: 0, y: 0 }, data: { moduleType: 'project_data', label: '回写状态', operation: 'setRecordStatus' } },
    ] as never })
    open()
    expect(screen.getByText('输出由节点自动产生，在节点里配置。')).toBeTruthy()
    const list = screen.getByRole('list', { name: '流程输出' })
    expect(within(list).getByText('业务结果：成功')).toBeTruthy()
    expect(within(list).getByText('设置记录状态')).toBeTruthy()
    expect(within(list).queryByRole('textbox')).toBeNull()
  })

  it('is a keyboard-reachable dialog that closes with Escape and moves focus inside', async () => {
    state().load(stored())
    const onOpenChange = open()
    const dialog = screen.getByRole('dialog', { name: '输入与输出' })
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))
    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('renders no internal identifiers', () => {
    state().load(stored())
    context.projectId = 'project-1'
    open()
    expect(findInternalIds(document.body)).toEqual([])
  })
})

describe('键的编辑', () => {
  it('edits the second field when two fields share a key', () => {
    state().load(stored())
    open()
    fireEvent.change(within(field('手机号')).getByLabelText('字段标识'), { target: { value: 'password' } })
    fireEvent.change(within(field('密码')).getByLabelText('中文名'), { target: { value: '口令' } })
    expect(state().inputs[0].fields.map(item => item.name)).toEqual(['手机号', '口令'])
    fireEvent.click(screen.getByRole('button', { name: '删除字段 口令' }))
    expect(state().inputs[0].fields.map(item => item.name)).toEqual(['手机号'])
  })

  it('keeps a key set under 高级 when the name is edited afterwards', () => {
    open()
    fireEvent.click(screen.getByRole('button', { name: '新增分组' }))
    fireEvent.click(screen.getByRole('button', { name: '新增字段' }))
    const row = field('字段1')
    fireEvent.change(within(row).getByLabelText('字段标识'), { target: { value: 'field7' } })
    fireEvent.change(within(row).getByLabelText('中文名'), { target: { value: '手机号' } })
    fireEvent.blur(within(row).getByLabelText('中文名'))
    expect(state().inputs[0].fields[0].key).toBe('field7')
  })
})

describe('从数据表导入', () => {
  const table = { tableId: 'tbl-1', name: '客户表' }
  const tableFields = [
    { key: 'phone', name: '手机号', type: 'string', required: true },
    { key: 'age', name: '年龄', type: 'number', required: false },
  ]
  beforeEach(() => {
    context.projectId = 'project-1'
    request.mockImplementation(async (path: string) => path.includes('/fields') ? { success: true, data: { items: tableFields } } : { success: true, data: { items: [table] } })
  })

  it('is hidden without a project context', () => {
    context.projectId = undefined
    open()
    expect(screen.queryByRole('button', { name: '从数据表导入' })).toBeNull()
  })

  it('previews fields, skips ones that already exist and imports the checked ones', async () => {
    state().load(stored())
    open()
    fireEvent.click(screen.getByRole('button', { name: '从数据表导入' }))
    fireEvent.change(await screen.findByLabelText('数据表'), { target: { value: 'tbl-1' } })
    const list = await screen.findByRole('list', { name: '可导入的字段' })
    const phone = within(list).getByLabelText(/手机号/) as HTMLInputElement
    expect(phone.disabled).toBe(true)
    expect(within(list).getByText(/已存在，不重复导入/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '导入所选字段' }))
    expect(state().inputs[0].fields.map(item => [item.key, item.type])).toEqual([['phone', 'string'], ['password', 'string'], ['age', 'number']])
  })

  it('imports into a new group named after the table', async () => {
    open()
    fireEvent.click(screen.getByRole('button', { name: '从数据表导入' }))
    fireEvent.change(await screen.findByLabelText('数据表'), { target: { value: 'tbl-1' } })
    await screen.findByRole('list', { name: '可导入的字段' })
    fireEvent.click(screen.getByRole('button', { name: '导入所选字段' }))
    expect(state().inputs).toHaveLength(1)
    expect(state().inputs[0].name).toBe('客户表')
    expect(state().inputs[0].fields.map(item => item.key)).toEqual(['phone', 'age'])
  })

  it('reads every page of data tables', async () => {
    const page = (n: number) => Array.from({ length: n === 3 ? 5 : 100 }, (_, i) => ({ tableId: `t${n}-${i}`, name: `表${n}-${i}` }))
    request.mockImplementation(async (path: string) => {
      const n = Number(/page=(\d+)/.exec(path)![1])
      return { success: true, data: { items: page(n), total: 205, page: n, pageSize: 100 } }
    })
    open()
    fireEvent.click(screen.getByRole('button', { name: '从数据表导入' }))
    await screen.findByLabelText('数据表')
    await waitFor(() => expect(screen.getByLabelText('数据表').querySelectorAll('option')).toHaveLength(206))
  })

  it('imports into a new group when the chosen group was deleted meanwhile', async () => {
    state().load(stored())
    open()
    fireEvent.click(screen.getByRole('button', { name: '从数据表导入' }))
    fireEvent.change(await screen.findByLabelText('数据表'), { target: { value: 'tbl-1' } })
    await screen.findByRole('list', { name: '可导入的字段' })
    act(() => state().removeInputAt(0))
    fireEvent.click(screen.getByRole('button', { name: '导入所选字段' }))
    expect(state().inputs).toHaveLength(1)
    expect(state().inputs[0].fields.map(item => item.key)).toEqual(['phone', 'age'])
  })

  it('shows why reading the tables failed and what to do', async () => {
    request.mockResolvedValue({ success: false, error: '连接被拒绝' })
    open()
    fireEvent.click(screen.getByRole('button', { name: '从数据表导入' }))
    expect((await screen.findByRole('alert')).textContent).toContain('连接被拒绝')
    expect(screen.getByRole('alert').textContent).toContain('请检查项目是否可访问后重试')
  })
})
