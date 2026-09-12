import AxeBuilder from '@axe-core/playwright'
import {test,expect,navigate,settle} from './electron-fixture'
import type {Page,TestInfo} from '@playwright/test'
async function audit(page:Page,name:string,testInfo:TestInfo){
 await settle(page);expect(await page.locator('iframe').count()).toBe(0);const result=await new AxeBuilder({page}).setLegacyMode().withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()
 await testInfo.attach(name,{body:JSON.stringify(result.violations,null,2),contentType:'application/json'})
 expect(result.violations,`${name}: ${result.violations.map(item=>item.id).join(', ')}`).toEqual([])
}
test('axe: actual navigation pages and real nested forms',async({page},testInfo)=>{
 for(const name of ['总览','浏览器配置','代理管理','模型管理','设置']){await navigate(page,name);await audit(page,name,testInfo)}
 await navigate(page,'浏览器配置');await page.getByRole('button',{name:'新建配置',exact:true}).first().click()
 for(const name of ['基础信息','浏览器环境','内核与代理','高级选项']){await page.getByRole('tab',{name,exact:true}).click();await audit(page,`浏览器表单-${name}`,testInfo)}
 await page.getByRole('tab',{name:'内核与代理'}).click();await page.getByRole('button',{name:'管理内核',exact:true}).click();await audit(page,'嵌套内核弹窗',testInfo)
})
