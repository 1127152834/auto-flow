import {beforeEach} from 'vitest'
import {selectBrowserNode} from './select-browser-node'
beforeEach(()=>selectBrowserNode('managed'))
import {afterEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
import {browserApi,currentBrowserSession,elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {useGlobalConfigStore} from '../hooks/stores/globalConfigStore'
afterEach(()=>{useGlobalConfigStore.getState().setBrowserProfileId('');vi.restoreAllMocks()})
it('uses managed profile identity and never forwards legacy launch settings',async()=>{
 const sent:Array<{path:string;body:Record<string,unknown>}>=[]
 let open=false
 const restore=configureStudioConnection('http://profile.test',async(input,init)=>{
  const path=new URL(String(input)).pathname
  const body=JSON.parse(String(init?.body||'{}'))
  if(path.endsWith('/profiles'))return Response.json({items:[{id:'managed',name:'管理端配置'}],total:1})
  if(path.endsWith('/status'))return Response.json({isOpen:open,pickerActive:false,sessionId:'browser',profileId:'managed'})
  sent.push({path,body});open=!path.endsWith('/close')
  return Response.json(path.endsWith('/start')?{success:true,sessionId:body.sessionId,active:true}:{success:true})
 })
 try{
  expect((await browserApi.open('https://local.test',{browserType:'chrome',chromePath:'/old'})).success).toBe(true)
  useGlobalConfigStore.getState().setBrowserProfileId('deleted')
  expect((await elementPickerApi.start(undefined,{browserType:'edge'})).success).toBe(true)
  expect(sent[0].body).toEqual({url:'https://local.test',profileId:'managed',browserEnvironment:{source:'newFromProfile',profileId:'managed'}})
  expect(sent.find(item=>item.path.endsWith('/start'))?.body).toEqual({sessionId:expect.any(String),url:null,profileId:'managed'})
 }finally{restore()}
})
it('holds startup occupancy during profile lookup and releases it when lookup fails',async()=>{
 let finish!:(value:Response)=>void
 const sent:string[]=[]
 const restore=configureStudioConnection('http://profile-pending.test',async input=>{
  const path=new URL(String(input)).pathname;sent.push(path)
  return new Promise<Response>(resolve=>{finish=resolve})
 })
 try{
  const pending=browserApi.open()
  expect(currentBrowserSession()).toBeTruthy()
  expect((await browserApi.close()).success).toBe(false)
  expect(sent).toHaveLength(1)
  finish(Response.json({items:[],total:0}))
  expect(await pending).toMatchObject({success:false,error:'所选模板不存在或已不可用，请在节点重新选择'})
  expect(currentBrowserSession()).toBeNull()
 }finally{restore()}
})
it('does not silently replace a deleted node template',async()=>{
 selectBrowserNode('deleted')
 useGlobalConfigStore.getState().setBrowserProfileId('deleted')
 const post=vi.fn()
 const restore=configureStudioConnection('http://deleted-profile.test',async(_input,init)=>{
  if(init?.method==='POST')post()
  return Response.json({items:[{id:'other',name:'其他配置'}],total:1})
 })
 try{
  expect(await browserApi.open()).toMatchObject({success:false,httpStatus:404})
  expect(post).not.toHaveBeenCalled()
  expect(currentBrowserSession()).toBeNull()
 }finally{restore()}
})
