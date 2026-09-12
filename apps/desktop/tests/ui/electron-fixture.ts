import {test as base,expect,_electron,type ElectronApplication,type Page} from '@playwright/test'
import {mkdtemp,realpath,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {resolve,join} from 'node:path'
import {createServer} from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'
const root=resolve(import.meta.dirname,'../../../..')
export const test=base.extend<{desktop:ElectronApplication;page:Page}>({
 desktop:async({},use,testInfo)=>{
  const userData=await realpath(await mkdtemp(join(tmpdir(),'autoflow-controls-e2e-')))
  const server=await createServer({root:join(root,'apps/desktop/src/renderer'),configFile:false,cacheDir:join(userData,'.vite'),plugins:[react(),tailwind()],server:{host:'127.0.0.1',port:0}})
  let desktop:ElectronApplication|undefined
  try{
   await server.listen();const address=server.httpServer!.address();if(!address||typeof address==='string')throw new Error('No isolated Vite port')
   desktop=await _electron.launch({args:[join(root,'apps/desktop'),`--user-data-dir=${userData}`],cwd:root,env:{...process.env,ELECTRON_RENDERER_URL:`http://127.0.0.1:${address.port}/#/dashboard`}})
   expect(await realpath(await desktop.evaluate(({app})=>app.getPath('userData')))).toBe(userData)
   await testInfo.attach('runtime',{body:JSON.stringify(await desktop.evaluate(()=>({platform:process.platform,arch:process.arch,electron:process.versions.electron,chromium:process.versions.chrome}))),contentType:'application/json'})
   await use(desktop)
  }finally{await desktop?.close();await server.close();await rm(userData,{recursive:true,force:true})}
 },
 page:async({desktop},use,testInfo)=>{
  const page=await desktop.firstWindow(), errors:string[]=[]
  page.on('pageerror',error=>errors.push(error.message))
  await expect(page.getByText('本地服务正常',{exact:true})).toBeVisible()
  try{await use(page)}finally{
   await testInfo.attach('window',{body:await page.screenshot(),contentType:'image/png'})
   if(errors.length)await testInfo.attach('renderer-errors',{body:JSON.stringify(errors),contentType:'application/json'})
   expect(errors).toEqual([])
  }
 }
})
export {expect}
export async function settle(page:Page){await page.evaluate(async()=>{await new Promise(requestAnimationFrame);await Promise.all(document.getAnimations().filter(animation=>animation.effect?.getTiming().iterations!==Infinity).map(animation=>animation.finished.catch(()=>{})));await new Promise(requestAnimationFrame)})}
export async function navigate(page:Page,name:string){await page.getByRole('button',{name,exact:true}).first().click();await expect(page.getByRole('heading',{level:1,name,exact:true})).toBeVisible();await settle(page)}
