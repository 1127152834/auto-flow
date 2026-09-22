import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'

describe('workflow document write identity',()=>{
  let restore:()=>void
  beforeEach(async()=>{
    vi.resetModules()
    vi.stubGlobal('crypto',{randomUUID:vi.fn().mockReturnValue('stable-request')})
  })
  afterEach(()=>{restore?.();vi.unstubAllGlobals()})

  it('reuses create request identity after an unknown response',async()=>{
    const bodies:Record<string,unknown>[]=[]
    let attempt=0
    const {configureStudioConnection}=await import('../api/config')
    restore=configureStudioConnection('http://studio.test',async(_input,init)=>{
      bodies.push(JSON.parse(String(init?.body)))
      if(attempt++===0)throw new TypeError('network response lost')
      return Response.json({id:'workflow-1',name:'流程',nodes:[],edges:[],variables:[],revision:1},{status:201})
    })
    const {workflowApi}=await import('../api')

    expect((await workflowApi.create({name:'流程',nodes:[],edges:[],variables:[]})).success).toBe(false)
    expect((await workflowApi.create({name:'流程',nodes:[],edges:[],variables:[]})).success).toBe(true)

    expect(bodies.map(body=>body.clientRequestId)).toEqual(['stable-request','stable-request'])
  })

  it('sends the loaded revision and reuses update identity after response loss',async()=>{
    const writes:Record<string,unknown>[]=[]
    let updateAttempt=0
    const {configureStudioConnection}=await import('../api/config')
    restore=configureStudioConnection('http://studio.test',async(input,init)=>{
      if(init?.method==='PUT'){
        writes.push(JSON.parse(String(init.body)))
        if(updateAttempt++===0)throw new TypeError('network response lost')
        return Response.json({id:'workflow-1',name:'新名称',nodes:[],edges:[],variables:[],revision:8})
      }
      expect(String(input)).toContain('/api/workflows/workflow-1')
      return Response.json({id:'workflow-1',name:'流程',nodes:[],edges:[],variables:[],revision:7})
    })
    const {workflowApi}=await import('../api')
    await workflowApi.get('workflow-1')

    expect((await workflowApi.update('workflow-1',{name:'新名称',nodes:[],edges:[],variables:[]})).success).toBe(false)
    expect((await workflowApi.update('workflow-1',{name:'新名称',nodes:[],edges:[],variables:[]})).success).toBe(true)

    expect(writes.map(body=>body.expectedRevision)).toEqual([7,7])
    expect(writes.map(body=>body.clientRequestId)).toEqual(['stable-request','stable-request'])
  })

  it('does not turn a concurrent update conflict into an implicit overwrite',async()=>{
    const writes:Record<string,unknown>[]=[]
    let attempt=0
    const {configureStudioConnection}=await import('../api/config')
    restore=configureStudioConnection('http://studio.test',async(_input,init)=>{
      const body=JSON.parse(String(init?.body))
      writes.push(body)
      if(attempt++===0){
        return Response.json({error:{code:'WORKFLOW_REVISION_CONFLICT',message:'流程已被其他窗口修改',details:{expectedRevision:1,currentRevision:4},requestId:'conflict'}},{status:409})
      }
      return Response.json({id:'workflow-1',name:'新名称',nodes:[],edges:[],variables:[],revision:5})
    })
    const {workflowApi}=await import('../api')

    expect((await workflowApi.update('workflow-1',{name:'新名称',nodes:[],edges:[],variables:[]})).httpStatus).toBe(409)
    expect((await workflowApi.update('workflow-1',{name:'新名称',nodes:[],edges:[],variables:[]})).success).toBe(true)

    expect(writes.map(body=>body.expectedRevision)).toEqual([1,1])
  })

  it('propagates the project scope for Studio documents', async () => {
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    const requests: string[] = []
    const bodies: Record<string, unknown>[] = []
    const { configureStudioConnection } = await import('../api/config')
    restore = configureStudioConnection('http://studio.test', async (input, init) => {
      requests.push(String(input))
      if (init?.body) bodies.push(JSON.parse(String(init.body)))
      return String(input).includes('/api/workflows?')
        ? Response.json([])
        : Response.json({ id: 'workflow-1', name: '流程', nodes: [], edges: [], variables: [], revision: 1 })
    })
    const { workflowApi } = await import('../api')
    await workflowApi.list()
    await workflowApi.create({ name: '流程', nodes: [], edges: [], variables: [] })
    expect(requests[0]).toContain('/api/workflows?projectId=project-a')
    expect(bodies[0]?.projectId).toBe('project-a')
  })
})
