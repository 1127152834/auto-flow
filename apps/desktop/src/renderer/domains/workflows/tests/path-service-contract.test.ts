import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {checkedPathSelection} from '../lib/pathSelectionContract'
describe.each(['memory','http'])('path selection protocol over %s',mode=>{
 let request:(path:string,body?:unknown,method?:string)=>Promise<Response>
 let fixture:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 beforeEach(async()=>{
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
  vi.resetModules();const {mockRequest}=await import('../api/mock-server')
  if(mode==='http')fixture=await startHttpStudioFixture(mockRequest)
  request=(path,body={},method='POST')=>{
   const init={method,...(method==='GET'?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
   return fixture?fetch(`${fixture.origin}/api/system/${path}`,init):mockRequest(`http://autoflow-studio.mock/api/system/${path}`,init)
  }
 })
 afterEach(async()=>{await fixture?.close();fixture=undefined;vi.unstubAllGlobals()})
 it.each(['file','folder'])('returns the original mock %s path and rejects wrong methods',async kind=>{
  const response=await request('select-'+kind,{title:'选择',initialDir:'/临时'})
  expect(response.status).toBe(200)
  const data=await response.json();expect(checkedPathSelection({success:true,data}).success).toBe(true)
  expect(data.path).toBe(data[kind])
  expect((await request('select-'+kind,{},'GET')).status).toBe(405)
 })
 it.each([{title:3},{initialDir:[]},{fileTypes:[['only-one']]},{fileTypes:[['name','pattern','extra']]},{fileTypes:[[3,'*.png']]},{extra:true}])('rejects invalid file request %#',async body=>{
  expect((await request('select-file',body)).status).toBe(422)
 })
 it('preserves null options and paired filters but rejects filters for folder selection',async()=>{
  expect((await request('select-file',{title:null,initialDir:null,fileTypes:[['图片','*.png;*.jpg']]})).status).toBe(200)
  expect((await request('select-folder',{fileTypes:[]})).status).toBe(422)
 })
})
it.each([{success:true,path:'/valid'}, {success:true,path:null}, {success:true,path:''}, {success:false,path:null,message:'用户取消选择'}])('accepts and normalizes source or compatible selection %#',data=>{
 expect(checkedPathSelection({success:true,data})).toMatchObject({success:true,data:{...data,error:null}})
})
it.each([{success:true}, {success:true,path:4}, {success:'true',path:'/path'}, {success:true,path:'/path',error:'失败'}, {success:false,path:'/path',error:'失败'}, {success:false,path:null}])('does not confirm ambiguous selection %#',data=>{
 expect(checkedPathSelection({success:true,data}).success).toBe(false)
})

it('preserves a service failure rather than confirming its null path',()=>{
 expect(checkedPathSelection({success:false,httpStatus:503,error:'不可用'})).toMatchObject({success:false,httpStatus:503,error:'不可用'})
 expect(checkedPathSelection({success:true,data:{success:false,path:null,error:'不可用'}})).toMatchObject({success:false,error:'不可用'})
})
