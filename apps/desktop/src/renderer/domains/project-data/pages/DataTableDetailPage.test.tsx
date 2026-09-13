import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ReactElement } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { ApiClientError } from '../../../shared/api/client'
import { DataTableDetailPage } from './DataTableDetailPage'

afterEach(cleanup)
beforeEach(()=>{const values=new Map<string,string>(),sessionValues=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)});vi.stubGlobal('sessionStorage',{getItem:(key:string)=>sessionValues.get(key)??null,setItem:(key:string,value:string)=>sessionValues.set(key,value),removeItem:(key:string)=>sessionValues.delete(key)});window.scrollTo=vi.fn();vi.stubGlobal('ResizeObserver',class{observe(){}unobserve(){}disconnect(){}});HTMLElement.prototype.hasPointerCapture=()=>false;HTMLElement.prototype.setPointerCapture=()=>{};HTMLElement.prototype.releasePointerCapture=()=>{};HTMLElement.prototype.scrollIntoView=()=>{}})
const table={projectId:'p',tableId:'t',name:'客户表',description:'真实说明',sourceKind:'local' as const,datasetGeneration:'g',tableRevision:3,identity:{mode:'system' as const},slotDefinitions:[],recordCount:1,syncSummary:{status:'notApplicable' as const,pendingCount:0,unknownCount:0},createdAt:'2026-01-01T00:00:00Z',updatedAt:'2026-01-02T00:00:00Z'}
const field={ref:{projectId:'p',tableId:'t',datasetGeneration:'g',fieldId:'f'},key:'name',name:'姓名',type:'string' as const,required:true,validation:{},writable:true,formula:false,fieldRevision:2}
const status={statusId:'s',name:'进行中',color:'#123456',order:0,statusRevision:4}
const record: import('../../../shared/api/generated').components['schemas']['DataRecordView']={ref:{projectId:'p',tableId:'t',datasetGeneration:'g',recordKey:{type:'text' as const,value:'001'}},values:[{fieldId:'f',value:'Alice',source:'local' as const,readable:true}],recordSlots:[],statusId:'s',currentEnvironmentId:null,contentRevision:1,statusRevision:1,linkRevision:1,deleted:false,createdAt:'2026-01-01T00:00:00Z',updatedAt:'2026-01-01T00:00:00Z'}
const page={items:[record],total:1,page:1,pageSize:50,sort:'[]'}
function api() {
  const request=vi.fn(async (path:string,_init?:{method?:string;body?:unknown})=>{
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
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client,{readonly:true})}/>)
  expect(await screen.findByRole('heading',{name:'客户表'})).toBeVisible();expect(await screen.findByText('Alice')).toBeVisible()
  expect(request.mock.calls.some(([path])=>String(path).includes('datasetGeneration=g'))).toBe(true)
  expect(screen.queryByRole('button',{name:/新增|编辑|删除/})).not.toBeInTheDocument()
})

it('creates an empty system record through the real command adapter',async()=>{
  const {client,request}=api()
  request.mockImplementation(async(path:string,init?:{method?:string;body?:unknown})=>{
    if(path.endsWith('/records')&&init?.method==='POST')return record
    if(path.endsWith('/tables/t'))return table
    if(path.endsWith('/fields'))return {items:[],tableRevision:3}
    if(path.endsWith('/statuses'))return {items:[],tableRevision:3}
    if(path.includes('/records?'))return {items:[],total:0,page:1,pageSize:50,sort:'[]'}
    throw new Error(path)
  })
  renderPage(<DataTableDetailPage {...props(client)}/>)
  await userEvent.click(await screen.findByRole('button',{name:'新增记录'}))
  await userEvent.click(screen.getByRole('button',{name:'创建记录'}))
  await waitFor(()=>expect(request.mock.calls.some(([path,init])=>String(path).endsWith('/records')&&init?.method==='POST')).toBe(true))
  const write=request.mock.calls.find(([path,init])=>String(path).endsWith('/records')&&init?.method==='POST')!
  expect(write[1]?.body).toEqual({datasetGeneration:'g',values:[]})
  expect(request.mock.calls.some(([path,init])=>String(path).endsWith('/status')&&init?.method==='PUT')).toBe(false)
})

