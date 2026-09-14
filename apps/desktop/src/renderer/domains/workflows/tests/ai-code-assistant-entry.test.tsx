import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{
 const data=new Map<string,string>()
 vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
 Object.defineProperty(window,'innerWidth',{configurable:true,value:1440})
})
// Only Monaco's rendering is substituted; editor dialogs, assistant, request seam and Store are real.
vi.mock('@monaco-editor/react',()=>({default:({value,onChange}:{value:string;onChange:(value:string)=>void})=><textarea aria-label="代码审查草稿" value={value} onChange={event=>onChange(event.target.value)}/>,loader:{config:vi.fn(),init:vi.fn(async()=>{})}}))
vi.mock('monaco-editor',()=>({}))
import {ConfigPanel} from '../components/ConfigPanel'
import {useWorkflowStore as store} from '../editor-store'
import {useGlobalConfigStore as config} from '../hooks/stores/globalConfigStore'
import {configureStudioConnection} from '../api/config'
import {mockRequest} from '../api/mock-server'
const initialConfig=structuredClone(config.getState().config)
const entries=[['inject_javascript','javascriptCode'],['js_script','code'],['python_script','scriptContent']] as const
const url='http://ai-code.test/api/generate'
let respond:()=>Response
let requests:Array<{body:Record<string,unknown>;headers:Headers}>
let restore:()=>void
beforeEach(()=>{
 config.setState({config:structuredClone(initialConfig)})
 config.getState().updateAIConfig({apiUrl:url,apiKey:'fixture-key',model:'fixture-model',temperature:0.3,maxTokens:1234,models:[],autoFallback:false})
 store.getState().clearWorkflow();requests=[]
 respond=()=>Response.json({choices:[{message:{content:'```javascript\nfunction main(vars) { return 7 }\n```'}}]})
 restore=configureStudioConnection('http://ai-code.test',async(input,init)=>{
  if(String(input)===url){requests.push({body:JSON.parse(String(init?.body)),headers:new Headers(init?.headers)});return respond()}
  return mockRequest(input,init)
 })
})
afterEach(()=>{cleanup();restore();config.setState({config:structuredClone(initialConfig)})})
async function open(type:typeof entries[number][0]='js_script',field:typeof entries[number][1]='code'){
 store.getState().addNode(type,{x:0,y:0})
 const id=store.getState().nodes.find(node=>node.data.moduleType===type)!.id
 store.getState().updateNodeData(id,{[field]:'原始代码'})
 render(<ConfigPanel selectedNodeId={id}/>)
 fireEvent.click(screen.getByText('打开代码编辑器'))
 await screen.findByLabelText('代码审查草稿')
 fireEvent.click(screen.getByTitle('使用AI生成代码'))
 return id
}
function generate(){
 fireEvent.change(screen.getByPlaceholderText(/^例如：/),{target:{value:'返回数字7'}})
 fireEvent.click(screen.getByRole('button',{name:'生成代码'}))
}
const node=(id:string)=>store.getState().nodes.find(item=>item.id===id)!.data
it.each(entries)('NODE.%s.ai-code.entry: generates into a review draft and saves only after explicit editing approval',async(type,field)=>{
 const generated=type==='python_script'?'return 7':'function main(vars) { return 7 }'
 respond=()=>Response.json({choices:[{message:{content:'```'+(type==='python_script'?'python':'javascript')+'\n'+generated+'\n```'}}]})
 const id=await open(type,field)
 generate()
 await waitFor(()=>expect((screen.getByLabelText('代码审查草稿') as HTMLTextAreaElement).value).toBe(generated))
 expect(node(id)[field]).toBe('原始代码')
 expect(requests[0].body).toMatchObject({model:'fixture-model',temperature:0.3,max_tokens:1234,stream:false})
 expect(requests[0].headers.get('Authorization')).toBe('Bearer fixture-key')
 expect(requests[0].body.messages).toEqual([expect.objectContaining({role:'system',content:expect.stringContaining(type==='python_script'?'Python':'JavaScript')}),{role:'user',content:'返回数字7'}])
 const reviewed=type==='python_script'?'return 8':'function main(vars) { return 8 }'
 fireEvent.change(screen.getByLabelText('代码审查草稿'),{target:{value:reviewed}})
 fireEvent.click(screen.getByRole('button',{name:/^保存$/}))
 expect(node(id)[field]).toBe(reviewed)
 expect(screen.queryByLabelText('代码审查草稿')).toBeNull()
})
it('TOOL.ai-code.cancel: cancelling the prompt sends nothing and discarding generated code does not change the node',async()=>{
 const id=await open()
 fireEvent.click(screen.getAllByRole('button',{name:/^取消$/}).at(-1)!)
 expect(requests).toHaveLength(0);expect(node(id).code).toBe('原始代码')
 fireEvent.click(screen.getByTitle('使用AI生成代码'));generate()
 await waitFor(()=>expect((screen.getByLabelText('代码审查草稿') as HTMLTextAreaElement).value).toContain('return 7'))
 fireEvent.click(screen.getByRole('button',{name:/^取消$/}))
 expect(node(id).code).toBe('原始代码')
})
it('TOOL.ai-code.rejection: shows a service error, preserves the draft and permits an explicit retry',async()=>{
 respond=()=>new Response('fixture rejection',{status:503})
 const id=await open();generate()
 await screen.findByText(/API请求失败 \(503\)/)
 expect(node(id).code).toBe('原始代码');expect((screen.getByLabelText('代码审查草稿') as HTMLTextAreaElement).value).toBe('原始代码')
 respond=()=>Response.json({message:{content:'return 9'}})
 fireEvent.click(screen.getByRole('button',{name:'生成代码'}))
 await waitFor(()=>expect((screen.getByLabelText('代码审查草稿') as HTMLTextAreaElement).value).toBe('return 9'))
 expect(requests).toHaveLength(2);expect(node(id).code).toBe('原始代码')
})
it('TOOL.ai-code.missing-model: rejects missing configuration before making a request',async()=>{
 config.getState().updateAIConfig({model:''})
 await open();generate();await screen.findByText('请先在全局配置中设置AI模型')
 expect(requests).toHaveLength(0)
})
it('TOOL.ai-code.zero-temperature: preserves an explicitly configured zero',async()=>{
 config.getState().updateAIConfig({temperature:0})
 await open();generate()
 await waitFor(()=>expect(requests).toHaveLength(1))
 expect(requests[0].body.temperature).toBe(0)
})
it('TOOL.ai-code.ndjson: reads Ollama NDJSON once and assembles code until done',async()=>{
 respond=()=>new Response('{"message":{"content":"return "}}\n{"message":{"content":"11"},"done":true}\n{"message":{"content":"ignored"}}\n',{headers:{'Content-Type':'application/x-ndjson'}})
 const id=await open();generate()
 await waitFor(()=>expect((screen.getByLabelText('代码审查草稿') as HTMLTextAreaElement).value).toBe('return 11'))
 expect(node(id).code).toBe('原始代码')
})
