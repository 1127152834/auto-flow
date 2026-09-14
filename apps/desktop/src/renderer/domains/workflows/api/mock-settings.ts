/** Local fixtures for retained settings forms; connection probes never contact remote services. */
const prefix = 'autoflow:studio:mock:settings:'
type Value = Record<string, unknown>
const read = (name: string, fallback: Value = {}): Value => JSON.parse(localStorage.getItem(prefix + name) || JSON.stringify(fallback))
const save = (name: string, value: Value) => localStorage.setItem(prefix + name, JSON.stringify(value))
const json = (value: unknown, status = 200) => Response.json(value, { status })
export function mockSettingsRequest(path: string, method: string, body: Value): Response | undefined {
  if (path === '/credentials/names') return json({success:true,names:Object.keys(read('credentials'))})
  if (path === '/credentials') {
    const credentials = read('credentials')
    if (method === 'POST') {
      const name = String(body.name || '').trim()
      if (!name) return json({success:false,error:'Credential name required'},400)
      const previous = credentials[name] as Value | undefined
      credentials[name] = {name,description:body.description || '',fields:Object.keys((body.fields || {}) as Value).map(key=>({key,masked:'•••••• (Mock)'})),created_at:previous?.created_at || new Date().toISOString(),updated_at:new Date().toISOString()}
      // The fixture retains names and masked field metadata, never credential values.
      save('credentials', credentials)
    }
    return json({success:true,credentials:Object.values(credentials),mock:true})
  }
  if (path === '/credentials/rename') {
    const credentials=read('credentials'), old=String(body.old_name), name=String(body.new_name)
    if (!credentials[old] || credentials[name]) return json({success:false,error:'Credential missing or name already exists'},409)
    credentials[name]={...(credentials[old] as Value),name};delete credentials[old];save('credentials',credentials);return json({success:true})
  }
  if (path.startsWith('/credentials/') && method === 'DELETE') {const credentials=read('credentials');delete credentials[path.split('/').at(-1)!];save('credentials',credentials);return json({success:true})}
  if (path.startsWith('/retention/')) {
    const usage={recordings:{count:0,sizeMB:0},data:{count:0,sizeMB:0}}
    if(path==='/retention/config' && method==='POST')save('retention',{...read('retention'),...body})
    return json({success:true,mock:true,usage,config:read('retention',{enabled:false,recordings_max_days:30,recordings_max_total_mb:0,data_max_days:30,data_max_total_mb:0,cleanup_interval_hours:24})})
  }
  if(path==='/local-workflows/webdav-config') {
    if(method==='POST')save('webdav',{...body,password:''})
    return json({success:true,config:read('webdav'),mock:true})
  }
  if(path==='/local-workflows/webdav-test')return json({success:false,error:'Mock: remote connection is not executed'})
  if(path==='/ai-assistant/mcp/config') {
    if(method==='PUT'){save('mcp',body.config as Value);return json({success:true,saved:true})}
    return json(read('mcp',{mcpServers:{}}))
  }
  if(path==='/ai-assistant/mcp/status' || path==='/ai-assistant/mcp/reload')return json({success:true,servers:[],tools:[],total_tools_injected:0,mock:true})
  return undefined
}