it('applies filter JSON only after explicit apply and paginates on the server',async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice');const before=request.mock.calls.length
  await userEvent.click(screen.getByRole('button',{name:'筛选'}));await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}));expect(request).toHaveBeenCalledTimes(before)
  await userEvent.click(screen.getByLabelText('比较值值状态'));await userEvent.click(screen.getByRole('option',{name:'填写值'}));await userEvent.type(screen.getByLabelText('比较值'),'Ali');await userEvent.click(screen.getByRole('button',{name:'应用筛选'}))
  await waitFor(()=>expect(request.mock.calls.length).toBeGreaterThan(before));const url=String(request.mock.calls.at(-1)?.[0]);expect(url).toContain('filter=');expect(url).not.toContain('filter=eyJmaWx0ZXIi')
})

it('renders factual field, status, source and settings tabs',async()=>{
  const {client}=api(),onTabChange=vi.fn();const view=renderPage(<DataTableDetailPage {...props(client,{tab:'fields',onTabChange})}/>);expect(await screen.findByText('姓名')).toBeVisible();expect(screen.getByText(/必填/)).toBeVisible();expect(document.body.textContent).not.toContain('修订 2')
  view.rerender(<DataTableDetailPage {...props(client,{tab:'statuses',onTabChange})}/>);expect(await screen.findByText('进行中')).toBeVisible();expect(screen.getByText(/顺序 0/)).toBeVisible();expect(document.body.textContent).not.toContain('修订 4')
  view.rerender(<DataTableDetailPage {...props(client,{tab:'source',onTabChange})}/>);expect(await screen.findByText('手动维护')).toBeVisible();expect(screen.getByText(/直接在项目中维护/)).toBeVisible()
  view.rerender(<DataTableDetailPage {...props(client,{tab:'settings',onTabChange})}/>);expect(await screen.findAllByText('真实说明')).toHaveLength(2);expect(screen.getByRole('button',{name:'编辑数据表'})).toBeVisible();expect(document.body.textContent).not.toContain('数据代次')
})

it('loads a selected record through get and shows its readonly detail',async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await userEvent.click(await screen.findByRole('button',{name:/查看记录/}));expect(await screen.findByRole('dialog',{name:/记录详情/})).toBeVisible()
  expect(within(screen.getByRole('dialog',{name:/记录详情/})).getByText('Alice')).toBeVisible();expect(request.mock.calls.some(([path])=>String(path).includes('/records/MDAx?'))).toBe(true)
})

it('protects record drafts while query drafts remain local',async()=>{
  const {client}=api(),register=vi.fn();renderPage(<DataTableDetailPage {...props(client,{registerLeaveGuard:register})}/>);await screen.findByText('Alice')
  await userEvent.click(screen.getByRole('button',{name:'筛选'}));await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}))
  const guard=register.mock.calls.map(call=>call[0]).find(value=>typeof value==='function');expect(await guard()).toBe(true)
  await userEvent.keyboard('{Escape}')
  await userEvent.click(screen.getByRole('button',{name:'新增记录'}));await userEvent.click(screen.getByLabelText('姓名值状态'));await userEvent.click(screen.getByRole('option',{name:'填写值'}));await userEvent.type(screen.getByLabelText('姓名'),'保留草稿')
  const result=guard();await userEvent.click(await screen.findByRole('button',{name:'继续编辑'}));expect(await result).toBe(false)
  expect(screen.getByLabelText('姓名')).toHaveValue('保留草稿')
})

