import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
import {BrowserProfileSelect} from '../components/BrowserProfileSelect'
import {browserApi} from '../api'
import {useGlobalConfigStore} from '../hooks/stores/globalConfigStore'
afterEach(()=>{cleanup();vi.restoreAllMocks();useGlobalConfigStore.getState().setBrowserProfileId('')})
it('shares the managed selection across browser and run entry points and retains unavailable IDs',async()=>{
 const profiles=vi.spyOn(browserApi,'profiles').mockResolvedValue({success:true,data:{items:[{id:'one',name:'配置一'},{id:'two',name:'配置二'}] as never,total:2}})
 render(<><BrowserProfileSelect/><BrowserProfileSelect label="运行浏览器配置"/></>)
 await waitFor(()=>expect((screen.getByLabelText('浏览器配置') as HTMLSelectElement).value).toBe('one'))
 fireEvent.change(screen.getByLabelText('运行浏览器配置'),{target:{value:'two'}})
 expect((screen.getByLabelText('浏览器配置') as HTMLSelectElement).value).toBe('two')
 profiles.mockResolvedValue({success:true,data:{items:[{id:'one',name:'配置一'}] as never,total:1}})
 fireEvent.click(screen.getAllByText('刷新配置')[0])
 await screen.findByRole('option',{name:'所选配置已不可用，请重新选择'})
 expect(useGlobalConfigStore.getState().config.browserProfileId).toBe('two')
})
it('shows empty and failed management responses without inventing profiles',async()=>{
 const profiles=vi.spyOn(browserApi,'profiles').mockResolvedValue({success:true,data:{items:[],total:0}})
 render(<BrowserProfileSelect/>)
 await screen.findByRole('option',{name:'暂无配置，请在管理端创建'})
 expect(useGlobalConfigStore.getState().config.browserProfileId).toBe('')
 profiles.mockResolvedValue({success:false,error:'管理服务离线'})
 fireEvent.click(screen.getByText('刷新配置'))
 expect((await screen.findByRole('alert')).textContent).toBe('管理服务离线')
})
