import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { AutoBrowserDialog } from '../components/AutoBrowserDialog'
import { browserApi, elementPickerApi, systemApi } from '../api'
import {configureStudioConnection} from '../api/config'
import { registerDocumentLeaveHandler, registerDocumentLeaveResource } from '../lib/documentLeave'
const log = vi.fn()
it.each([true, false])('closes the browser only after active recording departure is confirmed: %s', async allowed => {
  const removeResource = registerDocumentLeaveResource(() => ({id: 'recording', label: '网页录制', release: async () => true}))
  let confirm!: (value: boolean) => void
  const leave = vi.fn(() => new Promise<boolean>(resolve => { confirm = resolve }))
  const removeHandler = registerDocumentLeaveHandler(leave)
  const close = vi.spyOn(browserApi, 'close').mockResolvedValue({success: true})
  try {
    render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
    fireEvent.click(await screen.findByRole('button', {name: '关闭浏览器'}))
    expect(leave).toHaveBeenCalledWith({preserveMainDocument: true, sessionsOnly: true, keepBrowser: true})
    expect(close).not.toHaveBeenCalled()
    await act(async () => confirm(allowed))
    expect(close).toHaveBeenCalledTimes(allowed ? 1 : 0)
    if (!allowed) expect(screen.getByRole('button', {name: '关闭浏览器'})).toBeTruthy()
  } finally { removeHandler(); removeResource() }
})
beforeEach(() => {
  log.mockClear()
  vi.spyOn(browserApi, 'pages').mockResolvedValue({success:true,data:{sessionId:'b',revision:0,targetPageId:'p',pages:[{pageId:'p',title:'页面',url:'about:blank'}]}})
  vi.spyOn(browserApi, 'getStatus').mockResolvedValue({ success: true, data: { isOpen: true, pickerActive: true } })
  vi.spyOn(elementPickerApi, 'getSelected').mockResolvedValue({ success: true, data: { selected: false } })
  vi.spyOn(elementPickerApi, 'getSimilar').mockResolvedValue({ success: true, data: { selected: false } })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })
