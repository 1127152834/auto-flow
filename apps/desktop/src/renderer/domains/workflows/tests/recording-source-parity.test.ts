import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {expect,it} from 'vitest'
import {buildRecordedNodes,type RecEvent} from '../lib/recordingGeneration'
import {moduleTypeLabels} from '../editor-store'
const frozen=readFileSync('../../reference/WebRPA/frontend/src/components/workflow/RecorderPanel.tsx','utf8')
const start=frozen.indexOf('    const newNodes: any[] = []')
const end=frozen.indexOf('    if (!newNodes.length)',start)
if(start<0||end<0)throw Error('Frozen recorder converter boundaries changed')
const source=ts.transpile(`${frozen.slice(start,end)};return {nodes:newNodes,edges:newEdges}`,{target:ts.ScriptTarget.ES2022})
const convert=new Function('evs','autoWait','nanoid','moduleTypeLabels',source)
const cases:RecEvent[][]=[
 [{type:'navigate',url:'https://local.test/start'}],
 [{type:'click',selector:'#go',text:'button'}],
 [{type:'dblclick',selector:'#go',hints:{id:'go'}}],
 [{type:'input',selector:'#name',value:'中文 {原文}\n行'}],
 [{type:'select',selector:'#select',value:'one'}],
 [{type:'select',selector:'#select',values:['one','two']}],
 [{type:'check',selector:'#box',value:false}],
 [{type:'drag',selector:'#from',targetSelector:'#to'}],
 [{type:'drag',selector:'#slider',endX:100,endY:50}],
 [{type:'upload',selector:'#upload',fileName:'fixture.txt'}],
 [{type:'scroll',dy:-450}],
 [{type:'keypress',key:'Enter',selector:'#input'}],
 [{type:'click',selector:'#frame',_frame:{selector:'iframe#one'}},{type:'click',selector:'#main',_frame:{main:true}}],
 [{type:'click',selector:'#frame',_frame:{name:'named'}},{type:'click',selector:'#other',_frame:{index:2}}],
 [{type:'navigate',url:'https://local.test/a',ts:1},{type:'click',selector:'#next',ts:100},{type:'navigate',url:'https://local.test/b',ts:500},{type:'navigate',url:'https://local.test/c',ts:11000}],
 [{type:'navigate',url:'about:blank'},{type:'navigate',url:'https://local.test',_frame:{name:'child'}}],
]
it.each(cases.map((events,index)=>({events,index})))('F4.2 source conversion $index preserves source node fields and edge order',({events})=>{
 for(const autoWait of [true,false]){
  let index=0
  const expected=convert(events,autoWait,()=>`source-${index++}`,moduleTypeLabels)
  const actual=buildRecordedNodes(events,autoWait)
  expect(actual.nodes.map(node=>({data:node.data,position:node.position}))).toEqual(expected.nodes.map((node:{data:unknown;position:unknown})=>({data:node.data,position:node.position})))
  expect(actual.edges.map(edge=>[actual.nodes.findIndex(node=>node.id===edge.source),actual.nodes.findIndex(node=>node.id===edge.target)])).toEqual(expected.edges.map((edge:{source:string;target:string})=>[expected.nodes.findIndex((node:{id:string})=>node.id===edge.source),expected.nodes.findIndex((node:{id:string})=>node.id===edge.target)]))
 }
})
it('applies only explicit review overrides for navigation, variables and upload paths',()=>{
 const result=buildRecordedNodes([{type:'navigate',url:'https://local.test',navigation:'ignore'},{type:'input',selector:'#name',value:'literal',variableName:'name'},{type:'upload',selector:'#file',filePath:'/fixture.txt'},{type:'navigate',url:'https://local.test/next',navigation:'open'}],false)
 expect(result.nodes.map(node=>node.data.moduleType)).toEqual(['input_text','upload_file','open_page'])
 expect(result.nodes[0].data.text).toBe('{name}');expect(result.nodes[1].data.filePath).toBe('/fixture.txt')
})
