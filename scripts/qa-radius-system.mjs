import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { mkdtemp, mkdir, writeFile, readFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, connectCdp, waitFor, wait } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'
const root=resolve(import.meta.dirname,'..'), parent=join(root,'docs/ui/radius-system/runs')
await mkdir(parent,{recursive:true})
const evidence=await mkdtemp(join(parent,'run-')), workspace=await mkdtemp(join(tmpdir(),'autoflow-radius-qa-'))
await writeFile(join(workspace,'.radius-qa.json'),JSON.stringify({kind:'autoflow-radius-qa',evidence}))
const report={status:'running',workspace,platform:process.platform,arch:process.arch,screenshots:[],checks:[]}
async function hashTree(path) {const hash=createHash('sha256');for(const file of (await readdir(path,{recursive:true})).filter(f=>/\.(tsx?|css|js|html)$/.test(f)).sort())hash.update(file).update(await readFile(join(path,file)));return hash.digest('hex')}
report.sourceHead=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim()
report.sourceSha256=await hashTree(join(root,'apps/desktop/src/renderer'))
report.buildSha256=await hashTree(join(root,'apps/desktop/out'))
let desktop,page,native,studio
async function click(text){const p=await waitFor(page,`(()=>{const e=[...document.querySelectorAll('button')].find(e=>(e.textContent.trim()===${JSON.stringify(text)}||(${JSON.stringify(text)}==='工作流工作台'&&e.textContent.includes('工作流工作台')))&&!e.disabled);if(!e)return null;e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`,text);for(const type of ['mousePressed','mouseReleased'])await page.command('Input.dispatchMouseEvent',{type,...p,button:'left',clickCount:1});await wait(200)}
async function capture(name,target=page){const state=await target.evaluate(`({viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},font:getComputedStyle(document.body).fontFamily,tokens:Object.fromEntries(['control','card','modal'].map(k=>[k,getComputedStyle(document.documentElement).getPropertyValue('--radius-'+k)]))})`);const {data}=await target.command('Page.captureScreenshot',{format:'png'});await writeFile(join(evidence,name+'.png'),data,'base64');report.screenshots.push({name,...state})}
try{
 desktop=await launchElectron(root,{launchArgs:['--user-data-dir='+workspace,'--inspect=0'],cliArgs:[]});page=desktop.cdp;native=await connectCdp(desktop.inspectorUrl)
 await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');qaElectron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
 await waitFor(page,"document.body?.innerText.includes('本地服务正常')",'application ready',30000)
 await click('项目');await click('新建项目');await waitFor(page,"!!document.querySelector('#project-name')",'project dialog')
 const radii=await page.evaluate(`(()=>{const radius=e=>getComputedStyle(e).borderTopLeftRadius;return{input:radius(document.querySelector('#project-name')),textarea:radius(document.querySelector('#project-description')),dialog:radius(document.querySelector('[role=dialog]')),button:radius([...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='创建项目')),cards:[...document.querySelectorAll('.rounded-card')].map(radius)}})()`)
 assert.deepEqual([radii.input,radii.textarea,radii.button,radii.dialog],['4px','4px','4px','6px']);assert.ok(radii.cards.length>0&&radii.cards.every(r=>'6px'===r));report.checks.push({name:'real project dialog controls/cards',radii})
 await capture('project-create-100')
 await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2);true');await wait(250)
 assert.ok(await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
 await capture('project-create-200')
 await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1);true');await wait(250)
 await page.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await page.command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await waitFor(page,"!document.querySelector('[role=dialog]')",'Escape closes dialog')
 assert.equal(await page.evaluate('document.activeElement.textContent.trim()'),'新建项目');report.checks.push({name:'Escape focus restoration',status:'passed'})
 for(const name of ['浏览器配置','代理管理','模型管理','设置']){await click(name);await capture(name)}
 await click('总览');await click('工作流工作台')
 const target=await waitFor({evaluate:async()=>{const targets=await(await fetch(desktop.debugOrigin+'/json/list')).json();return targets.find(t=>t.type==='page'&&t.url.includes('view=automation-studio'))}},'','Studio window')
 studio=await connectCdp(target.webSocketDebuggerUrl);await waitFor(studio,"!!document.querySelector('.react-flow')",'Studio canvas',30000)
 const tokens=await studio.evaluate("Object.fromEntries(['control','card','modal','md','lg','xl','2xl'].map(k=>[k,getComputedStyle(document.documentElement).getPropertyValue('--radius-'+k).trim()]))")
 assert.deepEqual(tokens,{control:'4px',card:'6px',modal:'6px',md:'4px',lg:'4px',xl:'6px','2xl':'6px'});report.checks.push({name:'independent Studio uses same scale',tokens});await capture('studio',studio)
 report.status='passed'
}catch(error){report.status='failed';report.error=String(error);await capture('failure').catch(()=>{});throw error}
finally{await writeFile(join(evidence,'report.json'),JSON.stringify(report,null,2));studio?.close();page?.close();native?.close();await stop(desktop?.child);console.log(evidence)}
