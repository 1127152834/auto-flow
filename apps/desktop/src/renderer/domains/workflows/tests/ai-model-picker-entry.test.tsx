import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{
 const data=new Map<string,string>()
 vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
 Object.defineProperty(window,'innerWidth',{configurable:true,value:1440})
})
import type {ModuleType} from '../types'
import {ConfigPanel} from '../components/ConfigPanel'
import {useWorkflowStore as store} from '../editor-store'
import {useGlobalConfigStore as config,type AIModelProfile} from '../hooks/stores/globalConfigStore'
const initialConfig=structuredClone(config.getState().config)
const originalScroll=Object.getOwnPropertyDescriptor(HTMLElement.prototype,'scrollIntoView')
const primary:AIModelProfile={id:'primary',label:'主模型',apiUrl:'https://model-a.invalid/v1/chat/completions',apiKey:'fixture-key-a',model:'model-a',temperature:0,maxTokens:1234}
const secondary:AIModelProfile={id:'secondary',label:'备用模型',apiUrl:'https://model-b.invalid/v1/chat/completions',apiKey:'fixture-key-b',model:'model-b',temperature:0.4,maxTokens:2345}
beforeEach(()=>{
 config.setState({config:structuredClone(initialConfig)})
 config.getState().updateAIConfig({models:[primary,secondary],autoFallback:false})
 store.getState().clearWorkflow()
 Object.defineProperty(HTMLElement.prototype,'scrollIntoView',{configurable:true,value:vi.fn()})
})
afterEach(()=>{
 cleanup();config.setState({config:structuredClone(initialConfig)})
 if(originalScroll)Object.defineProperty(HTMLElement.prototype,'scrollIntoView',originalScroll)
 else Reflect.deleteProperty(HTMLElement.prototype,'scrollIntoView')
})
function create(type:ModuleType){
 store.getState().addNode(type,{x:120,y:240})
 return store.getState().nodes.find(node=>node.data.moduleType===type)!.id
}
const data=(id:string)=>store.getState().nodes.find(node=>node.id===id)!.data
const picker=()=>within(screen.getByText('从已配置模型选择').parentElement!).getByRole('combobox')
async function choose(label:RegExp){
 fireEvent.keyDown(picker(),{key:'ArrowDown'})
 fireEvent.click(await screen.findByRole('option',{name:label}))
}
it.each(['ai_chat','ai_vision','ai_vision_act','ai_route'] as const)('NODE.%s.model-picker.entry: writes the chosen profile only to this node and preserves it on document reopen',async type=>{
 const id=create(type)
 store.getState().addNode(type,{x:400,y:240})
 const other=store.getState().nodes.find(node=>node.data.moduleType===type&&node.id!==id)!
 const otherBefore=structuredClone(other.data)
 render(<ConfigPanel selectedNodeId={id}/>)
 await choose(/主模型/)
 expect(data(id)).toMatchObject({apiUrl:primary.apiUrl,apiKey:primary.apiKey,model:primary.model,temperature:0,maxTokens:1234})
 expect(data(other.id)).toEqual(otherBefore)
 expect(picker().textContent).toContain('主模型')
 const content=store.getState().exportWorkflow()
 cleanup()
 act(()=>{store.getState().clearWorkflow();expect(store.getState().importWorkflow(content)).toBe(true)})
 render(<ConfigPanel selectedNodeId={id}/>)
 expect(picker().textContent).toContain('主模型')
 expect(data(id)).toMatchObject({apiUrl:primary.apiUrl,apiKey:primary.apiKey,model:primary.model,temperature:0,maxTokens:1234})
})
it('TOOL.ai-model-picker.empty: keeps manual model fields when no profiles exist',()=>{
 config.getState().updateAIConfig({models:[]})
 const id=create('ai_chat')
 store.getState().updateNodeData(id,{apiUrl:'https://manual.invalid',apiKey:'manual-fixture',model:'manual-model',temperature:0.3,maxTokens:321})
 render(<ConfigPanel selectedNodeId={id}/>)
 expect(screen.queryByText('从已配置模型选择')).toBeNull()
 expect(data(id)).toMatchObject({apiUrl:'https://manual.invalid',apiKey:'manual-fixture',model:'manual-model',temperature:0.3,maxTokens:321})
})
it('TOOL.ai-model-picker.fallback: retains ordered valid alternatives, excludes the current identity and clears when disabled',async()=>{
 const sameIdentity={...primary,id:'same-identity',apiKey:'different-fixture-key'}
 const third={...secondary,id:'third',apiUrl:'https://model-c.invalid',model:'model-c'}
 config.getState().updateAIConfig({models:[primary,sameIdentity,secondary,{...secondary,id:'incomplete',model:''},third],autoFallback:true})
 const id=create('ai_chat')
 store.getState().updateNodeData(id,{apiUrl:primary.apiUrl,model:primary.model})
 render(<ConfigPanel selectedNodeId={id}/>)
 const expected=[secondary,third].map(({apiUrl,apiKey,model,temperature,maxTokens})=>({apiUrl,apiKey,model,temperature,maxTokens}))
 await waitFor(()=>expect(data(id).fallbackModels).toEqual(expected))
 act(()=>config.getState().updateAIConfig({autoFallback:false}))
 await waitFor(()=>expect(data(id).fallbackModels).toBeUndefined())
 expect(data(id)).toMatchObject({apiUrl:primary.apiUrl,model:primary.model})
})
it('TOOL.ai-model-picker.removed-profile: shows manual selection without erasing previously chosen node fields',async()=>{
 const id=create('ai_chat');render(<ConfigPanel selectedNodeId={id}/>)
 await choose(/主模型/)
 act(()=>config.getState().updateAIConfig({models:[secondary]}))
 expect(picker().textContent).toContain('手动填写')
 expect(data(id)).toMatchObject({apiUrl:primary.apiUrl,apiKey:primary.apiKey,model:primary.model,temperature:0,maxTokens:1234})
})
it('TOOL.ai-model-picker.optional: an unspecified temperature or token limit does not overwrite the node values',async()=>{
 config.getState().updateAIConfig({models:[{...secondary,temperature:undefined,maxTokens:undefined}]})
 const id=create('ai_chat');store.getState().updateNodeData(id,{temperature:0.2,maxTokens:765})
 render(<ConfigPanel selectedNodeId={id}/>)
 await choose(/备用模型/)
 expect(data(id)).toMatchObject({apiUrl:secondary.apiUrl,apiKey:secondary.apiKey,model:secondary.model,temperature:0.2,maxTokens:765})
})
