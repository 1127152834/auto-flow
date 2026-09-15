import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startHttpStudioFixture } from './fixtures/http-studio-server'
import { mockRequest } from '../api/mock-server'

describe.each(['memory', 'http'] as const)('atomic credential field commands: %s', mode => {
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let request: (path: string, init?: RequestInit) => Promise<Response>
  let storage: Map<string, string>
  let failWrite: boolean
  const post = (body: unknown) => ({method:'POST',body:JSON.stringify(body)})
  const list = async () => (await (await request('/credentials')).json()).credentials
  const command = (revision: number, operations: unknown[], commandId = 'stable-command') => ({commandId,name:'vault',expectedRevision:revision,operations})
  beforeEach(async () => {
    storage = new Map(); failWrite = false
    vi.stubGlobal('localStorage', {getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>{if(failWrite)throw new Error('disk full');storage.set(key,value)},removeItem:(key:string)=>storage.delete(key)})
    if (mode === 'http') fixture = await startHttpStudioFixture(mockRequest)
    request = (path, init) => mode === 'http' ? fetch(`${fixture!.origin}/api${path}`,init) : mockRequest(`http://autoflow-studio.mock/api${path}`,init)
    await request('/credentials',post({name:'vault',description:'keep',fields:{value:'dummy-secret',password:'dummy-password',obsolete:'dummy-old'}}))
  })
  afterEach(async () => {await fixture?.close();fixture=undefined;vi.unstubAllGlobals()})

  it('atomically renames and removes metadata, persists one receipt and replays the same command after reload',async()=>{
    const before=(await list())[0]
    const body=command(before.revision,[{kind:'rename',key:'password',newKey:'api_key'},{kind:'remove',key:'obsolete'}])
    const first=await(await request('/credentials/fields',post(body))).json()
    expect(first).toMatchObject({success:true,commandId:body.commandId,credential:{name:'vault',description:'keep',fields:[before.fields[0],{...before.fields[1],key:'api_key'}]}})
    expect(first.credential.revision).toBeGreaterThan(before.revision)
    // State and receipt are loaded from localStorage on every request, including retries.
    expect(await(await request('/credentials/fields',post(body))).json()).toEqual(first)
    expect(await list()).toEqual([first.credential])
    expect([...storage.values()].join('')).not.toMatch(/dummy-secret|dummy-password|dummy-old/)
    expect((await request('/credentials/fields',post({...body,operations:[{kind:'remove',key:'value'}]}))).status).toBe(409)
    expect(await list()).toEqual([first.credential])
  })

  it.each([
    [[{kind:'remove',key:'missing'}],409],
    [[{kind:'rename',key:'password',newKey:'value'}],409],
    [[{kind:'rename',key:'value',newKey:'same'},{kind:'rename',key:'password',newKey:'same'}],409],
    [[{kind:'remove',key:'value'},{kind:'rename',key:'value',newKey:'next'}],409],
    [[{kind:'remove',key:'value'},{kind:'remove',key:'password'},{kind:'remove',key:'obsolete'}],400],
    [[{kind:'rename',key:'value',newKey:'next'},{kind:'remove',key:'missing'}],409],
    [[{kind:'remove',key:'value',secret:'must-not-be-accepted'}],422],
  ])('rejects invalid batches without any partial mutation: %j',async(operations,status)=>{
    const before=await list()
    expect((await request('/credentials/fields',post(command(before[0].revision,operations)))).status).toBe(status)
    expect(await list()).toEqual(before)
  })

  it('detects intervening upsert, rename and delete/recreate through monotonically advancing revisions',async()=>{
    const original=(await list())[0]
    await request('/credentials',post({name:'vault',fields:{value:''}}))
    const upserted=(await list())[0];expect(upserted.revision).toBeGreaterThan(original.revision)
    expect((await request('/credentials/fields',post(command(original.revision,[{kind:'remove',key:'obsolete'}])))).status).toBe(409)
    await request('/credentials/rename',post({old_name:'vault',new_name:'renamed'}))
    const renamed=(await list())[0];expect(renamed.revision).toBeGreaterThan(upserted.revision)
    await request('/credentials/renamed',{method:'DELETE'})
    await request('/credentials',post({name:'vault',fields:{value:''}}))
    expect((await list())[0].revision).toBeGreaterThan(renamed.revision)
    expect((await request('/credentials/fields',post(command(original.revision,[{kind:'remove',key:'value'}])))).status).toBe(409)
  })

  it('leaves both metadata and receipt unchanged after persistence failure, allowing same-ID retry',async()=>{
    const before=await list(), persisted=[...storage.entries()]
    const body=command(before[0].revision,[{kind:'remove',key:'obsolete'}])
    failWrite=true
    expect((await request('/credentials/fields',post(body))).status).toBe(507)
    expect([...storage.entries()]).toEqual(persisted)
    expect(await list()).toEqual(before)
    failWrite=false
    expect((await request('/credentials/fields',post(body))).status).toBe(200)
    expect((await list())[0].fields).toHaveLength(2)
  })

  it('initializes legacy metadata revisions without losing fields and retains literal special names',async()=>{
    storage.set('autoflow:studio:mock:settings:credentials',JSON.stringify({vault:{name:'vault',description:'old',fields:[{key:'value',masked:'old mask'},{key:'__proto__',masked:'other mask'}],created_at:'old',updated_at:'old'}}))
    const old=(await list())[0];expect(old.revision).toBe(1)
    const result=await(await request('/credentials/fields',post(command(1,[{kind:'rename',key:'__proto__',newKey:'constructor'}])))).json()
    expect(result.credential.fields).toEqual([old.fields[0],{key:'constructor',masked:'other mask'}])
    expect(result.credential.created_at).toBe('old')
  })
})

it.each(['wrong-command','missing-revision','unapplied-operation'] as const)('API rejects %s field receipts instead of dismissing the draft',async mode=>{
  const {credentialApi}=await import('../api')
  const {configureStudioConnection}=await import('../api/config')
  const command={commandId:'stable',name:'vault',expectedRevision:1,operations:[{kind:'remove' as const,key:'obsolete'}]}
  const credential={name:'vault',description:'',revision:mode==='missing-revision'?undefined:2,created_at:'old',updated_at:'new',fields:mode==='unapplied-operation'?[{key:'obsolete',masked:'***'}]:[{key:'value',masked:'***'}]}
  const restore=configureStudioConnection('http://credential-receipt.fixture',async()=>Response.json({success:true,commandId:mode==='wrong-command'?'unrelated':'stable',credential}))
  try {expect((await credentialApi.mutateFields(command)).success).toBe(false)} finally {restore()}
})
