import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { chooseOption, choiceTestEnvironment } from '../../../shared/testing/choice-user'

choiceTestEnvironment()
import { createProxyApi, type ProxyView } from '../api'
import type { ApiClient } from '../../../shared/api/client'
import { ProxyRemoteControls } from '../components/ProxyRemoteControls'
import { RotationScheduleForm } from '../components/RotationScheduleForm'
import { LocationPicker } from '../components/LocationPicker'

afterEach(cleanup)
const proxy = {id:'proxy-1', connection_id:'connection-1', revision:7} as ProxyView
const noop = () => undefined

function fixture(status = 'queued') {
  const operation = {id:'op-1', target_id:proxy.id, kind:'change_ip', status, created_at:'2026-09-12T00:00:00Z', updated_at:'2026-09-12T00:00:00Z', error:null}
  const request = vi.fn(async (path:string, init?:RequestInit) => {
    if (path.endsWith('/remote-state')) return {city:'Dallas',current_ip:'192.0.2.1', fetched_at:'2026-09-12T00:00:00Z', capabilities:[{key:'change_ip',available:true},{key:'relocate',available:true},{key:'rotation_schedule',available:true}]}
    if (path.endsWith('/rotation-schedule')) return {enabled:false, mode:null, interval_minutes:null}
    if (path.endsWith('/operation')) return status === 'unknown' ? operation : null
    if (path.endsWith('/change-ip')) return {status:'accepted',operation_id:'op-1'}
    if (path.endsWith('/proxy-operations/op-1')) return operation
    if (path.endsWith('/reconcile')) return {...operation,status:'running'}
    if (path.endsWith('/acknowledge')) return {...operation,status:'failed'}
    throw new Error(`Unexpected ${init?.method} ${path}`)
  })
  const api = createProxyApi({request} as unknown as ApiClient)
  const changed = vi.fn(async () => undefined)
  render(<ProxyRemoteControls api={api} proxy={proxy} onChanged={changed} onDirtyChange={noop} onSubmittingChange={noop} />)
  return {request, operation, changed}
}

it('edits schedule locally and submits only on explicit save with official units', async () => {
  const user = userEvent.setup(), save = vi.fn(), dirty = vi.fn()
  render(<RotationScheduleForm value={{enabled:false, mode:null, interval_minutes:null}} disabled={false} canSave onDirtyChange={dirty} onSave={save} onClear={noop} />)
  await chooseOption(user, screen.getByLabelText('轮换模式'), 'same_city_carriers')
  await chooseOption(user, screen.getByLabelText('轮换周期'), '30')
  expect(save).not.toHaveBeenCalled()
  expect(dirty).toHaveBeenLastCalledWith(true)
  await user.click(screen.getByRole('button', {name:'开启轮换计划'}))
  expect(save).toHaveBeenCalledWith({enabled:true, mode:'same_city_carriers', interval_minutes:30})
})

it('groups location aliases and cannot submit a zero-capacity target', async () => {
  const user = userEvent.setup(), select = vi.fn()
  render(<LocationPicker locations={{items:[{id:'shared',city:'Arcadia / Aliso Viejo',cities:['Arcadia','Aliso Viejo'],country:'US',carrier:'T-Mobile',availability:'available',available_slots:2},{id:'empty',city:'Dallas',availability:'unavailable',available_slots:0}],stale:false}} loading={false} busy={false} onClose={noop} onReload={noop} onSelect={select} />)
  const radios = screen.getAllByRole('radio')
  expect(radios[1]).toBeDisabled()
  expect(screen.getByRole('button',{name:'下一步'})).toBeDisabled()
  await user.type(screen.getByLabelText('搜索地点'),'Aliso Viejo')
  await user.click(screen.getByRole('radio'))
  await user.click(screen.getByRole('button',{name:'下一步'}))
  expect(select).toHaveBeenCalledWith('shared')
  expect(screen.getByText('查看共用目标的覆盖城市')).toBeInTheDocument()
})

it('requires confirmation and polls accepted commands without reporting success early', async () => {
  const user = userEvent.setup(), {request,operation,changed} = fixture()
  await waitFor(() => expect(screen.getByRole('button',{name:'更换 IP'})).toBeEnabled())
  await user.click(screen.getByRole('button',{name:'更换 IP'}))
  expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'取消'})).toHaveFocus()
  expect(request.mock.calls.filter(([path]) => path.endsWith('/change-ip'))).toHaveLength(0)
  await user.click(screen.getByRole('button',{name:'确认'}))
  await screen.findByText('操作已受理，正在等待远程结果…')
  expect(changed).not.toHaveBeenCalled()
  expect(screen.getByRole('button',{name:'更换 IP'})).toBeDisabled()
  const writes = request.mock.calls.filter(([path]) => path.endsWith('/change-ip'))
  expect(writes).toHaveLength(1)
  expect(JSON.parse(writes[0][1]!.body as string)).toEqual({expected_revision:7})
  expect((writes[0][1]!.headers as Record<string,string>)['Idempotency-Key']).toBeTruthy()
  operation.status = 'succeeded'
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1),{timeout:2500})
})

it('recovers unknown operation on open and offers read-only reconciliation', async () => {
  const user = userEvent.setup(), {request} = fixture('unknown')
  await screen.findByText('结果尚未确认')
  expect(screen.getByRole('button',{name:'更换 IP'})).toBeDisabled()
  await user.click(screen.getByRole('button',{name:'重新核实'}))
  await screen.findByText('操作已受理，正在等待远程结果…')
  expect(request.mock.calls.filter(([path]) => path.endsWith('/change-ip'))).toHaveLength(0)
  expect(request.mock.calls.filter(([path]) => path.endsWith('/reconcile'))).toHaveLength(1)
})
