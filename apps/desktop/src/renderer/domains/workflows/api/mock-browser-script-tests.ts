import {checkedBrowserScriptRequest,sameScriptTarget,type BrowserScriptTarget,type BrowserScriptState} from '../lib/browserScriptContract'
import {jsonCopy} from '../lib/jsScript'

// Protocol fixture only: never evaluate submitted source or fabricate a real browser result.
let target:BrowserScriptTarget|null=null
const tests=new Map<string,{fingerprint:string;state:BrowserScriptState;timer?:ReturnType<typeof setTimeout>}>()
let fixture:{result?:unknown;error?:string;hold?:boolean}={}
export function configureMockScriptTest(value:typeof fixture){fixture=jsonCopy(value)}
export function mockScriptTestBusy(){return [...tests.values()].some(test=>test.state.status==='running')}
export function invalidateMockScriptTests(close=false){
 if(target)target=close?null:{...target,revision:target.revision+1}
 for(const test of tests.values())if(test.state.status==='running'){
  clearTimeout(test.timer);test.timer=undefined
  test.state={...test.state,status:'expired',error:'测试页面已导航或关闭，原请求已失效'}
 }
}
const failure=(error:string,status:number)=>Response.json({success:false,error,detail:error},{status})
export function mockBrowserScriptTests(path:string,method:string,body:unknown,available:boolean,url:string):Response|null {
 const prefix='/browser/script-tests'
 if(!path.startsWith(prefix))return null
 if(path===`${prefix}/context`){
  if(method!=='GET')return failure('页面上下文只接受GET',405)
  if(!available)return failure('请先打开空闲的自动化浏览器，结束运行、拾取或录制后再测试',409)
  target??={browserSessionId:crypto.randomUUID(),pageId:crypto.randomUUID(),revision:0}
  return Response.json({...target,url,activeRequestId:[...tests.values()].find(test=>test.state.status==='running')?.state.requestId??null})
 }
 if(path===prefix){
  if(method!=='POST')return failure('脚本测试启动只接受POST',405)
  let request
  try{request=checkedBrowserScriptRequest(body)}catch(error){return failure(error instanceof Error?error.message:String(error),422)}
  const fingerprint=JSON.stringify(request,(_key,value)=>value && typeof value==='object' && !Array.isArray(value)?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b))):value)
  const old=tests.get(request.requestId)
  if(old)return old.fingerprint===fingerprint?Response.json(old.state):failure('脚本测试请求标识冲突',409)
  if(!available || !target || !sameScriptTarget(target,request.context))return failure('测试页面不存在、被占用或导航修订已过期',409)
  if(mockScriptTestBusy())return failure('已有未结束的脚本测试，请先确认或取消原请求',409)
  const state:BrowserScriptState={requestId:request.requestId,context:{...target},status:'running',hasResult:false,result:null,error:null,executionKind:'mock'}
  const test:{fingerprint:string;state:BrowserScriptState;timer?:ReturnType<typeof setTimeout>}={fingerprint,state}
  const outcome=jsonCopy(fixture)
  test.timer=setTimeout(()=>{
   if(test.state.status!=='running')return
   test.timer=undefined
   test.state=outcome.error || outcome.hold
    ? {...state,status:'failed',error:outcome.error || '脚本测试超过30秒，已停止'}
    : {...state,status:'completed',hasResult:Object.hasOwn(outcome,'result'),result:outcome.result??null}
  },outcome.hold?30000:50)
  tests.set(request.requestId,test)
  return Response.json(test.state)
 }
 const match=path.match(/^\/browser\/script-tests\/([^/]+)(\/cancel)?$/)
 if(!match)return failure('未知脚本测试接口',404)
 const test=tests.get(decodeURIComponent(match[1]))
 if(!test)return failure('脚本测试请求不存在',404)
 if(method!==(match[2]?'POST':'GET'))return failure('脚本测试请求方法不支持',405)
 if(match[2] && test.state.status==='running'){
  clearTimeout(test.timer);test.timer=undefined
  test.state={...test.state,status:'cancelled'}
 }
 return Response.json(test.state)
}
