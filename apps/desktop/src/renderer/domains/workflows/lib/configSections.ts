/** 配置面板分段：未登记的字段一律视为基本字段。 */
export const ADVANCED_FIELDS: Record<string, readonly string[]> = {
  click_element: ['followNewTab'],
  input_text: ['clearBefore'],
  get_element_info: ['columnName'],
  wait_element: ['waitTimeout'],
  open_page: ['waitUntil'],
  hover_element: ['hoverDuration'],
}

export const COMMON_ADVANCED: readonly string[] = ['timeout', 'selectorHints']

export function isAdvancedField(moduleType: string, key: string): boolean {
  return COMMON_ADVANCED.includes(key) || (ADVANCED_FIELDS[moduleType]?.includes(key) ?? false)
}

export function splitFields(moduleType: string, keys: readonly string[]): { basic: string[]; advanced: string[] } {
  const basic: string[] = []
  const advanced: string[] = []
  for (const key of keys) (isAdvancedField(moduleType, key) ? advanced : basic).push(key)
  return { basic, advanced }
}

export type ConfigSection = 'all' | 'basic' | 'advanced'

export function inSection(moduleType: string, key: string, section: ConfigSection): boolean {
  return section === 'all' || isAdvancedField(moduleType, key) === (section === 'advanced')
}
