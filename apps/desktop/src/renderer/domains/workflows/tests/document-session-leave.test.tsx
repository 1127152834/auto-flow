import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {useDraftProtection} from '../hooks/useDraftProtection'
import {getDocumentLeaveResources, registerDocumentLeaveResource, requestDocumentLeave, type LeaveResource} from '../lib/documentLeave'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'

let resource: LeaveResource | null
let unregister: () => void
let save: ReturnType<typeof vi.fn<() => Promise<boolean>>>
let release: ReturnType<typeof vi.fn<() => Promise<boolean>>>
function Protection() { const {draftDialog} = useDraftProtection(save); return draftDialog }
beforeEach(() => {
  store.getState().clearWorkflow()
  store.getState().addVariable({name:'draft',value:'keep',type:'string',scope:'global'})
  save = vi.fn(async () => { store.setState({hasUnsavedChanges:false}); return true })
  release = vi.fn(async () => { resource=null; return true })
  resource = {id:'session:1',label:'测试会话',release}
  unregister = registerDocumentLeaveResource(() => resource)
})
afterEach(() => {cleanup();unregister()})
async function begin() { let promise!:Promise<boolean>; await act(async () => {promise=requestDocumentLeave()}); return {promise} }
const choose = async (name:string) => act(async () => {fireEvent.click(screen.getByRole('button',{name}))})
it('cancels without saving or releasing the session', async () => {
  render(<Protection/>);const {promise}=await begin();await choose('取消')
  expect(await promise).toBe(false);expect(save).not.toHaveBeenCalled();expect(release).not.toHaveBeenCalled()
})
it('waits for successful save before releasing, then allows departure', async () => {
  let finish!:(value:boolean)=>void
  save.mockImplementationOnce(() => new Promise(resolve => {finish=resolve}))
  render(<Protection/>);const {promise}=await begin();await choose('保存并结束会话')
  expect(release).not.toHaveBeenCalled()
  await act(async () => {store.setState({hasUnsavedChanges:false});finish(true)})
  expect(await promise).toBe(true);expect(release).toHaveBeenCalledTimes(1)
})
it('preserves the session after save failure', async () => {
  save.mockResolvedValueOnce(false)
  render(<Protection/>);const {promise}=await begin();await choose('保存并结束会话')
  expect(await promise).toBe(false);expect(release).not.toHaveBeenCalled();expect(store.getState().hasUnsavedChanges).toBe(true)
})
it('discard releases without saving; does not clear the draft itself', async () => {
  render(<Protection/>);const {promise}=await begin();await choose('放弃修改并结束会话')
  expect(await promise).toBe(true);expect(save).not.toHaveBeenCalled();expect(store.getState().variables[0].value).toBe('keep')
})
it('requires confirmation for a saved document with an active session', async () => {
  store.setState({hasUnsavedChanges:false});render(<Protection/>);const {promise}=await begin()
  expect(screen.queryByRole('button',{name:'放弃修改并结束会话'})).toBeNull()
  await choose('结束会话后继续');expect(await promise).toBe(true);expect(save).not.toHaveBeenCalled()
})
it('keeps responsibility and allows retry after cleanup failure', async () => {
  release.mockResolvedValueOnce(false)
  render(<Protection/>);const first=await begin();await choose('放弃修改并结束会话')
  expect(await first.promise).toBe(false);expect(getDocumentLeaveResources()).toHaveLength(1)
  const second=await begin();await choose('放弃修改并结束会话')
  expect(await second.promise).toBe(true);expect(release).toHaveBeenCalledTimes(2)
})
it('rejects a replacement session created while deciding', async () => {
  render(<Protection/>);const {promise}=await begin()
  resource={id:'session:2',label:'新会话',release}
  await choose('保存并结束会话');expect(await promise).toBe(false);expect(save).not.toHaveBeenCalled();expect(release).not.toHaveBeenCalled()
})
it('rejects a new session appearing during save', async () => {
  save.mockImplementationOnce(async () => {resource={id:'session:2',label:'新会话',release};store.setState({hasUnsavedChanges:false});return true})
  render(<Protection/>);const {promise}=await begin();await choose('保存并结束会话')
  expect(await promise).toBe(false);expect(release).not.toHaveBeenCalled()
})
it('blocks departure if edits arrive during cleanup', async () => {
  release.mockImplementationOnce(async () => {store.getState().updateVariable('draft','new');resource=null;return true})
  render(<Protection/>);const {promise}=await begin();await choose('放弃修改并结束会话')
  expect(await promise).toBe(false);expect(store.getState().variables[0].value).toBe('new')
})
it('does not stop an already finished session', async () => {
  render(<Protection/>);const {promise}=await begin();resource=null;await choose('放弃修改并结束会话')
  expect(await promise).toBe(true);expect(release).not.toHaveBeenCalled()
})
it('does not forward cleanup to a different connection', async () => {
  render(<Protection/>);const {promise}=await begin()
  const restore=configureStudioConnection('http://changed.test',fetch)
  try {await choose('放弃修改并结束会话');expect(await promise).toBe(false);expect(release).not.toHaveBeenCalled()} finally {restore()}
})
it('rejects concurrent departure and resolves cancellation when unmounted', async () => {
  const view=render(<Protection/>);const {promise}=await begin()
  expect(await requestDocumentLeave()).toBe(false);view.unmount()
  expect(await promise).toBe(false);expect(await requestDocumentLeave()).toBe(false);expect(release).not.toHaveBeenCalled()
})
it('does not release another session after a failed cleanup', async () => {
  const other=vi.fn(async()=>true)
  const remove=registerDocumentLeaveResource(()=>({id:'session:second',label:'第二会话',release:other}))
  try {
    release.mockResolvedValueOnce(false);render(<Protection/>);const {promise}=await begin();await choose('放弃修改并结束会话')
    expect(await promise).toBe(false);expect(other).not.toHaveBeenCalled()
  } finally {remove()}
})
it('rejects a service claiming cleanup success while still holding the session', async () => {
  release.mockResolvedValueOnce(true);render(<Protection/>);const {promise}=await begin();await choose('放弃修改并结束会话')
  expect(await promise).toBe(false)
  await waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('当前流程已保留'))).toBe(true))
})
it('session transitions keep the editor draft and may preserve its browsing container',async()=>{
 const {requestSessionTransition}=await import('../lib/documentLeave')
 let browser:LeaveResource|null={id:'browser:1',kind:'browser',label:'浏览器',release:vi.fn(async()=>{browser=null;return true})}
 const unregisterBrowser=registerDocumentLeaveResource(()=>browser)
 try{
  render(<Protection/>);let pending!:Promise<boolean>
  await act(async()=>{pending=requestSessionTransition(true)})
  await choose('结束会话后继续')
  expect(await pending).toBe(true);expect(save).not.toHaveBeenCalled()
  expect(store.getState().hasUnsavedChanges).toBe(true)
  expect(getDocumentLeaveResources().map(item=>item.id)).toEqual(['browser:1'])
 }finally{unregisterBrowser()}
})
