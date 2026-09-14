import {apiRequest,type ApiResponse} from '../api'
import {checkedBrowserScriptRequest,isBrowserScriptContext,isBrowserScriptState,type BrowserScriptContext,type BrowserScriptRequest,type BrowserScriptState} from '../lib/browserScriptContract'
const endpoint='/browser/script-tests'
async function stateRequest(id:string,path:string,options:RequestInit={}):Promise<ApiResponse<BrowserScriptState>> {
 const response=await apiRequest<BrowserScriptState>(path,options)
 if(response.success && (!isBrowserScriptState(response.data) || response.data.requestId!==id))return {success:false,httpStatus:response.httpStatus??200,error:'脚本测试状态格式错误，不能确认执行结果'}
 return response
}
export const browserScriptTestsApi={
 getContext:async(signal?:AbortSignal):Promise<ApiResponse<BrowserScriptContext>>=>{
  const response=await apiRequest<BrowserScriptContext>(`${endpoint}/context`,{signal})
  if(response.success && !isBrowserScriptContext(response.data))return {success:false,httpStatus:response.httpStatus??200,error:'脚本测试页面上下文格式错误'}
  return response
 },
 start:(request:BrowserScriptRequest,signal?:AbortSignal)=>{
  const checked=checkedBrowserScriptRequest(request)
  return stateRequest(request.requestId,endpoint,{method:'POST',body:JSON.stringify(checked),signal})
 },
 get:(id:string,signal?:AbortSignal)=>stateRequest(id,`${endpoint}/${encodeURIComponent(id)}`,{signal}),
 cancel:(id:string,signal?:AbortSignal)=>stateRequest(id,`${endpoint}/${encodeURIComponent(id)}/cancel`,{method:'POST',signal}),
}
