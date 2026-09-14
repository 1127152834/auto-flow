import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})})
vi.mock('@monaco-editor/react',()=>({default:()=>null,loader:{config:vi.fn(),init:vi.fn(async()=>{})}}))
vi.mock('monaco-editor',()=>({}))
vi.mock('../components/AICodeAssistant',()=>({AICodeAssistant:()=>null}))
import {JsEditorDialog} from '../components/JsEditorDialog'
import {InjectJsEditorDialog} from '../components/InjectJsEditorDialog'
import {PythonEditorDialog} from '../components/PythonEditorDialog'
const dialogs=[['JavaScript',JsEditorDialog],['页面注入',InjectJsEditorDialog],['Python',PythonEditorDialog]] as const
let write:ReturnType<typeof vi.fn<(text:string)=>Promise<void>>>
beforeEach(()=>{write=vi.fn(async()=>{});Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:write}})})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.useRealTimers()})
it.each(dialogs)('%s confirms copying only after acknowledgement and allows retry after rejection',async(_name,Dialog)=>{
 write.mockRejectedValueOnce(new Error('权限被拒绝'))
 render(<Dialog isOpen code="用户代码" onClose={vi.fn()} onSave={vi.fn()}/> )
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:/^复制$/}))})
 expect(screen.getByRole('alert').textContent).toContain('权限被拒绝');expect(screen.queryByText('已复制')).toBeNull()
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:/^复制$/}))})
 expect(screen.getByText('已复制')).toBeTruthy();expect(screen.queryByRole('alert')).toBeNull();expect(write.mock.calls).toEqual([['用户代码'],['用户代码']])
})
it.each(dialogs)('%s does not retain a late clipboard response across closing and reopening',async(_name,Dialog)=>{
 let finish!:()=>void;write.mockImplementationOnce(()=>new Promise<void>(resolve=>{finish=resolve}))
 const props={code:'用户代码',onClose:vi.fn(),onSave:vi.fn()};const view=render(<Dialog {...props} isOpen/>)
 fireEvent.click(screen.getByRole('button',{name:/^复制$/}));expect(screen.getByRole('button',{name:'正在复制'}).hasAttribute('disabled')).toBe(true)
 view.rerender(<Dialog {...props} isOpen={false}/>);view.rerender(<Dialog {...props} isOpen/>)
 await act(async()=>{finish()});expect(screen.queryByText('已复制')).toBeNull();expect(screen.getByRole('button',{name:/^复制$/})).toBeTruthy()
})
it.each(dialogs)('%s clears its copy acknowledgement timer on unmount',async(_name,Dialog)=>{
 vi.useFakeTimers();const view=render(<Dialog isOpen code="用户代码" onClose={vi.fn()} onSave={vi.fn()}/> )
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:/^复制$/}))});expect(screen.getByText('已复制')).toBeTruthy()
 view.unmount();expect(vi.getTimerCount()).toBe(0)
})
it.each(dialogs)('%s shows unavailable clipboard as an actionable failure',async(_name,Dialog)=>{
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined})
 render(<Dialog isOpen code="用户代码" onClose={vi.fn()} onSave={vi.fn()}/> )
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:/^复制$/}))})
 expect(screen.getByRole('alert').textContent).toContain('手动选择代码复制');expect(screen.queryByText('已复制')).toBeNull()
})
it.each(dialogs)('%s ignores a copy acknowledgement for code that has since changed',async(_name,Dialog)=>{
 let finish!:()=>void;write.mockImplementationOnce(()=>new Promise<void>(resolve=>{finish=resolve}))
 const props={isOpen:true,onClose:vi.fn(),onSave:vi.fn()};const view=render(<Dialog {...props} code="原代码"/>)
 fireEvent.click(screen.getByRole('button',{name:/^复制$/}));view.rerender(<Dialog {...props} code="新代码"/>)
 await act(async()=>{finish()});expect(screen.queryByText('已复制')).toBeNull()
 await act(async()=>{fireEvent.click(screen.getByRole('button',{name:/^复制$/}))})
 expect(write.mock.calls).toEqual([['原代码'],['新代码']]);expect(screen.getByText('已复制')).toBeTruthy()
})
