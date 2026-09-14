import {useEffect} from 'react'
import type { Monaco } from '@monaco-editor/react'
import type { editor, languages, Position, CancellationToken } from 'monaco-editor'
import {act,cleanup,render} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
const harness=vi.hoisted(()=>{
 const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
 return {editors:[] as editor.IStandaloneCodeEditor[],registrations:[] as Array<{language:string;provider:languages.CompletionItemProvider;dispose:ReturnType<typeof vi.fn>}>}
})
vi.mock('@monaco-editor/react',()=>({
 default:({onMount}:{onMount:(editor:editor.IStandaloneCodeEditor,monaco:Monaco)=>void})=>{
  useEffect(()=>{
   const callbacks:Array<()=>void>=[]
   const model={getWordUntilPosition:()=>({startColumn:1,endColumn:2})}
   const editor={getModel:()=>model,focus:vi.fn(),onDidDispose:(callback:()=>void)=>{callbacks.push(callback);return {dispose:vi.fn()}}}
   harness.editors.push(editor as unknown as editor.IStandaloneCodeEditor)
   onMount(editor as unknown as editor.IStandaloneCodeEditor,{languages:{CompletionItemKind:{Variable:1,Property:2,Function:3,Snippet:4},CompletionItemInsertTextRule:{InsertAsSnippet:4},registerCompletionItemProvider:(language:string,provider:languages.CompletionItemProvider)=>{const dispose=vi.fn();harness.registrations.push({language,provider,dispose});return{dispose}}}})
   return ()=>{for(const callback of callbacks)callback()}
  },[])
  return <div>代码编辑器</div>
 },loader:{config:vi.fn(),init:vi.fn(async()=>{})},
}))
vi.mock('monaco-editor',()=>({}))
vi.mock('../components/AICodeAssistant',()=>({AICodeAssistant:()=>null}))
import {JsEditorDialog} from '../components/JsEditorDialog'
import {InjectJsEditorDialog} from '../components/InjectJsEditorDialog'
import {PythonEditorDialog} from '../components/PythonEditorDialog'
import {useWorkflowStore} from '../editor-store'
const dialogs=[['JavaScript',JsEditorDialog],['页面注入',InjectJsEditorDialog],['Python',PythonEditorDialog]] as const
beforeEach(()=>{harness.editors.length=0;harness.registrations.length=0})
afterEach(cleanup)
it.each(dialogs)('%s completion suggestions are confined to their own editor model',async(_name,Dialog)=>{
 render(<Dialog isOpen code="test" onClose={vi.fn()} onSave={vi.fn()}/>)
 const {provider}=harness.registrations[0];const position={lineNumber:1,column:2} as Position
 const result=await provider.provideCompletionItems(harness.editors[0].getModel()!,position,{} as languages.CompletionContext,{} as CancellationToken)
 expect(result?.suggestions.length).toBeGreaterThan(0)
 const foreign={getWordUntilPosition:()=>({startColumn:1,endColumn:2})}
 expect(await provider.provideCompletionItems(foreign as unknown as editor.ITextModel,position,{} as languages.CompletionContext,{} as CancellationToken)).toEqual({suggestions:[]})
})
it.each(dialogs)('%s releases completions on close and reopening does not retain earlier providers',(_name,Dialog)=>{
 const props={code:'test',onClose:vi.fn(),onSave:vi.fn()}
 const view=render(<Dialog {...props} isOpen/>);const first=harness.registrations[0]
 view.rerender(<Dialog {...props} isOpen={false}/>);expect(first.dispose).toHaveBeenCalledOnce()
 view.rerender(<Dialog {...props} isOpen/>);expect(harness.registrations).toHaveLength(2);const second=harness.registrations[1];expect(second.dispose).not.toHaveBeenCalled()
 view.unmount();expect(first.dispose).toHaveBeenCalledOnce();expect(second.dispose).toHaveBeenCalledOnce()
})

it.each(dialogs.slice(0,2))('%s uses current variable names and output names without remounting',async(_name,Dialog)=>{
 const previous=useWorkflowStore.getState()
 useWorkflowStore.setState({variables:[{name:'before',type:'string',scope:'global',value:'text'}],nodes:[]})
 const read=async()=>{
  const result=await harness.registrations[0].provider.provideCompletionItems(harness.editors[0].getModel()!,{lineNumber:1,column:2} as Position,{} as languages.CompletionContext,{} as CancellationToken)
  return result?.suggestions.map(item=>item.label)
 }
 try{
  render(<Dialog isOpen code="test" onClose={vi.fn()} onSave={vi.fn()}/>)
  expect(await read()).toContain('vars.before')
  act(()=>{
   useWorkflowStore.setState({variables:[{name:'after',type:'string',scope:'global',value:'text'}]})
   useWorkflowStore.getState().addNode('get_element_info',{x:0,y:0},{variableName:'new_output'})
  })
  expect(await read()).toContain('vars.after')
  expect(await read()).toContain('vars.new_output')
  expect(await read()).not.toContain('vars.before')
  act(()=>useWorkflowStore.setState({variables:[],nodes:[]}))
  expect(await read()).not.toContain('vars.after')
  expect(await read()).not.toContain('vars.new_output')
  expect(harness.registrations).toHaveLength(1)
 }finally{cleanup();useWorkflowStore.setState(previous)}
})
