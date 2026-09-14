import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { parseServerSentEvents } from '../../../shared/api/events'
let server: typeof import('../api/mock-server')
const aborts: AbortController[]=[]
const request=(path:string,body?:unknown,method=body===undefined?'GET':'POST')=>server.mockRequest('http://autoflow-studio.mock/api'+path,{method,...(body===undefined?{}:{body:JSON.stringify(body)})})
beforeEach(async()=>{
  const data=new Map<string,string>()
  vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key),clear:()=>data.clear()})
  vi.resetModules();server=await import('../api/mock-server')
})
afterEach(async()=>{aborts.splice(0).forEach(c=>c.abort());await request('/workflows/any/stop',{},'POST');server.configureMock({offline:false,disconnect:true});vi.useRealTimers();vi.unstubAllGlobals()})
describe('source-compatible mock HTTP boundary',()=>{
  it('saves exact source document content and reopens it, with observable save failure',async()=>{
    const content={name:'roundtrip',nodes:[{id:'a',type:'input_text',data:{text:'{literal}'},position:{x:120,y:90}}],edges:[],variables:[{name:'v',value:[1,2]}]}
    expect((await request('/local-workflows/save-to-folder',{filename:'roundtrip',content})).ok).toBe(true)
    const saved=await (await request('/local-workflows/load/roundtrip.json')).json()
    expect(saved.content).toEqual(content)
    server.configureMock({failNextSave:true})
    expect((await request('/local-workflows/save-to-folder',{filename:'roundtrip',content:{...content,name:'lost'}})).status).toBe(507)
    expect((await (await request('/local-workflows/load/roundtrip.json')).json()).content.name).toBe('roundtrip')
    const list=await (await request('/local-workflows/list',{})).json();expect(list.workflows).toHaveLength(1)
  })
  it('does not overwrite saved files with a stale renderer settings snapshot',async()=>{
    vi.resetModules()
    const peer=await import('../api/mock-server')
    await request('/local-workflows/save-to-folder',{filename:'keep',content:{nodes:[],name:'keep'}})
    await peer.mockRequest('http://autoflow-studio.mock/api/local-workflows/active-folder',{method:'POST',body:JSON.stringify({folder:''})})
    expect((await request('/local-workflows/load/keep.json')).ok).toBe(true)
  })
  it('treats the source empty active folder as default and isolates same-named files by folder', async()=>{
    await request('/local-workflows/active-folder',{folder:''})
    expect((await(await request('/local-workflows/default-folder')).json()).folder).toBe('mock://AutoFlow/workflows')
    for(const folder of ['mock://A','mock://B'])await request('/local-workflows/save-to-folder',{filename:'same',content:{name:folder,nodes:[],_folder:folder}})
    expect((await(await request('/local-workflows/load/same.json?folder=mock%3A%2F%2FA')).json()).content.name).toBe('mock://A')
    expect((await(await request('/local-workflows/list',{folder:'mock://B'})).json()).workflows).toHaveLength(1)
  })
  it('round-trips source bundles, settings and masked credential metadata',async()=>{
    await request('/system/browser-config',{config:{language:'zh-CN'}})
    expect((await(await request('/system/browser-config')).json()).config.language).toBe('zh-CN')
    await request('/credentials',{name:'test',fields:{token:'never-store-this'}})
    expect(JSON.stringify(await(await request('/credentials')).json())).not.toContain('never-store-this')
    const module=await(await request('/custom-modules',{name:'bundle-module'})).json()
    const content={nodes:[{id:'n',type:'custom_module',data:{customModuleId:module.id}}],edges:[],variables:[]}
    const exported=await(await request('/workflow-bundle/export',{name:'bundle',content})).json()
    expect(exported.bundle.customModules).toHaveLength(1)
    const imported=await(await request('/workflow-bundle/import',{bundle:exported.bundle})).json()
    expect(imported.workflow).toEqual(content)
    expect((await request('/workflow-bundle/import',{bundle:{}})).status).toBe(400)
  })
  it('emits one failed completion and no success for an injected node failure',async()=>{
    vi.useFakeTimers()
    const doc=await(await request('/workflows',{nodes:[{id:'fail',type:'click_element'}],variables:[]})).json()
    server.configureMock({failNextRun:true})
    await request(`/workflows/${doc.id}/execute`,{})
    await vi.advanceTimersByTimeAsync(400)
    const abort=new AbortController();aborts.push(abort)
    const res=await server.mockRequest('http://autoflow-studio.mock/api/events/stream',{signal:abort.signal})
    const iterator=parseServerSentEvents(res.body!)[Symbol.asyncIterator]()
    const completions=[]
    for(let i=0;i<server.mockSnapshot().sequence;i++){const event=(await iterator.next()).value;if(event?.event==='execution:node_complete')completions.push(JSON.parse(event.data))}
    expect(completions).toHaveLength(1)
    expect(completions[0]).toMatchObject({workflowId:doc.id,runId:expect.any(String),nodeId:'fail',success:false})
    expect(server.mockSnapshot().run).toBeNull()
  })
  it('rejects malformed and unknown requests and never reaches a real URL',async()=>{
    expect((await server.mockRequest('http://autoflow-studio.mock/api/workflows',{method:'POST',body:'{broken'})).status).toBe(400)
    expect((await request('/does-not-exist')).status).toBe(501)
    expect((await server.mockRequest('https://example.test/')).status).toBe(403)
    server.configureMock({offline:true});await expect(request('/workflows')).rejects.toThrow(/offline/);server.configureMock({offline:false})
  })
  it('preserves event sequence and replays events produced during a disconnected stream',async()=>{
    server.emitMockEvent('execution:log',{message:'first'})
    const c=new AbortController();aborts.push(c)
    const response=await server.mockRequest('http://autoflow-studio.mock/api/events/stream?afterSeq=0',{signal:c.signal})
    const iterator=parseServerSentEvents(response.body!)[Symbol.asyncIterator]()
    expect((await iterator.next()).value?.id).toBe('1');c.abort();await iterator.return?.(undefined)
    server.emitMockEvent('execution:log',{message:'second'})
    const next=new AbortController();aborts.push(next)
    const replay=await server.mockRequest('http://autoflow-studio.mock/api/events/stream?afterSeq=1',{signal:next.signal})
    const reader=parseServerSentEvents(replay.body!)[Symbol.asyncIterator]()
    const event=(await reader.next()).value;expect(event?.id).toBe('2');expect(JSON.parse(event!.data)).toEqual({message:'second'});next.abort();await reader.return?.(undefined)
  })
  it('deduplicates commands and rejects same ID with changed content',async()=>{
    const command={commandId:'same',event:'set_verbose_log',data:{enabled:true}}
    expect((await request('/events/commands',command)).status).toBe(200)
    expect((await request('/events/commands',command)).status).toBe(200)
    expect((await request('/events/commands',{...command,data:{enabled:false}})).status).toBe(409)
  })
  it('freezes the run fixture, rejects concurrent runs and confirms stop through events',async()=>{
    vi.useFakeTimers()
    const doc=await(await request('/workflows',{name:'debug',nodes:[{id:'n1',type:'open_page',data:{label:'打开网页'}},{id:'n2',type:'click_element',data:{}}],edges:[],variables:[]})).json()
    expect((await request(`/workflows/${doc.id}/execute`,{stepMode:true})).ok).toBe(true)
    expect((await request(`/workflows/${doc.id}/execute`,{})).status).toBe(409)
    await vi.advanceTimersByTimeAsync(30)
    expect(server.mockSnapshot().run).toBe(doc.id)
    const firstPause=server.mockSnapshot().pause
    expect((await request(`/workflows/${doc.id}/debug/step`,{commandId:'first-step',...firstPause})).ok).toBe(true)
    expect((await request(`/workflows/${doc.id}/debug/step`,{commandId:'duplicate-click',...firstPause})).status).toBe(409)
    await vi.advanceTimersByTimeAsync(300)
    expect((await request(`/workflows/${doc.id}/debug/step`,{commandId:'next-step',...server.mockSnapshot().pause})).ok).toBe(true)
    await request(`/workflows/${doc.id}/stop`,{})
    const sequence=server.mockSnapshot().sequence
    await vi.advanceTimersByTimeAsync(2000)
    expect(server.mockSnapshot().run).toBe(null);expect(server.mockSnapshot().sequence).toBe(sequence)
  })
  it('feeds the non-destructive recorder protocol and requires an available browser',async()=>{
    expect((await request('/recorder/start',{sessionId:'recording'})).status).toBe(409)
    await request('/browser/open',{url:'about:blank'});await request('/recorder/start',{sessionId:'recording'})
    server.addMockRecordingEvent({type:'input',selector:'#name',value:'中文'})
    expect((await(await request('/recorder/events?sessionId=recording')).json()).data[0]).toMatchObject({value:'中文'})
    expect((await(await request('/recorder/events?sessionId=recording')).json()).data[0]).toMatchObject({value:'中文',sequence:1})
    expect((await(await request('/recorder/events?sessionId=recording&afterSeq=1')).json()).data).toEqual([])
    server.addMockRecordingEvent({type:'click',selector:'#submit'})
    expect((await(await request('/recorder/stop',{sessionId:'recording',afterSeq:1})).json()).data.events).toHaveLength(1)
    expect(server.mockSnapshot().recording).toBe(false)
  })
  it('persists custom modules and mutable resource folders through the same request seam',async()=>{
    const created=await(await request('/custom-modules',{name:'snippet',parameters:[],workflow:{nodes:[],edges:[]}})).json()
    expect((await(await request('/custom-modules')).json()).modules[0].id).toBe(created.id)
    await request(`/custom-modules/${created.id}`,{...created,name:'renamed'},'PUT')
    expect((await(await request(`/custom-modules/${created.id}`)).json()).name).toBe('renamed')
    await request('/image-assets/folders',{name:'screenshots'})
    expect(await(await request('/image-assets/folders')).json()).toEqual(['screenshots'])
    expect(await(await request('/image-assets')).json()).toEqual([])
  })
})

