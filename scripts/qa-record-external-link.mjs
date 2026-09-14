import assert from 'node:assert/strict'
import {createServer} from 'node:http'
import {createHash} from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {mkdtemp,mkdir,writeFile,rm,readFile} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join,resolve} from 'node:path'
import {createInterface} from 'node:readline/promises'
import {launchElectron,waitFor} from './electron-cdp.mjs'
import {stop} from './smoke-sidecar.mjs'
const root=resolve(import.meta.dirname,'..'),owner=await mkdtemp(join(tmpdir(),'autoflow-link-qa-')),marker=crypto.randomUUID()
await writeFile(join(owner,'.link-qa-owner'),marker)
const parent=join(root,'docs/project-management/design-alignment/acceptance/r2/external-link');await mkdir(parent,{recursive:true});const evidence=await mkdtemp(join(parent,'run-'))
const requests=[],server=createServer((request,response)=>{requests.push({url:request.url,at:new Date().toISOString()});response.writeHead(200,{'content-type':'text/html;charset=utf-8'});response.end('<!doctype html><title>AutoFlow 外链验收</title><h1>外部链接已打开</h1><p>这是本次隔离测试的本地页面。</p>')})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url=`http://127.0.0.1:${server.address().port}/autoflow-link-${marker}`
let desktop
try{
 desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${owner}`],cliArgs:[]});const page=desktop.cdp
 await waitFor(page,"document.body?.innerText.includes('本地服务正常')",'ready',30000)
 const {sidecar}=await page.evaluate('window.autoflow.getRuntimeContext()')
 // Read each response only once; setup is E2, the operator must click the actual renderer control.
 const post=async(path,body)=>{const response=await fetch(`${sidecar.baseUrl}/api/v1${path}`,{method:'POST',headers:{'x-autoflow-token':sidecar.token,'content-type':'application/json','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(body)});const value=await response.json();assert.ok(response.ok,JSON.stringify(value));return value}
 const project=await post('/projects',{name:'外链隔离验收'}),base=`/projects/${project.projectId}`
 const table=await post(`${base}/tables`,{name:'外链资料',sourceKind:'local'})
 const mutation=(await post(`${base}/tables/${table.tableId}/fields`,{definition:{key:'url',name:'文章链接',type:'string',required:false,validation:{}},expectedTableRevision:table.tableRevision,sourceColumnPolicy:'localOnly'}))
 const field=mutation.field, secure=(await post(`${base}/tables/${table.tableId}/fields`,{definition:{key:'secure_url',name:'HTTPS链接',type:'string',required:false,validation:{}},expectedTableRevision:mutation.tableRevision,sourceColumnPolicy:'localOnly'})).field
 const record=await post(`${base}/tables/${table.tableId}/records`,{datasetGeneration:table.datasetGeneration,values:[{fieldId:field.ref.fieldId,value:url},{fieldId:secure.ref.fieldId,value:'https://example.com/'}]})
 await page.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data/${table.tableId}/records/${table.datasetGeneration}/${record.ref.recordKey.type}/${Buffer.from(record.ref.recordKey.value).toString('base64url')}`)}`)
 await waitFor(page,"!!document.querySelector('[aria-label=\"打开链接 文章链接\"]')",'real record link control')
 console.log(JSON.stringify({evidence,owner,url,ready:true,setup:'E2 API data and direct record route; click uses native CUA'}))
 const lines=createInterface({input:process.stdin,output:process.stdout});for await(const command of lines){if(command.trim()==='verify'){assert.ok(requests.some(item=>item.url===new URL(url).pathname),'local server must observe the exact link opened by the system browser');await writeFile(join(evidence,'result.json'),JSON.stringify({result:'passed',platform:process.platform,arch:process.arch,url,requests,setup:'E2 real HTTP fixture/direct route',action:'native CUA clicks actual record open-link control',https:'native browser destination recorded separately in browser evidence',sourceHead:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),buildSha256:createHash('sha256').update(await readFile(join(root,'apps/desktop/out/main/index.js'))).digest('hex'),scriptSha256:createHash('sha256').update(await readFile(import.meta.filename)).digest('hex'),at:new Date().toISOString()},null,2));console.log('exact local browser target verified')}else if(command.trim()==='quit'){lines.close();break}}
}finally{desktop?.cdp.close();await stop(desktop?.child);server.closeAllConnections();await new Promise(resolve=>server.close(resolve));assert.equal(await readFile(join(owner,'.link-qa-owner'),'utf8'),marker);await rm(owner,{recursive:true,force:true})}
