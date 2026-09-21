import { expect, it } from 'vitest'
import { getAllAvailableModules, moduleCategories } from '../components/ModuleSidebar'

it('keeps the approved 227-node scope and all approved notification channels', () => {
  const modules = getAllAvailableModules().filter(module => !module.isCustom)
  const types = modules.map(module => module.type)
  expect(types).toHaveLength(227)
  expect(new Set(types).size).toBe(227)
  expect(types.filter(type => /^(excel_|pdf_|word_|wps_|qq_|wechat_|feishu_)/.test(type))).toEqual([])
  expect(types.filter(type => /^(dp_|db_|oracle_|postgresql_|mongodb_|sqlserver_|sqlite_|redis_)/.test(type))).toEqual([])
  expect(types).not.toContain('read_excel')
  expect(types).not.toContain('notify_feishu')
  expect(types).toContain('open_page')
  expect(types).toContain('click_element')
  expect(types).toContain('screenshot')
  expect(moduleCategories.find(item => item.name === '消息推送')?.modules).toHaveLength(16)
  expect(moduleCategories.find(item => item.name === '消息推送')?.modules).not.toContain('notify_feishu')
  for (const category of ['DP 反检测自动化', '数据库', '图像编辑', '盲水印', '视频处理', '音频处理', '媒体格式转换', '文件管理']) {
    expect(moduleCategories.map(item => item.name)).not.toContain(category)
  }
})
