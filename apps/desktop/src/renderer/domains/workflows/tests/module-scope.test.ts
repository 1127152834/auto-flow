import { expect, it } from 'vitest'
import { getAllAvailableModules, moduleCategories } from '../components/ModuleSidebar'
import { diagnosticModuleTypes } from '../lib/moduleCatalog'

const projectModuleTypes = ['project_data', 'project_manual', 'project_end'] as const
const proxyModuleTypes = ['proxy_change_ip', 'proxy_change_location', 'proxy_query'] as const
const extensionModuleTypes = new Set<string>([
  ...projectModuleTypes,
  ...proxyModuleTypes,
  ...diagnosticModuleTypes,
  'press_key', // remediation M1 R1-15
])

it('keeps 213 frozen nodes plus the ten approved AutoFlow extensions', () => {
  const types = getAllAvailableModules()
    .filter(module => !module.isCustom)
    .map(module => module.type)
  const frozenTypes = types.filter(type => !extensionModuleTypes.has(type))

  expect(types).toHaveLength(223)
  expect(new Set(types).size).toBe(223)
  expect(frozenTypes).toHaveLength(213)
  expect(new Set(frozenTypes).size).toBe(213)
  expect(types.filter(type => projectModuleTypes.includes(type as typeof projectModuleTypes[number]))).toEqual(projectModuleTypes)
  expect(types.filter(type => proxyModuleTypes.includes(type as typeof proxyModuleTypes[number]))).toEqual(proxyModuleTypes)
  expect(types.filter(type => diagnosticModuleTypes.includes(type))).toEqual(diagnosticModuleTypes)
  expect(types.filter(type => /^(excel_|pdf_|word_|wps_|qq_|wechat_|feishu_)/.test(type))).toEqual([])
  expect(types.filter(type => /^(dp_|db_|oracle_|postgresql_|mongodb_|sqlserver_|sqlite_|redis_)/.test(type))).toEqual([])
  expect(types).not.toContain('read_excel')
  expect(types).not.toContain('notify_feishu')
  expect(types).toContain('open_page')
  expect(types).toContain('click_element')
  expect(types).toContain('screenshot')
  expect(moduleCategories.find(item => item.name === '消息推送')?.modules).toEqual(['notify_telegram', 'notify_webhook'])
  expect(moduleCategories.find(item => item.name === '消息推送')?.modules).not.toContain('notify_feishu')
  for (const category of ['DP 反检测自动化', '数据库', '图像编辑', '盲水印', '视频处理', '音频处理', '媒体格式转换', '文件管理']) {
    expect(moduleCategories.map(item => item.name)).not.toContain(category)
  }
})
