/* ============================================================
   路径选择器完整性审计

   要守的规则：凡是让用户填「本地文件 / 文件夹路径」的输入框，旁边都必须有选择器
   （PathInput / ImagePathInput，或手写的 systemApi.selectFile / selectFolder 按钮）。
   只能手打路径的输入框对用户很不友好——「播放音乐」的音频地址就曾漏配选择器。

   判定思路：
     1. 字段名像本地路径（含 path/dir/folder/file，或 audio/video/image 等媒体 Url）；
     2. 承载它的组件是纯输入框（VariableInput / Input / Textarea）；
     3. 附近既没有选择器组件，也没有手写的 selectFile/selectFolder 调用。
   三条同时成立即为缺口。

   命名像路径但实际不是文件系统路径的字段（XPath、JSONPath、文件名模板、各种 ID 等）
   必须显式登记进 NOT_FILESYSTEM_KEYS，以此强制新增字段时做一次判断。
   ============================================================ */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const FRONTEND_DIR = path.resolve(path.dirname(__filename), '../..')
const PANEL_DIR = path.join(FRONTEND_DIR, 'components', 'config-panels')

/** 已提供选择器的输入组件 */
const PICKER_COMPONENTS = /(PathInput|ImagePathInput)/
/** 承载用户输入、需要检查的纯输入组件 */
const PLAIN_INPUTS = /^(VariableInput|Input|Textarea)$/

/**
 * 命名像路径、但并非「本地文件系统路径」的字段白名单。
 * 新增字段若命名含 path/file/dir 却不是本地路径，请登记到这里并注明原因。
 */
export const NOT_FILESYSTEM_KEYS = new Set([
  // 选择器 / 表达式类路径
  'xpath', 'jsonPath', 'conditionPath', 'controlPath', 'menuPath', 'path',
  // 匹配模式，不是具体路径
  'filePattern', 'fileNamePattern',
  // 网络地址
  'includePaths', 'excludePaths', 'remotePath', 'urlPattern', 'apiUrl', 'baseUrl',
  'webhookUrl', 'targetUrl', 'url', 'pageUrl', 'requestUrl', 'proxyUrl', 'hubUrl',
  'downloadUrl', 'avatarUrl', 'iconUrl', 'callbackUrl',
  // 只是文件名 / 文件名模板，与「输出目录」配对使用，选文件无意义
  'fileName', 'filename', 'outputFilename',
  // 各种 ID
  'fileId', 'folderId',
  // 被 dir 子串误命中的无关字段
  'direction',
  // 变量引用（值是列表变量名，不是单个路径）
  'inputFiles',
  // 其它非路径
  'sheetName', 'cell', 'link', 'address', 'resultVariable', 'variableName',
])

const FS_KEY_RE = /(path|dir|directory|folder|file)/i
const MEDIA_URL_RE = /^(audio|video|image|media|music|sound|doc|excel|pdf|word)Url$/i

function looksLikeFsPath(key) {
  if (NOT_FILESYSTEM_KEYS.has(key)) return false
  return FS_KEY_RE.test(key) || MEDIA_URL_RE.test(key)
}

/** 返回缺少路径选择器的输入框清单：{ file, line, key, detail }[] */
export function findMissingPathPickers() {
  const gaps = []
  for (const name of fs.readdirSync(PANEL_DIR)) {
    if (!name.endsWith('.tsx')) continue
    const src = fs.readFileSync(path.join(PANEL_DIR, name), 'utf8')
    const lines = src.split('\n')

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]

      // 形态一：声明式 schema —— { key: 'xxxPath', type: 'text' }
      const schemaKey = line.match(/key:\s*'([A-Za-z0-9_]+)'/)
      if (schemaKey) {
        const key = schemaKey[1]
        if (!looksLikeFsPath(key)) continue
        const seg = lines.slice(i, i + 4).join(' ')
        const t = (seg.match(/type:\s*'([a-z]+)'/) || [])[1] || ''
        if (t && !['path', 'imagepath'].includes(t)) {
          gaps.push({ file: name, line: i + 1, key, detail: `声明式字段 type:'${t}'，应改为 'path' 或 'imagepath'` })
        }
        continue
      }

      // 形态二：JSX 输入组件绑定路径类字段
      const bound = line.match(/data\.([A-Za-z0-9_]+)\b/)
      if (!bound) continue
      const key = bound[1]
      if (!looksLikeFsPath(key)) continue

      let comp = ''
      for (let j = i; j >= Math.max(0, i - 6); j--) {
        const c = lines[j].match(/<([A-Z][A-Za-z0-9]*)/)
        if (c) { comp = c[1]; break }
      }
      if (!comp || PICKER_COMPONENTS.test(comp)) continue
      if (!PLAIN_INPUTS.test(comp)) continue

      // 手写的选择器按钮（Button + systemApi.selectFile/selectFolder）同样算已提供
      const near = lines.slice(Math.max(0, i - 8), i + 20).join(' ')
      if (/selectFile|selectFolder/.test(near)) continue

      gaps.push({ file: name, line: i + 1, key, detail: `<${comp}> 未配路径选择器` })
    }
  }
  return gaps
}

// 直接运行时打印报告
const isMain = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(__filename)
if (isMain) {
  const gaps = findMissingPathPickers()
  console.log(`路径选择器缺口: ${gaps.length}`)
  for (const g of gaps) console.log(`  ${g.file}:${g.line} ${g.key} — ${g.detail}`)
  process.exit(gaps.length === 0 ? 0 : 1)
}