it('closes stale query drafts on a changed generation without applying them',async()=>{
  let currentTable=table
  const {client}=api(),request=vi.mocked(client.request)
  request.mockImplementation(async(path:string)=>{
    if(path.endsWith('/tables/t'))return currentTable
    if(path.includes('/fields'))return {items:[field],tableRevision:3}
    if(path.includes('/statuses'))return {items:[status],tableRevision:3}
    if(path.includes('/records?'))return page
    throw new Error(path)
  })
  const view=renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice')
  await userEvent.click(screen.getByRole('button',{name:'筛选'}));await userEvent.click(screen.getByRole('button',{name:'添加字段条件'}))
  currentTable={...table,datasetGeneration:'g2'};view.rerender(<DataTableDetailPage {...props(client,{instanceId:'i2'})}/>)
  await waitFor(()=>expect(screen.queryByText('字段条件')).not.toBeInTheDocument())
  expect(await screen.findByText('数据已更新，查询条件已重置。')).toBeVisible()
  await waitFor(()=>expect(request.mock.calls.some(([path])=>String(path).includes('datasetGeneration=g2'))).toBe(true))
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
  await screen.findByText('Alice');await userEvent.click(screen.getByRole('button',{name:'新增记录'}));await userEvent.click(screen.getByLabelText('姓名值状态'));await userEvent.click(screen.getByRole('option',{name:'填写值'}));await userEvent.type(screen.getByLabelText('姓名'),'草稿')
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

it('passes frozen record selection into the batch status workflow',async()=>{
  const {client}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice')
  await userEvent.click(screen.getByRole('checkbox',{name:'选择记录 文本 · 001'}));await userEvent.click(screen.getByRole('button',{name:'批量设置状态'}))
  expect(await screen.findByRole('dialog',{name:'批量设置业务状态'})).toHaveTextContent('已选择 1 条记录')
})

it('refreshes record facts when a batch partially applies before failing',async()=>{
  const {client}=api(),request=vi.mocked(client.request);let recordReads=0
  request.mockImplementation(async(path:string,init?:Parameters<StreamingApiClient['request']>[1])=>{
    if(path.endsWith('/tables/t'))return table;if(path.includes('/fields'))return {items:[field],tableRevision:3};if(path.includes('/statuses'))return {items:[status],tableRevision:3}
    if(path.includes('/records?')){recordReads++;return page}
    if(path.endsWith('/record-status-batches/preview'))return {request:init?.body,checkedAt:'',blocks:[]}
    if(path.endsWith('/record-status-batches')&&init?.method==='POST'){const key=new Headers(init.headers).get('Idempotency-Key');return {operation:{operationId:'partial',idempotencyKey:key,kind:'setRecordStatuses',projectId:'p',status:'failed',statusRevision:2,resource:{type:'table',projectId:'p',tableId:'t'},result:{blocks:[],changedCount:1,conflictCount:1,notStartedCount:0,cancelled:false},error:{message:'部分记录冲突'}}}}
    throw new Error(path)
  })
  renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice');await userEvent.click(screen.getByRole('checkbox',{name:'选择记录 文本 · 001'}));await userEvent.click(screen.getByRole('button',{name:'批量设置状态'}));await userEvent.click(screen.getByRole('button',{name:'预检批量状态'}));await userEvent.click(await screen.findByRole('button',{name:'确认开始'}))
  expect(await screen.findByText('已修改 1 条')).toBeVisible();await waitFor(()=>expect(recordReads).toBeGreaterThan(1))
})

it('opens replace import only for writable tables and keeps archived export available',async()=>{
  const {client}=api(),view=renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice')
  await userEvent.click(screen.getByRole('button',{name:'重新导入 Excel'}));expect(await screen.findByRole('dialog',{name:'用 Excel 替换数据表'})).toBeVisible()
  await userEvent.keyboard('{Escape}')
  view.rerender(<DataTableDetailPage {...props(client,{readonly:true})}/>)
  expect(screen.queryByRole('button',{name:'重新导入 Excel'})).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button',{name:'导出 Excel'}));expect(await screen.findByRole('dialog',{name:'导出 Excel'})).toBeVisible();expect(screen.getByRole('button',{name:'选择保存位置'})).toBeEnabled()
})

it('renders saved source facts without synthetic sync counters',async()=>{
  const sourceTable={...table,sourceKind:'excel' as const,source:{kind:'excel' as const,filename:'customers.xlsx',sheetName:'Customers',importedAt:'2026-01-02T00:00:00Z'}}
  const {client}=api(),request=vi.mocked(client.request);request.mockImplementation(async(path:string)=>{if(path.endsWith('/tables/t'))return sourceTable;if(path.includes('/fields'))return {items:[field],tableRevision:3};if(path.includes('/statuses'))return {items:[status],tableRevision:3};if(path.includes('/records?'))return page;throw new Error(path)})
  renderPage(<DataTableDetailPage {...props(client,{tab:'source'})}/>);expect(await screen.findByText('customers.xlsx')).toBeVisible();expect(screen.getByText('Customers')).toBeVisible();expect(screen.getByText(/不会监听原文件/)).toBeVisible();expect(screen.queryByText(/待处理 0/)).not.toBeInTheDocument()
})

it('restores applied table view state for the same workspace project and table',async()=>{
  const first=api(),view=renderPage(<DataTableDetailPage {...props(first.client)}/>);await screen.findByText('Alice')
  await userEvent.click(screen.getByRole('button',{name:'显示列'}));await userEvent.click(screen.getByRole('checkbox',{name:'姓名'}));await userEvent.click(screen.getByRole('button',{name:'应用显示列'}));expect(screen.queryByRole('columnheader',{name:'姓名'})).not.toBeInTheDocument();await waitFor(()=>expect(sessionStorage.getItem('autoflow:table-view:["w","p","t"]')).toContain('"visibleFieldIds":[]'));view.unmount()
  const second=api();renderPage(<DataTableDetailPage {...props(second.client,{instanceId:'i2'})}/>);await screen.findByText('文本 · 001')
  await userEvent.click(screen.getByRole('button',{name:'显示列'}));expect(screen.getByRole('checkbox',{name:'姓名'})).not.toBeChecked();expect(screen.queryByRole('columnheader',{name:'姓名'})).not.toBeInTheDocument()
})

it('removes stale field references from restored view state',async()=>{
  sessionStorage.setItem('autoflow:table-view:["w","p","t"]',JSON.stringify({query:{filter:{type:'compare',fieldId:'gone',operator:'eq',value:'x'},orderBy:[{fieldId:'gone',direction:'asc'}]},page:4,visibleFieldIds:['gone','f']}))
  const {client}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice')
  await waitFor(()=>{const saved=JSON.parse(sessionStorage.getItem('autoflow:table-view:["w","p","t"]')!);expect(saved.query).toEqual({filter:{type:'all',items:[]},orderBy:[]});expect(saved.visibleFieldIds).toEqual(['f']);expect(saved.page).toBe(1)})
})

it('loads current facts before replacing a conflicted editor draft',async()=>{
  let latestStatus=status,conflicted=false
  const {client}=api(),request=vi.mocked(client.request);request.mockImplementation(async(path:string,init?:Parameters<StreamingApiClient['request']>[1])=>{
    if(path.endsWith('/tables/t'))return table;if(path.includes('/fields'))return {items:[field],tableRevision:3};if(path.includes('/statuses')&&init?.method!=='PATCH')return {items:[latestStatus],tableRevision:4};if(path.includes('/records?'))return page
    if(path.includes('/statuses/s')&&init?.method==='PATCH'){conflicted=true;latestStatus={...status,name:'服务端最新状态',statusRevision:5};throw new ApiClientError('状态已变化',409,'REVISION_CONFLICT')}
    throw new Error(path)
  })
  renderPage(<DataTableDetailPage {...props(client,{tab:'statuses'})}/>);await userEvent.click(await screen.findByRole('button',{name:'编辑状态 进行中'}));const name=screen.getByLabelText('状态名称');await userEvent.clear(name);await userEvent.type(name,'我的草稿');await userEvent.click(screen.getByRole('button',{name:'保存修改'}));expect(conflicted).toBe(true)
  await userEvent.click(await screen.findByRole('button',{name:'载入最新资料'}));expect(await screen.findByText(/业务状态“服务端最新状态”的最新资料已载入/)).toBeVisible();expect(screen.getByLabelText('状态名称')).toHaveValue('我的草稿')
  await userEvent.click(screen.getByRole('button',{name:'重新编辑'}));expect(screen.getByLabelText('状态名称')).toHaveValue('服务端最新状态')
})

it('opens the table editor from settings without exposing internal versions',async()=>{
  const {client}=api();renderPage(<DataTableDetailPage {...props(client,{tab:'settings'})}/>);await userEvent.click(await screen.findByRole('button',{name:'编辑数据表'}))
  expect(screen.getByRole('dialog',{name:'编辑数据表'})).toBeVisible();expect(screen.getByLabelText('数据表名称')).toHaveValue('客户表');expect(document.body.textContent).not.toContain('数据代次')
})

it('keeps a dirty editor on the old data until the user handles the draft',async()=>{
  let currentTable=table
  const {client}=api(),request=vi.mocked(client.request);request.mockImplementation(async(path:string)=>{if(path.endsWith('/tables/t'))return currentTable;if(path.includes('/fields'))return {items:[field],tableRevision:3};if(path.includes('/statuses'))return {items:[status],tableRevision:3};if(path.includes('/records?'))return page;throw new Error(path)})
  const view=renderPage(<DataTableDetailPage {...props(client,{tab:'statuses'})}/>);await userEvent.click(await screen.findByRole('button',{name:'编辑状态 进行中'}));const name=screen.getByLabelText('状态名称');await userEvent.clear(name);await userEvent.type(name,'未保存草稿')
  currentTable={...table,datasetGeneration:'g2'};view.rerender(<DataTableDetailPage {...props(client,{tab:'statuses',instanceId:'i2'})}/>)
  expect(await screen.findByText(/数据已更新，请先处理当前编辑草稿再载入/)).toBeVisible();expect(screen.getByLabelText('状态名称')).toHaveValue('未保存草稿')
})

it('does not bind an old record key to a replacement data version during conflict reload',async()=>{
  let currentTable=table,conflicted=false
  const {client}=api(),request=vi.mocked(client.request);request.mockImplementation(async(path:string,init?:Parameters<StreamingApiClient['request']>[1])=>{
    if(path.endsWith('/tables/t'))return currentTable;if(path.includes('/fields'))return {items:[field],tableRevision:3};if(path.includes('/statuses'))return {items:[status],tableRevision:3};if(path.includes('/records?'))return page;if(path.includes('/records/MDAx')&&init?.method!=='PATCH')return record
    if(path.includes('/records/MDAx')&&init?.method==='PATCH'){conflicted=true;currentTable={...table,datasetGeneration:'g2'};throw new ApiClientError('记录已变化',409,'REVISION_CONFLICT')}
    throw new Error(path)
  })
  renderPage(<DataTableDetailPage {...props(client)}/>);await userEvent.click(await screen.findByRole('button',{name:/查看记录/}));await userEvent.click(await screen.findByRole('button',{name:'编辑记录'}));const editorDialog=screen.getByRole('dialog',{name:'编辑记录'}),value=within(editorDialog).getByLabelText('姓名');await userEvent.clear(value);await userEvent.type(value,'我的草稿');await userEvent.click(within(editorDialog).getByRole('button',{name:'保存修改'}));expect(conflicted).toBe(true)
  request.mockClear();await userEvent.click(await screen.findByRole('button',{name:'载入最新资料'}));expect(await screen.findByText(/原记录已失效/)).toBeVisible();expect(screen.queryByRole('button',{name:'重新编辑'})).not.toBeInTheDocument();expect(request.mock.calls.some(([path])=>String(path).includes('/records/'))).toBe(false);expect(within(editorDialog).getByLabelText('姓名')).toHaveValue('我的草稿')
})

it('falls back from malformed saved filters and restores the scoped scroll position',async()=>{
  sessionStorage.setItem('autoflow:table-view:["w","p","t"]',JSON.stringify({query:{filter:{type:'all'},orderBy:[]},page:1,visibleFieldIds:null,scrollY:240}))
  const {client}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice')
  expect(window.scrollTo).toHaveBeenCalledWith({top:240,behavior:'auto'});expect(screen.getByText('Alice')).toBeVisible()
})

it('shows malformed command recovery as a write blocker without discarding it',async()=>{
  localStorage.setItem('autoflow:data-edit:w:p:t','{"pending":{"kind":"recordEdit"}}')
  const {client}=api();renderPage(<DataTableDetailPage {...props(client)}/>);expect(await screen.findByText(/保存恢复记录不完整/)).toBeVisible();expect(screen.queryByRole('button',{name:'新增记录'})).not.toBeInTheDocument();expect(localStorage.getItem('autoflow:data-edit:w:p:t')).not.toBeNull()
})

it('keeps query drafts local and applies quick search only on submit',async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client)}/>);await screen.findByText('Alice')
  expect(screen.queryByRole('button',{name:'添加字段条件'})).not.toBeInTheDocument()
  const before=request.mock.calls.filter(([path])=>path.includes('/records?')).length
  await userEvent.type(screen.getByLabelText('文本搜索'),'温室')
  expect(request.mock.calls.filter(([path])=>path.includes('/records?'))).toHaveLength(before)
  await userEvent.click(screen.getByRole('button',{name:'搜索记录'}))
  await waitFor(()=>expect(request.mock.calls.filter(([path])=>path.includes('/records?')).length).toBeGreaterThan(before))
  const path=request.mock.calls.filter(([path])=>path.includes('/records?')).at(-1)![0]
  const filter=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(new URL(path,'http://local').searchParams.get('filter')!.replaceAll('-','+').replaceAll('_','/')),character=>character.charCodeAt(0))))
  expect(JSON.stringify(filter)).toContain('温室')
  const count=request.mock.calls.length
  await userEvent.click(screen.getByRole('button',{name:'显示列'}))
  await userEvent.click(screen.getByLabelText('姓名'))
  await userEvent.click(screen.getByRole('button',{name:/应用/}))
  expect(request).toHaveBeenCalledTimes(count)
  expect(screen.queryByRole('columnheader',{name:'姓名'})).not.toBeInTheDocument()
  expect(screen.getAllByRole('button',{name:'新增记录'})).toHaveLength(1)
  expect(screen.getAllByRole('button',{name:'导出 Excel'})).toHaveLength(1)
  expect(screen.getByRole('button',{name:'批量设置状态'})).toBeDisabled()
})

