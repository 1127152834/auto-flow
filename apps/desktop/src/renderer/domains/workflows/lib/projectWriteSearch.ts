import { moduleMatchesQuery } from './pinyin'
import { projectWriteEntries, type ProjectWriteEntry } from './moduleCatalog'

// Kept out of moduleCatalog.ts: that file is also loaded by plain Node scripts (studio-docs test), which cannot resolve the extension-less './pinyin' import.
/** Same matching as every other module search (Chinese, pinyin, initials, English, case-insensitive); "项目数据" shows all four. */
export const matchProjectWriteEntries = (query: string): ProjectWriteEntry[] =>
  projectWriteEntries.filter(entry => moduleMatchesQuery(query, { label: '项目数据', type: 'project_data' }) || moduleMatchesQuery(query, { label: entry.label, type: entry.operation }))
