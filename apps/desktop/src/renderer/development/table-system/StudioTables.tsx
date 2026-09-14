import { useMemo, useState, type CSSProperties } from 'react'
import { DataTable } from '../../domains/workflows/components/DataTable'
import { MarkdownRenderer } from '../../domains/workflows/components/documentation/MarkdownRenderer'
import { MessageBubble } from '../../domains/workflows/components/assistant/MessageBubble'
import type { ChatMessage } from '../../domains/workflows/hooks/stores/aiAssistantStore'
import type { DataRow } from '../../domains/workflows/editor-store'

const columns = Array.from({ length: 12 }, (_, index) => `合成列 ${index + 1}`)

const studioTheme = {
  '--background': '40 26% 93%',
  '--card': '45 33% 98%',
  '--foreground': '40 6% 19%',
  '--border': '40 16% 82%',
  '--muted': '38 27% 95%',
  '--muted-foreground': '38 6% 36%',
  '--brand-50': '25 50% 96%',
  '--brand-100': '25 45% 90%',
  '--brand-500': '23 47% 43%',
  '--brand-600': '20 50% 37%',
  '--brand-700': '20 51% 35%',
  '--slate-50': '40 25% 97%',
  '--slate-100': '40 20% 94%',
  '--slate-200': '40 15% 87%',
  '--slate-300': '40 11% 76%',
  '--slate-600': '40 7% 38%',
  '--slate-700': '40 7% 29%',
  '--slate-800': '40 7% 23%',
  '--danger-500': '0 65% 52%',
  '--danger-600': '0 66% 45%',
  '--ring': '23 47% 43%',
} as CSSProperties

const documentationTable = `| 字段 | 用途 | 示例 |
| --- | --- | --- |
| selector | 页面元素定位 | #submit-button |
| timeout | 最大等待毫秒数 | 30000 |
| result | 节点输出变量 | {页面结果} |`

const assistantMessage = {
  id: 'studio-table-showcase',
  role: 'assistant',
  content: `下面是合成执行摘要：\n\n| 阶段 | 记录数 | 状态 |\n| --- | ---: | --- |\n| 读取 | 10000 | 完成 |\n| 转换 | 10000 | 完成 |\n| 写入 | 9987 | 等待复核 |`,
} as ChatMessage

export default function StudioTables() {
  const initialData = useMemo(() => Array.from({ length: 10_000 }, (_, rowIndex) => Object.fromEntries(
    columns.map((column, columnIndex) => [column, columnIndex === 0 ? `合成记录 ${rowIndex + 1}` : (rowIndex + 1) * (columnIndex + 1)]),
  )), [])
  const [data, setData] = useState<DataRow[]>(initialData)

  return (
    <section style={studioTheme} className="space-y-6 rounded-lg bg-[hsl(var(--background))] p-4 text-[hsl(var(--foreground))]">
      <header>
        <h2 className="text-lg font-semibold">Studio 表格真实组件验收</h2>
        <p className="text-sm text-[hsl(var(--muted-foreground))]">以下 10,000 行 × 12 列均为合成数据，仅用于验证虚拟滚动、键盘 PageDown、横向滚动和表头同步。</p>
      </header>

      <div className="h-[480px] min-w-0 overflow-hidden rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
        <DataTable
          data={data}
          columns={columns}
          displayMode="head"
          onEdit={(rowIndex, column, value) => setData(current => current.map((row, index) => index === rowIndex ? { ...row, [column]: value } : row))}
          onDeleteRow={rowIndex => setData(current => current.filter((_, index) => index !== rowIndex))}
          onDeleteColumn={column => setData(current => current.map(row => Object.fromEntries(Object.entries(row).filter(([key]) => key !== column))))}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <article className="min-w-0 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-4">
          <h3 className="mb-2 text-sm font-semibold">教学文档 MarkdownRenderer</h3>
          <MarkdownRenderer content={documentationTable} />
        </article>
        <article className="min-w-0">
          <h3 className="mb-2 text-sm font-semibold">AI 回复 MessageBubble</h3>
          <MessageBubble message={assistantMessage} />
        </article>
      </div>
    </section>
  )
}
