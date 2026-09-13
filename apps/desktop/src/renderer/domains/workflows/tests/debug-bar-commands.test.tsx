import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {DebugBar} from '../components/DebugBar'
import {useDebugStore} from '../hooks/stores/debugStore'
import {useWorkflowStore} from '../editor-store'
import {workflowApi} from '../api'
beforeEach(()=>{useWorkflowStore.setState({currentExecutionWorkflowId:'debug-ui'});useDebugStore.getState().setPaused({nodeId:'first',label:'首次暂停',variables:{value:1}})})
afterEach(()=>{cleanup();useDebugStore.getState().clearPaused();vi.restoreAllMocks()})
it('shows an explicit rejected command and permits correction without clearing the pause',async()=>{
 vi.spyOn(workflowApi,'debugStep').mockResolvedValue({success:false,httpStatus:409,error:'暂停上下文已过期'})
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}))
 await screen.findByText('暂停上下文已过期')
 expect(useDebugStore.getState().isPaused).toBe(true)
 expect((screen.getByRole('button',{name:'单步'}) as HTMLButtonElement).disabled).toBe(false)
})
it('keeps stop available while a step request is pending',async()=>{
 vi.spyOn(workflowApi,'debugStep').mockImplementation(()=>new Promise(()=>{}))
 vi.spyOn(workflowApi,'stop').mockResolvedValue({success:true})
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}))
 expect((screen.getByRole('button',{name:'停止'}) as HTMLButtonElement).disabled).toBe(false)
 fireEvent.click(screen.getByRole('button',{name:'停止'}))
 await waitFor(()=>expect(workflowApi.stop).toHaveBeenCalledWith('debug-ui'))
})
it('does not unlock another step merely because HTTP accepted the first request',async()=>{
 vi.spyOn(workflowApi,'debugStep').mockResolvedValue({success:true})
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}))
 await screen.findByText('等待执行状态确认')
 expect((screen.getByRole('button',{name:'单步'}) as HTMLButtonElement).disabled).toBe(true)
 expect(useDebugStore.getState().isPaused).toBe(true)
})
it('does not show a late failure in a newer pause, even at the same node',async()=>{
 let reply!:(value:Awaited<ReturnType<typeof workflowApi.debugStep>>)=>void
 vi.spyOn(workflowApi,'debugStep').mockImplementation(()=>new Promise(resolve=>{reply=resolve}))
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}))
 act(()=>useDebugStore.getState().setPaused({nodeId:'first',label:'下一轮暂停',variables:{value:2}}))
 await act(async()=>reply({success:false,httpStatus:409,error:'旧请求失败'}))
 expect(screen.queryByText('旧请求失败')).toBeNull()
 expect((screen.getByRole('button',{name:'单步'}) as HTMLButtonElement).disabled).toBe(false)
})
it('retains an uncertain control request without offering an unsafe repeat step',async()=>{
 vi.spyOn(workflowApi,'debugStep').mockResolvedValue({success:false,error:'Failed to fetch'})
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}))
 await screen.findByText(/请求结果尚未确认/)
 expect((screen.getByRole('button',{name:'单步'}) as HTMLButtonElement).disabled).toBe(true)
 expect((screen.getByRole('button',{name:'停止'}) as HTMLButtonElement).disabled).toBe(false)
})
it('keeps the pause and reports a stop rejection instead of claiming it ended',async()=>{
 vi.spyOn(workflowApi,'stop').mockResolvedValue({success:false,httpStatus:503,error:'清理尚未完成'})
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'停止'}))
 await screen.findByText('清理尚未完成')
 expect(useDebugStore.getState().isPaused).toBe(true)
 expect((screen.getByRole('button',{name:'停止'}) as HTMLButtonElement).disabled).toBe(false)
})
it('lets a confirmed next pause release the pending step',async()=>{
 vi.spyOn(workflowApi,'debugStep').mockResolvedValue({success:true})
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}))
 await screen.findByText('等待执行状态确认')
 act(()=>useDebugStore.getState().clearPaused())
 expect(screen.queryByRole('button',{name:'单步'})).toBeNull()
 act(()=>useDebugStore.getState().setPaused({nodeId:'next',label:'下一节点'}))
 expect((screen.getByRole('button',{name:'单步'}) as HTMLButtonElement).disabled).toBe(false)
})
it('does not let a superseded step response unlock a pending stop',async()=>{
 let reply!:(value:Awaited<ReturnType<typeof workflowApi.debugStep>>)=>void
 vi.spyOn(workflowApi,'debugStep').mockImplementation(()=>new Promise(resolve=>{reply=resolve}))
 vi.spyOn(workflowApi,'stop').mockImplementation(()=>new Promise(()=>{}))
 render(<DebugBar />);fireEvent.click(screen.getByRole('button',{name:'单步'}));fireEvent.click(screen.getByRole('button',{name:'停止'}))
 await act(async()=>reply({success:false,httpStatus:409,error:'旧单步拒绝'}))
 expect(screen.queryByText('旧单步拒绝')).toBeNull()
 expect((screen.getByRole('button',{name:'停止'}) as HTMLButtonElement).disabled).toBe(true)
})
