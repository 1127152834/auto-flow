import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ReactElement } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { DataTableDetailPage } from './DataTableDetailPage'

afterEach(cleanup)
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});HTMLElement.prototype.hasPointerCapture=()=>false;HTMLElement.prototype.setPointerCapture=()=>{};HTMLElement.prototype.releasePointerCapture=()=>{};HTMLElement.prototype.scrollIntoView=()=>{}})
const table={projectId:'p',tableId:'t',name:'客户表',description:'真实说明',sourceKind:'local' as const,datasetGeneration:'g',tableRevision:3,identity:{mode:'system' as const},slotDefinitions:[],recordCount:1,syncSummary:{status:'notApplicable' as const,pendingCount:0,unknownCount:0},createdAt:'2026-01-01T00:00:00Z',updatedAt:'2026-01-02T00:00:00Z'}
const field={ref:{projectId:'p',tableId:'t',datasetGeneration:'g',fieldId:'f'},key:'name',name:'姓名',type:'string' as const,required:true,validation:{},writable:true,formula:false,fieldRevision:2}
const status={statusId:'s',name:'进行中',color:'#123456',order:0,statusRevision:4}
const record={ref:{projectId:'p',tableId:'t',datasetGeneration:'g',recordKey:{type:'text' as const,value:'001'}},values:[{fieldId:'f',value:'Alice',source:'local' as const,readable:true,error:null}],recordSlots:[],statusId:'s',currentEnvironmentId:null,contentRevision:1,statusRevision:1,linkRevision:1,deleted:false,createdAt:'2026-01-01T00:00:00Z',updatedAt:'2026-01-01T00:00:00Z'}
const page={items:[record],total:1,page:1,pageSize:50,sort:'[]'}
function api() {
  const request=vi.fn(async (path:string)=>{
    if(path.endsWith('/tables/t'))return table
    if(path.includes('/fields'))return {items:[field],tableRevision:3}
    if(path.includes('/statuses'))return {items:[status],tableRevision:3}
    if(path.includes('/records/'))return record
    if(path.includes('/records?'))return page
    throw new Error(path)
  })
  return {client:{request:request as StreamingApiClient['request'],health:vi.fn(),stream:vi.fn()} as StreamingApiClient,request}
}
const props=(client:StreamingApiClient,overrides:Partial<Parameters<typeof DataTableDetailPage>[0]>={})=>({workspaceKey:'w',instanceId:'i',projectId:'p',tableId:'t',tab:'records' as const,client,readonly:false,disabled:false,onBack:vi.fn(),onTabChange:vi.fn(),registerLeaveGuard:vi.fn(),...overrides})
const renderPage=(page:ReactElement)=>{const queryClient=new QueryClient({defaultOptions:{queries:{retry:false}}});const view=render(<QueryClientProvider client={queryClient}>{page}</QueryClientProvider>);return {...view,queryClient,rerender:(next:ReactElement)=>view.rerender(<QueryClientProvider client={queryClient}>{next}</QueryClientProvider>)} }

it('loads the real table, generation catalog and server record page',async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client)}/>)
  expect(await screen.findByRole('heading',{name:'客户表'})).toBeVisible();expect(await screen.findByText('Alice')).toBeVisible()
  expect(request.mock.calls.some(([path])=>String(path).includes('datasetGeneration=g'))).toBe(true)
  expect(screen.queryByRole('button',{name:/新增|编辑|删除/})).not.toBeInTheDocument()
})

it('applies filter JSON only after explicit apply and paginates on the server',async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice');const before=request.mock.calls.length
  await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}));expect(request).toHaveBeenCalledTimes(before)
  await userEvent.click(screen.getByLabelText('比较值值状态'));await userEvent.click(screen.getByRole('option',{name:'填写值'}));await userEvent.type(screen.getByLabelText('比较值'),'Ali');await userEvent.click(screen.getByRole('button',{name:'应用筛选'}))
  await waitFor(()=>expect(request.mock.calls.length).toBeGreaterThan(before));const url=String(request.mock.calls.at(-1)?.[0]);expect(url).toContain('filter=');expect(url).not.toContain('filter=eyJmaWx0ZXIi')
})

it('renders factual field, status, source and settings tabs',async()=>{
  const {client}=api(),onTabChange=vi.fn();const view=renderPage(<DataTableDetailPage {...props(client,{tab:'fields',onTabChange})}/>);expect(await screen.findByText('姓名')).toBeVisible();expect(screen.getByText(/必填/)).toBeVisible()
  view.rerender(<DataTableDetailPage {...props(client,{tab:'statuses',onTabChange})}/>);expect(await screen.findByText('进行中')).toBeVisible();expect(screen.getByText(/修订 4/)).toBeVisible()
  view.rerender(<DataTableDetailPage {...props(client,{tab:'source',onTabChange})}/>);expect(await screen.findAllByText('本地数据')).toHaveLength(2);expect(screen.getByText(/不适用/)).toBeVisible()
  view.rerender(<DataTableDetailPage {...props(client,{tab:'settings',onTabChange})}/>);expect(await screen.findAllByText('真实说明')).toHaveLength(2);expect(screen.getByText(/表修订 3/)).toBeVisible()
})

