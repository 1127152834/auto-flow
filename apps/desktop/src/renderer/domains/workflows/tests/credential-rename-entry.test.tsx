import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const storage = vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  return data
})
import { GlobalConfigDialog } from '../components/GlobalConfigDialog'
import { credentialApi } from '../api'
import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'
let restore: () => void
let failRename: boolean
let loseFieldsResponse: boolean
let writes: Array<{ path: string; body: unknown }>
beforeEach(async () => {
  storage.clear(); writes = []; failRename = false; loseFieldsResponse = false
  restore = configureStudioConnection('http://autoflow-studio.mock', async (input, init) => {
    const path = new URL(input instanceof Request ? input.url : String(input)).pathname
    if (init?.method === 'POST' && path.startsWith('/api/credentials')) writes.push({ path, body: JSON.parse(String(init.body)) })
    if (path.endsWith('/credentials/rename') && failRename) return Response.json({ success: false, error: '改名暂不可用' }, { status: 503 })
    const response = await mockRequest(input, init)
    if (path.endsWith('/credentials/fields') && loseFieldsResponse) { loseFieldsResponse = false; throw new TypeError('Failed to fetch') }
    return response
  })
  await credentialApi.upsert('旧凭据', { value: 'dummy-secret', password: 'dummy-password' }, '保留说明')
  writes = []
})
afterEach(() => { cleanup(); restore() })
async function open() {
  render(<GlobalConfigDialog isOpen onClose={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: '凭据库' }))
  await screen.findByText('旧凭据', { exact: true })
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name: new RegExp(`^${name}$`) }))
const name = (value: string) => fireEvent.change(screen.getByPlaceholderText('如：我的邮箱'), { target: { value } })
const records = async () => (await credentialApi.list()).data!.credentials

it('renames through the actual settings entry using one command and preserves metadata after reopening', async () => {
  const original = (await records())[0]
  await open(); click('改名'); name('新凭据')
  expect(screen.getByText(/已有工作流引用不会自动更新/)).toBeTruthy()
  expect(screen.queryByPlaceholderText('值')).toBeNull()
  click('保存')
  await screen.findByText('新凭据', { exact: true })
  expect(writes).toEqual([{ path: '/api/credentials/rename', body: { old_name: '旧凭据', new_name: '新凭据' } }])
  expect(await records()).toEqual([{ ...original, name: '新凭据', revision: (original.revision ?? 1) + 1 }])
  click('系统'); await screen.findByText('配置系统相关的全局设置'); click('凭据库')
  await screen.findByText('新凭据', { exact: true }); click('编辑')
  expect(screen.getByPlaceholderText('如：我的邮箱')).toHaveProperty('readOnly', true)
  expect(screen.getByPlaceholderText('用途备注')).toHaveProperty('value', '保留说明')
  expect(screen.getAllByPlaceholderText('值').map(input => (input as HTMLInputElement).value)).toEqual(['', ''])
  expect([...storage.values()].join('')).not.toMatch(/dummy-secret|dummy-password/)
})

it('cancels a rename without writes and protects rename drafts on leaving the settings tab', async () => {
  await open(); click('改名'); name('取消名称'); click('取消')
  expect(writes).toEqual([])
  click('改名'); name('未提交名称'); click('系统')
  const dialog = await screen.findByRole('dialog', { name: '保存凭据编辑？' })
  fireEvent.click(within(dialog).getByRole('button', { name: '取消' }))
  expect(screen.getByPlaceholderText('如：我的邮箱')).toHaveProperty('value', '未提交名称')
  expect(writes).toEqual([])
  expect((await records()).map(record => record.name)).toEqual(['旧凭据'])
})

it('retains the rename input after failure and retries without upserting or deleting either record', async () => {
  await open(); click('改名'); name('新凭据'); failRename = true; click('保存')
  await screen.findByText(/保存失败：.*改名暂不可用/)
  expect(screen.getByPlaceholderText('如：我的邮箱')).toHaveProperty('value', '新凭据')
  expect((await records()).map(record => record.name)).toEqual(['旧凭据'])
  click('确定'); await waitFor(() => expect(screen.getByRole('button', { name: /^保存$/ })).toHaveProperty('disabled', false)); failRename = false; click('保存')
  await screen.findByText('新凭据', { exact: true })
  expect(writes.map(write => write.path)).toEqual(['/api/credentials/rename', '/api/credentials/rename'])
})

it('reports a rename conflict and preserves both existing credentials', async () => {
  await credentialApi.upsert('已存在', { token: '' }); writes = []
  const before = await records()
  await open()
  fireEvent.click(screen.getAllByRole('button', { name: /^改名$/ })[0])
  name('已存在'); click('保存')
  await screen.findByText(/保存失败：.*凭据名称已存在/)
  expect(await records()).toEqual(before)
})

