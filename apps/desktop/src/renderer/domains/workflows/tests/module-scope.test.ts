import { expect, it } from 'vitest'
import { getAllAvailableModules, moduleCategories } from '../components/ModuleSidebar'

it('removes non-Web office, media and bot nodes from the shared add/search catalog while retaining Web actions', () => {
  const modules = getAllAvailableModules().filter(module => !module.isCustom)
  const types = modules.map(module => module.type)
  expect(types.filter(type => /^(excel_|pdf_|word_|wps_|qq_|wechat_|feishu_)/.test(type))).toEqual([])
  expect(types).not.toContain('read_excel')
  expect(types).not.toContain('notify_feishu')
  expect(types).toContain('open_page')
  expect(types).toContain('click_element')
  expect(types).toContain('screenshot')
  for (const category of ['图像编辑', '盲水印', '视频处理', '音频处理', '媒体格式转换', '文件管理']) {
    expect(moduleCategories.map(item => item.name)).not.toContain(category)
  }
})
