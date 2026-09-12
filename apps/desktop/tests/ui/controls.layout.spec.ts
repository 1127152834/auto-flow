import {test,expect,navigate,settle} from './electron-fixture'
import type {Locator,Page} from '@playwright/test'

async function rect(control:Locator){
 const box=await control.boundingBox()
 expect(box).not.toBeNull()
 return {x:box!.x,width:box!.width}
}
async function layout(page:Page){
 return {main:await rect(page.locator('main')),search:await rect(page.getByRole('searchbox',{name:'搜索配置',exact:true,includeHidden:true})),filter:await rect(page.getByRole('combobox',{name:'代理模式筛选',includeHidden:true}))}
}
function expectStable(actual:Awaited<ReturnType<typeof layout>>,baseline:Awaited<ReturnType<typeof layout>>){
 for(const key of ['main','search','filter'] as const){
  expect(Math.abs(actual[key].width-baseline[key].width),`${key} width`).toBeLessThan(0.5)
  expect(Math.abs(actual[key].x-baseline[key].x),`${key} position`).toBeLessThan(0.5)
 }
}

test('opening a select or searchable popup preserves page and control geometry',async({page,desktop},testInfo)=>{
 await navigate(page,'浏览器配置')
 const samples=[]
 for(const zoom of [1,1.25,2]){
  await desktop.evaluate(({BrowserWindow},zoom)=>BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(zoom),zoom)
  await settle(page)
  // Require a real scrollbar so this catches scroll-lock compensation regressions.
  expect(await page.evaluate(()=>innerWidth-document.documentElement.clientWidth)).toBeGreaterThan(0)
  const baseline=await layout(page)
  for(let attempt=0;attempt<2;attempt++){
   await page.getByRole('combobox',{name:'代理模式筛选'}).click()
   await expect(page.getByRole('listbox')).toBeVisible();await settle(page)
   const opened=await layout(page);expectStable(opened,baseline)
   await page.keyboard.press('Escape');await settle(page);expectStable(await layout(page),baseline)
   samples.push({zoom,attempt,baseline,opened})
  }
  await page.getByRole('button',{name:'新建配置',exact:true}).first().click()
  await page.getByRole('tab',{name:'浏览器环境'}).click();await settle(page)
  expectStable(await layout(page),baseline)
  const input=page.getByRole('combobox',{name:'浏览器语言',exact:true}),before=await rect(input)
  await input.focus();await page.keyboard.press('ArrowDown')
  await expect(page.getByRole('listbox')).toBeVisible();await settle(page)
  expect(await rect(input)).toEqual(before);expectStable(await layout(page),baseline)
  await page.keyboard.press('Escape');await expect(input).toBeFocused()
  await page.keyboard.press('Escape');await settle(page);expectStable(await layout(page),baseline)
 }
 await testInfo.attach('stable-layout',{body:JSON.stringify(samples,null,2),contentType:'application/json'})
})
