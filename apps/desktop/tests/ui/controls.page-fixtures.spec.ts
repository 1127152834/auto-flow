import {test,expect,navigate,settle} from './electron-fixture'
import {connection,proxies,groups} from './page-fixtures'
import AxeBuilder from '@axe-core/playwright'
import type {ModelProvider,ModelDiscoveryRead} from '../../src/renderer/domains/models/model'

test('page fixture: proxy table, SOCKS5, ordered searchable group membership',async({page},testInfo)=>{
 const second={...proxies.items[0],id:'proxy-2',name:'Tokyo fixture',city:'Tokyo'}
 const rows={...proxies,items:[...proxies.items,second],matched_count:2}
 await page.route('**/api/v1/proxy-panel/connections',route=>route.fulfill({json:{items:[connection]}}))
 await page.route('**/api/v1/proxy-panel/connections/connection-1/sync',route=>route.fulfill({json:{status:'completed',operation_id:null,resource:null,error:null}}))
 await page.route('**/api/v1/proxy-groups?*',route=>route.fulfill({json:groups}))
 await page.route('**/api/v1/proxies?*',route=>route.fulfill({json:rows}))
 await page.route('**/api/v1/proxies/proxy-1',route=>route.fulfill({json:rows.items[0]}))
 await page.route('**/api/v1/proxies/proxy-1/references',route=>route.fulfill({json:{profiles:[],groups:[]}}))
 await navigate(page,'代理管理');await expect(page.getByRole('alert')).toHaveCount(0);await page.getByRole('row').filter({hasText:'Dallas Verizon'}).getByRole('button',{name:'详情',exact:true}).click()
 const drawer=page.getByRole('dialog',{name:'Dallas Verizon',exact:true});await expect(drawer).toBeVisible()
 await expect(page.getByRole('combobox',{name:'检测协议'})).toHaveAttribute('data-choice-value','socks5')
 await page.getByRole('tab',{name:'凭据与白名单'}).click()
 await expect(page.getByRole('combobox',{name:'凭据协议'})).toHaveAttribute('data-choice-value','socks5')
 await page.keyboard.press('Escape')
 await page.getByRole('button',{name:'新建代理组',exact:true}).click()
 const dialog=page.getByRole('dialog',{name:'新建本地代理组'})
 await page.getByRole('checkbox',{name:/Dallas Verizon/}).check();await page.getByRole('checkbox',{name:/Tokyo fixture/}).check()
 await page.getByRole('searchbox',{name:'搜索组成员'}).fill('Tokyo')
 await expect(dialog.getByRole('listitem')).toHaveCount(2)
 await page.getByRole('button',{name:'上移 Tokyo fixture'}).click();await expect(dialog.getByRole('listitem').first()).toContainText('Tokyo fixture')
 await page.getByRole('button',{name:'清除搜索',exact:true}).click();await expect(page.getByRole('checkbox',{name:/Dallas Verizon/})).toBeChecked()
 await settle(page);const axe=await new AxeBuilder({page}).setLegacyMode().withTags(['wcag2a','wcag2aa']).analyze();expect(axe.violations).toEqual([])
 await testInfo.attach('fixture-proxy-group',{body:await page.screenshot(),contentType:'image/png'})
})

test('page fixture: model suggestions apply metadata, free IDs and tags preserve save payload',async({page},testInfo)=>{
 const provider:ModelProvider={id:'fixture-provider',name:'Fixture local',presetId:'ollama',providerKind:'openai-compatible',baseUrl:'http://127.0.0.1:11434/v1',apiKeyConfigured:false,enabled:true,description:'UI fixture',models:[],connectionStatus:'connected',lastCheckedAt:null,lastCheckLatencyMs:null,lastCheckMessage:null,createdAt:'2026-09-12T00:00:00Z',updatedAt:'2026-09-12T00:00:00Z'}
 const discovery:ModelDiscoveryRead={ok:true,items:[{modelKey:'known',displayName:'Known',ownedBy:null,contextWindow:8192}],total:1,latencyMs:1,endpoint:'/models',message:''}
 await page.route('**/api/v1/model-providers',route=>route.fulfill({json:{items:[provider]}}))
 await page.route('**/api/v1/model-providers/fixture-provider/models/discover',route=>route.fulfill({json:discovery}))
 let payload:unknown
 await page.route('**/api/v1/model-providers/fixture-provider/models',async route=>{payload=route.request().postDataJSON();await route.fulfill({json:{...payload as object,id:'fixture-model',providerId:provider.id,createdAt:provider.createdAt,updatedAt:provider.updatedAt}})})
 await navigate(page,'模型管理');await page.getByRole('button',{name:'添加模型',exact:true}).click()
 const id=page.getByRole('combobox',{name:'模型标识',exact:true});await id.fill('known')
 await page.getByRole('option',{name:'Known · known',exact:true}).click()
 await expect(page.getByLabel('上下文窗口',{exact:true})).toHaveValue('8192');await expect(page.getByLabel('显示名称',{exact:true})).toHaveValue('Known')
 await id.fill('custom-id');await page.keyboard.press('Escape')
 await page.getByLabel('自定义标签',{exact:true}).fill('本地，推理,本地');await page.getByLabel('自定义标签',{exact:true}).press('Enter')
 await expect(page.getByRole('button',{name:'移除标签 本地'})).toHaveCount(1)
 const result=await new AxeBuilder({page}).setLegacyMode().withTags(['wcag2a','wcag2aa']).analyze();expect(result.violations).toEqual([])
 await testInfo.attach('fixture-model-editor',{body:await page.screenshot(),contentType:'image/png'})
 await page.getByRole('button',{name:'保存模型',exact:true}).click()
 await expect.poll(()=>payload).toMatchObject({modelKey:'custom-id',displayName:'Known',contextWindow:8192,tagsJson:['本地','推理']})
})