it('leaves picking mode after a confirmed external session closure',async()=>{
 vi.useFakeTimers()
 vi.mocked(elementPickerApi.getSelected).mockResolvedValue({success:true,data:{active:false,selected:false}})
 render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log}/>)
 await act(async()=>{})
 await act(async()=>vi.advanceTimersByTimeAsync(500))
 expect(screen.queryByRole('button',{name:'停止选择'})).toBeNull()
 expect(screen.getByRole('button',{name:'启动选择器'})).toBeTruthy()
 expect(elementPickerApi.getSimilar).not.toHaveBeenCalled()
})
it.each(['close', 'stop'])('keeps confirmed browser state when %s returns a cleanup error', async action => {
  const method = action === 'close' ? 'close' : 'stopPicker'
  vi.spyOn(browserApi, method).mockResolvedValue({ success: false, error: '清理失败，请重试' })
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await screen.findByRole('button', { name: '停止选择' })
  fireEvent.click(screen.getByRole('button', { name: action === 'close' ? '关闭浏览器' : '停止选择' }))
  await waitFor(() => expect(log).toHaveBeenCalledWith('error', expect.stringContaining('清理失败')))
  expect(screen.getByRole('button', { name: '关闭浏览器' })).toBeDefined()
  expect(screen.getByRole('button', { name: '停止选择' })).toBeDefined()
  expect(log.mock.calls.some(([, message]) => /已关闭|已停止/.test(message))).toBe(false)
})
it('keeps the last confirmed state on a failed refresh instead of claiming closure', async () => {
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await screen.findByRole('button', { name: '停止选择' })
  vi.mocked(browserApi.getStatus).mockRejectedValueOnce(new Error('offline'))
  fireEvent.click(screen.getByTitle('刷新状态'))
  await waitFor(() => expect(log).toHaveBeenCalledWith('error', expect.stringContaining('offline')))
  expect(screen.getByRole('button', { name: '关闭浏览器' })).toBeDefined()
  expect(screen.getByRole('button', { name: '停止选择' })).toBeDefined()
})
it.each(['close-panel', 'unmount'])('does not copy a late selected element after %s', async action => {
  vi.useFakeTimers()
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.getSelected>>) => void
  vi.mocked(elementPickerApi.getSelected).mockImplementation(() => new Promise(resolve => { release = resolve }))
  const copy = vi.spyOn(systemApi, 'setClipboard').mockResolvedValue({ success: true })
  const view = render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await act(async () => {})
  await act(async () => { vi.advanceTimersByTime(500) })
  expect(elementPickerApi.getSelected).toHaveBeenCalledOnce()
  if (action === 'unmount') view.unmount()
  else view.rerender(<AutoBrowserDialog isOpen={false} onClose={vi.fn()} onLog={log} />)
  await act(async () => release({ success: true, data: { selected: true, element: { selector: '#late' } } }))
  expect(copy).not.toHaveBeenCalled()
  expect(elementPickerApi.getSimilar).not.toHaveBeenCalled()
  expect(log).not.toHaveBeenCalled()
})
it('keeps at most one polling request in flight', async () => {
  vi.useFakeTimers()
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.getSelected>>) => void
  vi.mocked(elementPickerApi.getSelected).mockImplementation(() => new Promise(resolve => { release = resolve }))
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await act(async () => {})
  await act(async () => { vi.advanceTimersByTime(2500) })
  expect(elementPickerApi.getSelected).toHaveBeenCalledOnce()
  await act(async () => release({ success: true, data: { selected: false } }))
})
it('does not resurrect the picker from a refresh response older than a confirmed stop', async () => {
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await screen.findByRole('button', { name: '停止选择' })
  let release!: (value: Awaited<ReturnType<typeof browserApi.getStatus>>) => void
  vi.mocked(browserApi.getStatus).mockImplementationOnce(() => new Promise(resolve => { release = resolve }))
  vi.spyOn(browserApi, 'stopPicker').mockResolvedValue({ success: true })
  fireEvent.click(screen.getByTitle('刷新状态'))
  fireEvent.click(screen.getByRole('button', { name: '停止选择' }))
  await screen.findByRole('button', { name: '启动选择器' })
  await act(async () => release({ success: true, data: { isOpen: true, pickerActive: true } }))
  expect(screen.queryByRole('button', { name: '停止选择' })).toBeNull()
})
it('suppresses repeated polling errors without pretending the picker has stopped and recovers polling', async () => {
  vi.useFakeTimers()
  vi.mocked(elementPickerApi.getSelected).mockResolvedValue({ success: false, error: '暂时离线' })
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await act(async () => {})
  await act(async () => { vi.advanceTimersByTime(500) })
  await act(async () => { vi.advanceTimersByTime(500) })
  expect(log).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: '停止选择' })).toBeDefined()
  vi.mocked(elementPickerApi.getSelected).mockResolvedValueOnce({ success: true, data: { selected: false } })
  await act(async () => { vi.advanceTimersByTime(500) })
  await act(async () => { vi.advanceTimersByTime(500) })
  expect(log).toHaveBeenCalledTimes(2)
})
it('ignores a similar-element response after the panel closes', async () => {
  vi.useFakeTimers()
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.getSimilar>>) => void
  vi.mocked(elementPickerApi.getSimilar).mockImplementation(() => new Promise(resolve => { release = resolve }))
  const copy = vi.spyOn(systemApi, 'setClipboard').mockResolvedValue({ success: true })
  const view = render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log} />)
  await act(async () => {})
  await act(async () => { vi.advanceTimersByTime(500) })
  expect(elementPickerApi.getSimilar).toHaveBeenCalledOnce()
  view.rerender(<AutoBrowserDialog isOpen={false} onClose={vi.fn()} onLog={log} />)
  await act(async () => release({ success: true, data: { selected: true, similar: { pattern: '.row-{index}', count: 4, minIndex: 1, maxIndex: 4 } } }))
  expect(copy).not.toHaveBeenCalled()
  expect(log).not.toHaveBeenCalled()
})
it.each(['start','stop','navigate'] as const)('serializes %s with other browser commands and restores controls after rejection',async action=>{
 vi.mocked(browserApi.getStatus).mockResolvedValue({success:true,data:{isOpen:true,pickerActive:action==='stop'}})
 const method=action==='start'?'startPicker':action==='stop'?'stopPicker':'page'
 let release!:(value:{success:boolean;error?:string})=>void
 const command=vi.spyOn(browserApi,method).mockImplementation(()=>new Promise<{success:boolean;error?:string}>(resolve=>{release=resolve}))
 const close=vi.spyOn(browserApi,'close').mockResolvedValue({success:true})
 render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log}/>)
 await screen.findByRole('button',{name:'关闭浏览器'})
 if(action==='navigate')fireEvent.change(screen.getByPlaceholderText('https://example.com'),{target:{value:'https://example.test'}})
 const button=screen.getByRole('button',{name:action==='start'?'启动选择器':action==='stop'?'停止选择':'跳转'})
 fireEvent.click(button);fireEvent.click(button);fireEvent.click(screen.getByRole('button',{name:'关闭浏览器'}))
 expect(command).toHaveBeenCalledTimes(1)
 expect(close).not.toHaveBeenCalled()
 expect((button as HTMLButtonElement).disabled).toBe(true)
 await act(async()=>release({success:false,error:'命令被拒绝'}))
 expect((button as HTMLButtonElement).disabled).toBe(false)
 expect(log).toHaveBeenCalledWith('error',expect.stringContaining('命令被拒绝'))
})

