import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
const api=vi.hoisted(()=>({pages:vi.fn(),page:vi.fn()}))
vi.mock('../api',()=>({browserApi:api}))
import {BrowserPagesPanel} from '../components/BrowserPagesPanel'
const state={sessionId:'browser-a',revision:2,targetPageId:'one',pages:[{pageId:'one',title:'第一页',url:'http://local/a'},{pageId:'two',title:'第二页',url:'http://local/b'}]}
beforeEach(()=>{vi.useFakeTimers();api.pages.mockResolvedValue({success:true,data:state});api.page.mockReset()})
afterEach(()=>{cleanup();vi.useRealTimers()})
async function mount(){await act(async()=>{render(<BrowserPagesPanel url="http://local/new" onUrlChange={()=>{}}/>)})}
it('selects explicitly, then focuses and navigates the confirmed target',async()=>{
 await mount();const selected={...state,revision:3,targetPageId:'two'};api.page.mockResolvedValue({success:true,data:selected})
 await act(async()=>{fireEvent.change(screen.getByLabelText('目标标签页'),{target:{value:'two'}})})
 expect(api.page).toHaveBeenLastCalledWith({sessionId:'browser-a',expectedRevision:2,pageId:'two',action:'select',url:null})
 await act(async()=>{fireEvent.click(screen.getByText('聚焦目标页'))})
 expect(api.page).toHaveBeenLastCalledWith({sessionId:'browser-a',expectedRevision:3,pageId:'two',action:'focus',url:null})
 await act(async()=>{fireEvent.click(screen.getByText('跳转'))})
 expect(api.page).toHaveBeenLastCalledWith({sessionId:'browser-a',expectedRevision:3,pageId:'two',action:'navigate',url:'http://local/new'})
})
it('does not select a replacement when the target closes',async()=>{
 await mount();api.pages.mockResolvedValue({success:true,data:{...state,revision:3,targetPageId:null,pages:[state.pages[1]]}})
 await act(async()=>{vi.advanceTimersByTime(1000)})
 expect((screen.getByLabelText('目标标签页') as HTMLSelectElement).value).toBe('')
 expect((screen.getByText('跳转') as HTMLButtonElement).disabled).toBe(true)
 expect(api.page).not.toHaveBeenCalled()
})
it('preserves last confirmed target on failure and ignores a late status during command',async()=>{
 let deliver!:(value:unknown)=>void
 await mount();api.pages.mockImplementation(()=>new Promise(resolve=>{deliver=resolve}))
 await act(async()=>{vi.advanceTimersByTime(1000)})
 api.page.mockResolvedValue({success:false,error:'页面已变化'})
 await act(async()=>{fireEvent.change(screen.getByLabelText('目标标签页'),{target:{value:'two'}})})
 await act(async()=>{deliver({success:true,data:{...state,targetPageId:'two'}})})
 expect(screen.getByRole('alert').textContent).toBe('页面已变化')
 expect((screen.getByLabelText('目标标签页') as HTMLSelectElement).value).toBe('one')
})