it('loads a selected record through get and shows its readonly detail',async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await userEvent.click(await screen.findByRole('button',{name:/查看记录/}));expect(await screen.findByRole('dialog',{name:/记录详情/})).toBeVisible()
  expect(within(screen.getByRole('dialog',{name:/记录详情/})).getByText('Alice')).toBeVisible();expect(request.mock.calls.some(([path])=>String(path).includes('/records/MDAx?'))).toBe(true)
})

it('registers dirty leave protection and keeps the draft when navigation is cancelled',async()=>{
  const {client}=api(),register=vi.fn(),change=vi.fn();renderPage(<DataTableDetailPage {...props(client,{registerLeaveGuard:register,onTabChange:change})}/>);await screen.findByText('Alice');await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}))
  const guard=register.mock.calls.map(call=>call[0]).find(value=>typeof value==='function');expect(guard).toBeTypeOf('function');const result=guard()
  expect(await screen.findByRole('alertdialog')).toBeVisible();await userEvent.click(screen.getByRole('button',{name:'继续编辑'}));expect(await result).toBe(false)
  expect(screen.getByText('字段条件')).toBeVisible();expect(change).not.toHaveBeenCalled()
})

it('keeps a dirty filter across reconnect and blocks a changed generation until discard',async()=>{
  let currentTable=table
  const {client}=api(),request=vi.mocked(client.request)
  request.mockImplementation(async(path:string)=>{
    if(path.endsWith('/tables/t'))return currentTable
    if(path.includes('/fields'))return {items:[field],tableRevision:3}
    if(path.includes('/statuses'))return {items:[status],tableRevision:3}
    if(path.includes('/records?'))return page
    throw new Error(path)
  })
  const register=vi.fn(),view=renderPage(<DataTableDetailPage {...props(client,{registerLeaveGuard:register})}/>)
  await screen.findByText('Alice');await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}))
  currentTable={...table,datasetGeneration:'g2'}
  view.rerender(<DataTableDetailPage {...props(client,{instanceId:'i2',registerLeaveGuard:register})}/>)
  expect(await screen.findByText(/数据代次已变化/)).toBeVisible();expect(screen.getByText('字段条件')).toBeVisible()
  await userEvent.click(screen.getByRole('button',{name:'处理草稿并载入新代次'}));await userEvent.click(await screen.findByRole('button',{name:'放弃并离开'}))
  await waitFor(()=>expect(request.mock.calls.some(([path])=>String(path).includes('datasetGeneration=g2'))).toBe(true))
  expect(view.queryClient.getQueryCache().getAll().some(item=>item.queryKey.includes('i2')&&item.queryKey.includes('g2'))).toBe(true)
})

it('does not reopen the same typed key against a replacement generation',async()=>{
  let currentTable=table
  const {client}=api(),request=vi.mocked(client.request)
  request.mockImplementation(async(path:string)=>{
    if(path.endsWith('/tables/t'))return currentTable
    if(path.includes('/fields'))return {items:[field],tableRevision:3}
    if(path.includes('/statuses'))return {items:[status],tableRevision:3}
    if(path.includes('/records/'))return record
    if(path.includes('/records?'))return page
    throw new Error(path)
  })
  const view=renderPage(<DataTableDetailPage {...props(client)}/>)
  await userEvent.click(await screen.findByRole('button',{name:/查看记录/}));await screen.findByRole('dialog',{name:/记录详情/})
  request.mockClear();currentTable={...table,datasetGeneration:'g2'}
  view.rerender(<DataTableDetailPage {...props(client,{instanceId:'i2'})}/>)
  await waitFor(()=>expect(screen.queryByRole('dialog',{name:/记录详情/})).not.toBeInTheDocument())
  expect(request.mock.calls.some(([path])=>String(path).includes('/records/')&&String(path).includes('datasetGeneration=g2'))).toBe(false)
})

it('keeps one pending leave approval and rejects a concurrent guard call',async()=>{
  const {client}=api(),register=vi.fn();renderPage(<DataTableDetailPage {...props(client,{registerLeaveGuard:register})}/>)
  await screen.findByText('Alice');await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}))
  const guard=register.mock.calls.map(call=>call[0]).find(value=>typeof value==='function')
  const first=guard(),second=guard();expect(await second).toBe(false)
  await userEvent.click(await screen.findByRole('button',{name:'继续编辑'}));expect(await first).toBe(false)
})

it('retries the failed catalog dependency from the records error action',async()=>{
  let fieldAttempts=0
  const {client}=api(),request=vi.mocked(client.request)
  request.mockImplementation(async(path:string)=>{
    if(path.endsWith('/tables/t'))return table
    if(path.includes('/fields')){fieldAttempts++;if(fieldAttempts===1)throw new Error('字段目录失败');return {items:[field],tableRevision:3}}
    if(path.includes('/statuses'))return {items:[status],tableRevision:3}
    if(path.includes('/records?'))return page
    throw new Error(path)
  })
  renderPage(<DataTableDetailPage {...props(client)}/>)
  await waitFor(()=>expect(screen.getAllByRole('alert').some(item=>item.textContent?.includes('字段目录失败'))).toBe(true));await userEvent.click(screen.getByRole('button',{name:'重试'}))
  await waitFor(()=>expect(fieldAttempts).toBe(2));expect(await screen.findByText('Alice')).toBeVisible()
})
