import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {isRequiredFieldMetadata} from '../lib/requiredFields'
import fixture from '../development/module-required-fields.json'
describe.each(['memory','http'] as const)('module metadata over %s',mode=>{
 let mock:typeof import('../api/mock-server');let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let request:(method?:string)=>Promise<Response>
 beforeEach(async()=>{
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
  vi.resetModules();mock=await import('../api/mock-server');if(mode==='http')server=await startHttpStudioFixture(mock.mockRequest)
  request=(method='GET')=>server?fetch(`${server.origin}/api/system/module-required-fields`,{method}):mock.mockRequest('http://autoflow-studio.mock/api/system/module-required-fields',{method})
 })
 afterEach(async()=>{mock.configureMock({disconnect:true});await server?.close();server=undefined;vi.unstubAllGlobals()})
 it('returns exactly the filtered frozen metadata with explicit coverage',async()=>{
  const response=await request();expect(response.status).toBe(200);const data=await response.json()
  expect(isRequiredFieldMetadata(data)).toBe(true);expect(data).toEqual(fixture);expect(data.coveredModules).toHaveLength(69)
  expect(data.requiredFields.open_page).toEqual(['url']);expect(data.requiredFields.wait).toBeUndefined()
  expect(data.coveredModules).not.toContain('real_keyboard');expect(data.fieldLabels.open_page.url).toContain('URL')
 })
 it('rejects mutation without changing metadata',async()=>{
  expect((await request('POST')).status).toBe(405);expect(await(await request()).json()).toEqual(fixture)
 })
})