it('explains reference naming without changing legacy names and does not claim merged fields can be removed', async () => {
  await credentialApi.rename('旧凭据', '旧.名称')
  render(<GlobalConfigDialog isOpen onClose={() => {}} />); click('凭据库')
  await screen.findByText('旧.名称', { exact: true })
  expect(screen.getByText(/引用按第一个点分隔/)).toBeTruthy()
  click('编辑')
  expect(screen.getByPlaceholderText('如：我的邮箱')).toHaveProperty('value', '旧.名称')
  expect(screen.getByRole('button', { name: '删除字段 value' })).toHaveProperty('disabled', true)
  expect(screen.getAllByPlaceholderText('字段名 如 value/password/api_key')[0]).toHaveProperty('readOnly', true)
  click('添加字段')
  const fields = screen.getAllByPlaceholderText('字段名 如 value/password/api_key')
  fireEvent.change(fields[2], { target: { value: 'temporary' } })
  click('删除字段 temporary')
  expect(screen.getAllByPlaceholderText('字段名 如 value/password/api_key')).toHaveLength(2)
  click('保存')
  await waitFor(() => expect(screen.queryByPlaceholderText('如：我的邮箱')).toBeNull())
  expect((await records())[0]).toMatchObject({ name: '旧.名称', fields: [{ key: 'value' }, { key: 'password' }] })
})

it('atomically renames and removes existing fields through the real settings entry and reopens masked metadata', async () => {
  await open(); click('管理字段')
  const keys=screen.getAllByPlaceholderText('字段名 如 value/password/api_key')
  fireEvent.change(keys[1],{target:{value:'api_key'}})
  click('删除字段 value')
  click('保存')
  await screen.findByText('api_key: •••••• (Mock)')
  const changes=writes.filter(write=>write.path==='/api/credentials/fields')
  expect(changes).toHaveLength(1)
  expect(changes[0].body).toMatchObject({name:'旧凭据',expectedRevision:1,operations:[{kind:'remove',key:'value'},{kind:'rename',key:'password',newKey:'api_key'}]})
  expect(JSON.stringify(changes[0].body)).not.toMatch(/dummy|masked/)
  click('系统');await screen.findByText('配置系统相关的全局设置');click('凭据库')
  await screen.findByText('旧凭据',{exact:true});click('管理字段')
  expect(screen.getAllByPlaceholderText('字段名 如 value/password/api_key')).toHaveLength(1)
  expect(screen.getByPlaceholderText('字段名 如 value/password/api_key')).toHaveProperty('value','api_key')
  expect(screen.queryByPlaceholderText('值')).toBeNull()
  expect(screen.getByText('•••••• (Mock)',{exact:true})).toBeTruthy()
})

it('cancels field edits without a command and rejects removal of the last field before sending', async () => {
  await open();click('管理字段');click('删除字段 value');click('取消')
  expect(writes).toEqual([])
  expect((await records())[0].fields).toHaveLength(2)
  click('管理字段');click('删除字段 value');click('删除字段 password');click('保存')
  await screen.findByText('至少需要一个字段')
  expect(writes).toEqual([])
})

it('preserves a stale field draft on revision conflict and can cancel/reopen the current metadata', async () => {
  await open();click('管理字段');click('删除字段 value')
  await credentialApi.upsert('旧凭据',{concurrent:'dummy-later'})
  click('保存')
  await screen.findByText(/字段修改未确认：.*凭据已被修改/)
  expect(screen.getByPlaceholderText('字段名 如 value/password/api_key')).toHaveProperty('value','password')
  click('确定');await waitFor(()=>expect(screen.getByRole('button',{name:/^取消$/})).toHaveProperty('disabled',false));click('取消')
  click('刷新凭据');await screen.findByText('concurrent: •••••• (Mock)')
  click('管理字段');expect(screen.getAllByPlaceholderText('字段名 如 value/password/api_key')).toHaveLength(3)
})

it('retries a committed field command with the same ID after its response is lost', async () => {
  await open();click('管理字段');click('删除字段 value')
  loseFieldsResponse=true;click('保存')
  await screen.findByText(/字段修改未确认/)
  expect((await records())[0].fields.map(field=>field.key)).toEqual(['password'])
  click('确定');await waitFor(()=>expect(screen.getByRole('button',{name:/^保存$/})).toHaveProperty('disabled',false))
  expect(screen.getByRole('button',{name:/^取消$/})).toHaveProperty('disabled',true)
  expect(screen.getByPlaceholderText('字段名 如 value/password/api_key')).toHaveProperty('disabled',true)
  click('保存');await screen.findByText('password: •••••• (Mock)')
  const commands=writes.filter(write=>write.path==='/api/credentials/fields')
  expect(commands).toHaveLength(2);expect(commands[1].body).toEqual(commands[0].body)
  expect((await records())[0].revision).toBe(2)
})
