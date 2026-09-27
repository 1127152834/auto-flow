// Read-only verification of UI actions performed in the packaged app.
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { connectCdp } from '../../../scripts/electron-cdp.mjs'
const out = join(import.meta.dirname,'ui')
const session = JSON.parse(await readFile(join(out,'native-session.json'),'utf8'))
const targets = await (await fetch(`${session.debugOrigin}/json/list`)).json()
const studioTarget = targets.find(t=>t.type==='page'&&t.url.includes('view=automation-studio'))
const studio=await connectCdp(studioTarget.webSocketDebuggerUrl)
try {
 const context=await studio.evaluate('window.autoflow.getRuntimeContext()')
 const service=context.sidecar
 const api=async path=>{const r=await fetch(`${service.baseUrl}/api${path}`,{headers:{'x-autoflow-token':service.token}});assert.equal(r.status,200);return r.json()}
 const list=await api('/workflow-runs?cursor=0&limit=20')
 const run=list.items.find(r=>r.workflowName==='原生编辑器真实JavaScript验收')
 assert.ok(run);assert.equal(run.status,'completed')
 const detail=await api(`/workflow-runs/${run.runId}`)
 const results=await api(`/workflow-runs/${run.runId}/results?cursor=0&limit=20`)
 const actual=results.items.find(r=>r.values?.result?.runtime)?.values.result
 const expected=await studio.evaluate('({runtime:navigator.userAgent,language:navigator.language,timeZone:Intl.DateTimeFormat().resolvedOptions().timeZone})')
 assert.deepEqual(actual,expected)
 const screenshot=await studio.command('Page.captureScreenshot',{format:'png'})
 await writeFile(join(out,'native-js-completed.png'),screenshot.data,'base64')
 await writeFile(join(out,'native-js-result.json'),JSON.stringify({status:'passed',packaged:true,createdViaNativeUI:true,code:'function main(vars) { return {runtime: navigator.userAgent, language: navigator.language, timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone}; }',expected,actual,run,detail,results},null,2))
 await writeFile(join(out,'native-before-quit.json'),JSON.stringify({desktopPid:session.pid,sidecarInstanceId:service.instanceId,baseUrl:service.baseUrl},null,2))
 console.log(JSON.stringify({status:'passed',runId:run.runId,actual}))
}finally{studio.close()}