it('keeps excluded legacy configuration readable but refuses to run it', async () => {
  const content = { id: 'legacy', name: 'Legacy', nodes: [{ id: 'old', type: 'excel_create', data: { path: '/original.xlsx', custom: 'preserve' } }], edges: [] }
  expect((await request('/workflows', content)).ok).toBe(true)
  expect(await (await request('/workflows/legacy')).json()).toMatchObject(content)
  expect((await request('/workflows/legacy/execute', {})).status).toBe(422)
  expect(server.mockSnapshot().run).toBe(null)
  expect(await (await request('/workflows/legacy')).json()).toMatchObject(content)
})

it('rejects removed Excel resource operations without deleting existing stored data or disabling image resources', async () => {
  const previous = JSON.stringify({ assets: [{ id: 'legacy', dataUrl: 'data:application/octet-stream;base64,YQ==' }], folders: ['old'] })
  localStorage.setItem('autoflow:studio:mock:data-assets', previous)
  for (const [path, method] of [['/data-assets', 'GET'], ['/data-assets/upload', 'POST'], ['/data-assets/legacy', 'DELETE']]) {
    expect((await request(path, method === 'GET' ? undefined : {}, method)).status).toBe(410)
  }
  expect(localStorage.getItem('autoflow:studio:mock:data-assets')).toBe(previous)
  expect((await request('/image-assets/folders', { name: 'retained' })).ok).toBe(true)
  expect(await (await request('/image-assets/folders')).json()).toEqual(['retained'])
})

it('rejects excluded nodes inside nested custom modules without changing the module or workflow', async () => {
  const inner = { id: 'inner', name: 'old', workflow: { nodes: [{ id: 'excel', type: 'excel_create', data: { path: '/preserve.xlsx' } }], edges: [] } }
  await request('/custom-modules', inner)
  await request('/custom-modules', { id: 'outer', workflow: { nodes: [{ id: 'nested', type: 'custom_module', data: { customModuleId: 'inner' } }] } })
  const doc = { id: 'nested-legacy', nodes: [{ id: 'call', type: 'moduleNode', data: { moduleType: 'custom_module', customModuleId: 'outer' } }], edges: [] }
  await request('/workflows', doc)
  expect((await request('/workflows/nested-legacy/execute', {})).status).toBe(422)
  expect(server.mockSnapshot().run).toBe(null)
  expect(await (await request('/custom-modules/inner')).json()).toMatchObject(inner)
  expect(await (await request('/workflows/nested-legacy')).json()).toMatchObject(doc)
})
