import type { ChatMessage } from '../hooks/stores/aiAssistantStore'
interface Session { id:string;title:string;messages:ChatMessage[];updated_at:string }
const key='autoflow:studio:mock:assistant'
const read=():Session[]=>JSON.parse(localStorage.getItem(key)||'[]')
const save=(sessions:Session[])=>localStorage.setItem(key,JSON.stringify(sessions))
export async function mockAssistantRequest(path:string,method:string,body:Record<string,unknown>,signal:AbortSignal|undefined|null,emit:(event:string,data:unknown)=>void):Promise<Response|undefined> {
  if (!path.startsWith('/ai-assistant/')) return undefined
  const json=(data:unknown,status=200)=>Response.json(data,{status})
  const sessions=read()
  if(path==='/ai-assistant/sessions') {
    if(method==='GET')return json(sessions.map(s=>({...s,message_count:s.messages.length,last_message_preview:s.messages.at(-1)?.content || ''})))
    const session={id:crypto.randomUUID(),title:String(body.title||'Mock 对话'),messages:[],updated_at:new Date().toISOString()};sessions.unshift(session);save(sessions);return json({session_id:session.id,title:session.title})
  }
  if(path==='/ai-assistant/chat') {
    let session=sessions.find(s=>s.id===body.session_id)
    if(!session){session={id:crypto.randomUUID(),title:String(body.message).slice(0,30),messages:[],updated_at:new Date().toISOString()};sessions.unshift(session)}
    session.messages.push({id:crypto.randomUUID(),role:'user',content:String(body.message)})
    const content='[Mock 回复] 已接收到当前画布上下文。本轮只验证对话、流式消息和会话管理，没有调用真实模型，也没有自动修改工作流。'
    for(let end=10;end<content.length+10;end+=10){
      if(signal?.aborted)throw new DOMException('Aborted','AbortError')
      emit('ai_assistant:content_partial',{session_id:session.id,full:content.slice(0,end)})
      await new Promise(resolve=>setTimeout(resolve,25))
    }
    const message:ChatMessage={id:crypto.randomUUID(),role:'assistant',content,timestamp:new Date().toISOString()};session.messages.push(message);session.updated_at=message.timestamp!;save(sessions);return json({session_id:session.id,message})
  }
  const match=path.match(/^\/ai-assistant\/sessions\/([^/]+)(?:\/(.*))?$/)
  if(match){
    const [,id,action]=match;const session=sessions.find(s=>s.id===id)
    if(!session)return json({success:false,error:'会话不存在'},404)
    if(method==='DELETE'){save(sessions.filter(s=>s.id!==id));return json({success:true})}
    if(action==='title'){session.title=String(body.title);save(sessions);return json({success:true})}
    if(action==='truncate'){const index=session.messages.findIndex(m=>m.id===body.message_id);if(index<0)return json({success:false,error:'消息不存在'},404);session.messages=session.messages.slice(0,index);save(sessions);return json({success:true,messages:session.messages})}
    if(action==='cancel')return json({success:true,session_id:id})
    return json(session)
  }
  if(path==='/ai-assistant/config'){const configKey=key+':config';if(method==='POST' || method==='PUT')localStorage.setItem(configKey,JSON.stringify(body.config || body));return json({success:true,config:JSON.parse(localStorage.getItem(configKey)||'null')})}
  if(path==='/ai-assistant/skills')return json({count:0,skills:[]})
  if(path==='/ai-assistant/test-connection')return json({success:true,message:'Mock 连接可用；未连接真实模型',latency_ms:0})
  if(path==='/ai-assistant/memories') {
    const memoryKey=key+':memories';const entries:Record<string,unknown>[]=JSON.parse(localStorage.getItem(memoryKey)||'[]')
    if(method==='POST'){entries.push({id:crypto.randomUUID(),content:body.content,tags:body.tags});localStorage.setItem(memoryKey,JSON.stringify(entries))}
    return json({entries})
  }
  if(path.startsWith('/ai-assistant/memories/')&&method==='DELETE'){const memoryKey=key+':memories';const entries:Record<string,unknown>[]=JSON.parse(localStorage.getItem(memoryKey)||'[]');localStorage.setItem(memoryKey,JSON.stringify(entries.filter(e=>e.id!==path.split('/').at(-1))));return json({success:true})}
  if(path==='/ai-assistant/extract-file')return json({success:true,text:`[Mock 附件 ${String(body.filename)}，未解析文件正文]`})
  if(path==='/ai-assistant/transcribe')return json({success:true,text:'[Mock 语音转写，未识别音频]',language:body.language})
  return json({success:false,error:`Mock 不支持 ${path}`},501)
}