it('preserves an open browser after a malformed status response through the actual API',async()=>{
 vi.mocked(browserApi.getStatus).mockRestore()
 let malformed=false
 const restore=configureStudioConnection('http://browser-status.test',async()=>Response.json(malformed?{isOpen:'false',pickerActive:false}:{isOpen:true,pickerActive:false}))
 try{
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log}/>)
  await screen.findByRole('button',{name:'关闭浏览器'})
  malformed=true;fireEvent.click(screen.getByTitle('刷新状态'))
  await waitFor(()=>expect(log).toHaveBeenCalledWith('error','读取浏览器状态失败: 浏览器状态响应格式错误，保留最后确认状态'))
  expect(screen.getByRole('button',{name:'关闭浏览器'})).toBeTruthy()
 }finally{restore()}
})
it('does not copy a pending pick result once a stop command has begun',async()=>{
 vi.useFakeTimers()
 let selected!:(value:Awaited<ReturnType<typeof elementPickerApi.getSelected>>)=>void
 let stopped!:(value:{success:boolean})=>void
 vi.mocked(elementPickerApi.getSelected).mockImplementation(()=>new Promise(resolve=>{selected=resolve}))
 vi.spyOn(browserApi,'stopPicker').mockImplementation(()=>new Promise<{success:boolean}>(resolve=>{stopped=resolve}))
 const copy=vi.spyOn(systemApi,'setClipboard').mockResolvedValue({success:true})
 render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log}/>);await act(async()=>{})
 await act(async()=>vi.advanceTimersByTimeAsync(500))
 fireEvent.click(screen.getByRole('button',{name:'停止选择'}))
 await act(async()=>selected({success:true,data:{selected:true,element:{selector:'#late'}}}))
 expect(copy).not.toHaveBeenCalled()
 expect(log).not.toHaveBeenCalledWith('success','已选择元素: #late')
 await act(async()=>stopped({success:true}))
 expect(screen.getByRole('button',{name:'启动选择器'})).toBeTruthy()
})

it('passes the selected AutoFlow profile without mixing source launch settings',async()=>{
 vi.mocked(browserApi.getStatus).mockResolvedValue({success:true,data:{isOpen:false,pickerActive:false}})
 vi.spyOn(browserApi,'profiles').mockResolvedValue({success:true,data:{items:[{id:'profile-1',name:'验收配置'}] as never,total:1}})
 const open=vi.spyOn(browserApi,'open').mockResolvedValue({success:true})
 render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={log}/>)
 await screen.findByRole('option',{name:'验收配置'})
 fireEvent.change(screen.getByLabelText('浏览器配置'),{target:{value:'profile-1'}})
 fireEvent.click(screen.getByRole('button',{name:'打开浏览器'}))
 await waitFor(()=>expect(open).toHaveBeenCalledWith(undefined,undefined,'profile-1'))
})