it('opens the typed detail route directly without fetching the record list', async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client,{record:{mode:'detail',datasetGeneration:'g',recordKey:record.ref.recordKey},onRecordNavigate:vi.fn()})}/>)
  expect(await screen.findByRole('heading',{level:1,name:'Alice'})).toBeVisible()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(request.mock.calls.some(([path])=>path.includes('/records?'))).toBe(false)
  expect(request.mock.calls.some(([path])=>path.includes('/records/MDAx?'))).toBe(true)
})
it('rejects a direct record response with a different typed identity', async()=>{
  const {client,request}=api();const original=request.getMockImplementation()!
  request.mockImplementation(async(path,init)=>path.includes('/records/')?{...record,ref:{...record.ref,recordKey:{type:'integer',value:'1'}}}:original(path,init))
  renderPage(<DataTableDetailPage {...props(client,{record:{mode:'detail',datasetGeneration:'g',recordKey:record.ref.recordKey},onRecordNavigate:vi.fn()})}/>)
  expect(await screen.findByText(/记录响应与当前地址不一致/)).toBeVisible()
  expect(screen.queryByText('Alice')).not.toBeInTheDocument()
})
it('keeps a stale generation route invalid rather than opening the same key in new data', async()=>{
  const {client,request}=api();renderPage(<DataTableDetailPage {...props(client,{record:{mode:'detail',datasetGeneration:'old',recordKey:record.ref.recordKey},onRecordNavigate:vi.fn()})}/>)
  expect(await screen.findByText(/这条记录属于已替换的数据/)).toBeVisible()
  expect(request.mock.calls.some(([path])=>path.includes('/records/'))).toBe(false)
})

it('rebuilds inline status baseline from confirmed save results so cancel cannot restore a stale status',async()=>{
  let currentRecord={...record};const {client,request}=api();const original=request.getMockImplementation()!
  request.mockImplementation(async(path,init)=>{if(path.includes('/records/')) { if(init?.method==='PUT') currentRecord={...currentRecord,statusId:(init.body as {statusId:string|null}).statusId,statusRevision:currentRecord.statusRevision+1};return currentRecord }return original(path,init)})
  renderPage(<DataTableDetailPage {...props(client,{record:{mode:'detail',datasetGeneration:'g',recordKey:record.ref.recordKey},onRecordNavigate:vi.fn()})}/>)
  await userEvent.click(await screen.findByRole('button',{name:'清空状态'}))
  await waitFor(()=>expect(currentRecord.statusId).toBeNull())
  await waitFor(()=>expect(screen.getByRole('combobox',{name:'记录业务状态'})).toHaveTextContent('未设置'))
  await userEvent.click(screen.getByRole('button',{name:'取消'}))
  expect(screen.getByRole('combobox',{name:'记录业务状态'})).toHaveTextContent('未设置')
  await userEvent.click(screen.getByRole('button',{name:'清空状态'}))
  await waitFor(()=>expect(currentRecord.statusRevision).toBe(3))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('restores an accepted-unknown create after a full coordinator remount without opening a second editor',async()=>{
  const {client,request}=api();const original=request.getMockImplementation()!
  request.mockImplementation(async(path,init)=>{if(init?.method==='POST'||path.includes('/operations/'))throw new TypeError('offline');return original(path,init)})
  const options=props(client,{record:{mode:'create'},onRecordNavigate:vi.fn()})
  const first=renderPage(<DataTableDetailPage {...options}/>);await userEvent.click(await screen.findByRole('combobox',{name:'姓名值状态'}));await userEvent.click(screen.getByRole('option',{name:'填写值'}));await userEvent.type(screen.getByLabelText('姓名'),'持久草稿')
  await userEvent.click(screen.getByRole('button',{name:'创建记录'}));await screen.findByRole('button',{name:'核对保存结果'});first.unmount()
  renderPage(<DataTableDetailPage {...options}/>)
  expect(await screen.findByRole('button',{name:'核对保存结果'})).toBeVisible()
  expect(screen.getByRole('heading',{level:1,name:'新增记录'})).toBeVisible()
  expect(screen.getByLabelText('姓名')).toHaveValue('持久草稿')
})

it('shows corrupt recovery evidence as a write block instead of throwing from route activation',async()=>{
  localStorage.setItem('autoflow:data-edit:w:p:t','{bad-json');const {client}=api()
  renderPage(<DataTableDetailPage {...props(client,{record:{mode:'create'},onRecordNavigate:vi.fn()})}/>)
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.queryByRole('form',{name:'新建记录表单'})).not.toBeInTheDocument()
})
it('does not mount a recovered record A form under a direct record B edit address',async()=>{
  const {client,request}=api();const original=request.getMockImplementation()!
  request.mockImplementation(async(path,init)=>{if(init?.method==='PATCH'||path.includes('/operations/'))throw new TypeError('offline');if(path.includes('/records/'))return {...record,ref:{...record.ref,recordKey:{type:'text',value:path.includes('Qg?')?'B':'001'}}};return original(path,init)})
  const options=props(client,{record:{mode:'edit',datasetGeneration:'g',recordKey:record.ref.recordKey},onRecordNavigate:vi.fn()})
  const first=renderPage(<DataTableDetailPage {...options}/>);const name=await screen.findByLabelText('姓名');await userEvent.clear(name);await userEvent.type(name,'仅属于A');await userEvent.click(screen.getByRole('button',{name:'保存修改'}));await screen.findByRole('button',{name:'核对保存结果'});first.unmount()
  renderPage(<DataTableDetailPage {...options} record={{mode:'edit',datasetGeneration:'g',recordKey:{type:'text',value:'B'}}}/>)
  expect(await screen.findByRole('button',{name:'核对原记录保存结果'})).toBeVisible()
  expect(screen.queryByLabelText('姓名')).not.toBeInTheDocument()
  expect(localStorage.getItem('autoflow:data-edit:w:p:t')).toContain('仅属于A')
})
it('persists the clicked typed origin before navigating away from the list',async()=>{
  const {client}=api(),navigate=vi.fn();renderPage(<DataTableDetailPage {...props(client,{onRecordNavigate:navigate})}/>);await userEvent.click(await screen.findByRole('button',{name:'查看记录 文本 · 001'}))
  expect(navigate).toHaveBeenCalledWith({mode:'detail',datasetGeneration:'g',recordKey:record.ref.recordKey})
  expect(JSON.parse(sessionStorage.getItem('autoflow:table-view:["w","p","t"]')!)).toMatchObject({originRowKey:record.ref.recordKey,identity:{datasetGeneration:'g',workspaceKey:'w'}})
})

it('does not mount record A pending status controls inside record B detail',async()=>{
  const {client,request}=api();const original=request.getMockImplementation()!
  request.mockImplementation(async(path,init)=>{if(init?.method==='PUT'||path.includes('/operations/'))throw new TypeError('offline');if(path.includes('/records/'))return {...record,ref:{...record.ref,recordKey:{type:'text',value:path.includes('Qg?')?'B':'001'}}};return original(path,init)})
  const options=props(client,{record:{mode:'detail',datasetGeneration:'g',recordKey:record.ref.recordKey},onRecordNavigate:vi.fn()})
  const first=renderPage(<DataTableDetailPage {...options}/>);await userEvent.click(await screen.findByRole('button',{name:'清空状态'}));await screen.findByRole('button',{name:'核对保存结果'});first.unmount()
  renderPage(<DataTableDetailPage {...options} record={{mode:'detail',datasetGeneration:'g',recordKey:{type:'text',value:'B'}}}/>)
  expect(await screen.findByRole('button',{name:'核对原记录保存结果'})).toBeVisible()
  expect(screen.queryByRole('combobox',{name:'记录业务状态'})).not.toBeInTheDocument()
  expect(await screen.findByRole('region',{name:'业务状态'})).toHaveTextContent('进行中')
})
