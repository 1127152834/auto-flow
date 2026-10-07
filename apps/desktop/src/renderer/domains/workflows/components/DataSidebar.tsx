import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { credentialApi } from '../api'
import { useWorkflowStore } from '../editor-store'
import { useSignatureStore } from '../hooks/stores/signatureStore'
import { buildDataSidebar, filterRows, referencesInNode, type DataCredential, type DataGroupId, type DataRow } from '../lib/dataSidebarModel'

const GROUPS: { id: DataGroupId; title: string; empty: string }[] = [
  { id: 'inputs', title: '输入字段', empty: '还没有输入字段，可在“输入与输出”里添加' },
  { id: 'nodeOutputs', title: '节点输出', empty: '画布上还没有会产出数据的步骤' },
  { id: 'variables', title: '全局变量', empty: '还没有全局变量，可在“变量”面板添加' },
  { id: 'credentials', title: '凭据', empty: '还没有凭据，可在“设置”里添加' },
]
const AVAILABILITY = { always: '必有', conditional: '条件' }
const CHIP = 'shrink-0 rounded-control bg-[hsl(var(--slate-100))] px-1.5 text-[10px] text-[hsl(var(--muted-foreground))]'

export function DataSidebar() {
  const nodes = useWorkflowStore(s => s.nodes)
  const edges = useWorkflowStore(s => s.edges)
  const variables = useWorkflowStore(s => s.variables)
  const signature = useSignatureStore(s => s.inputs)
  const [credentials, setCredentials] = useState<DataCredential[]>([])
  const [credentialError, setCredentialError] = useState('')
  const [query, setQuery] = useState('')
  const [active, setActive] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const prefix = useId()

  useEffect(() => {
    let live = true
    credentialApi.list().then(res => {
      if (!live) return
      const list = res.data?.credentials
      if (!res.success || !Array.isArray(list)) { setCredentialError(`读取凭据失败：${res.error || '响应格式错误'}。可稍后重试，或到“设置”里检查凭据。`); return }
      setCredentials(list.map(item => ({ name: item.name, description: item.description })))
    }).catch(error => {
      if (live) setCredentialError(`读取凭据失败：${error instanceof Error ? error.message : String(error)}。可稍后重试，或到“设置”里检查凭据。`)
    })
    return () => { live = false; clearTimeout(timer.current) }
  }, [])

  const data = useMemo(() => buildDataSidebar({ signature, nodes, edges, variables, credentials }), [signature, nodes, edges, variables, credentials])
  const selected = nodes.find(node => node.selected)
  const used = useMemo(() => new Set(selected ? referencesInNode(selected, Object.values(data).flat()) : []), [selected, data])

  const say = (text: string) => { setNotice(text); clearTimeout(timer.current); timer.current = setTimeout(() => setNotice(''), 2500) }
  const copy = async (row: DataRow) => {
    try {
      await navigator.clipboard.writeText(row.copyText)
      say(row.isReference ? '已复制引用' : '已复制凭据名称')
    } catch (error) {
      say(`没能复制：${error instanceof Error ? error.message : String(error)}。可手动输入该内容。`)
    }
  }

  const sections = GROUPS.map(group => ({ ...group, all: data[group.id], rows: filterRows(data[group.id], query) }))
  const searching = query.trim() !== ''
  const nothing = searching && sections.every(section => section.rows.length === 0)

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
        <input
          type="search" value={query} onChange={e => setQuery(e.target.value)} aria-label="搜索数据" placeholder="搜索字段、节点输出、变量..."
          className="h-8 w-full rounded-control border border-[hsl(var(--border))] bg-[hsl(var(--card))] pl-8 pr-2 text-[12px]"
        />
      </div>
      <p role="status" aria-live="polite" className="min-h-4 text-[11px] text-[hsl(var(--brand-700))]">{notice}</p>
      {nothing && <p className="px-1 text-[12px] text-[hsl(var(--muted-foreground))]">没有匹配的数据，换个关键词试试</p>}
      {sections.map(section => (!nothing && (!searching || section.rows.length > 0)) && (
        <section key={section.id} className="flex flex-col gap-0.5">
          <h3 className="px-1 text-[12px] font-semibold text-[hsl(var(--slate-800))]">{section.title}</h3>
          {section.id === 'credentials' && credentialError && <p className="px-1 text-[11px] text-[hsl(var(--danger-600))]">{credentialError}</p>}
          {section.all.length === 0 && !(section.id === 'credentials' && credentialError) && <p className="px-1 text-[11px] text-[hsl(var(--muted-foreground))]">{section.empty}</p>}
          <ul className="flex flex-col gap-0.5">
            {section.rows.map((row, index) => {
              const tipId = `${prefix}-${section.id}-${index}`
              const open = active === row.key
              const highlighted = used.has(row.copyText)
              return (
                <li key={row.key}>
                  {row.subgroup && row.subgroup !== section.rows[index - 1]?.subgroup && <div className="px-1 pt-1 text-[10.5px] text-[hsl(var(--muted-foreground))]">{row.subgroup}</div>}
                  <button
                    type="button" onClick={() => void copy(row)} aria-describedby={open ? tipId : undefined} data-highlighted={highlighted ? 'true' : undefined}
                    onMouseEnter={() => setActive(row.key)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(row.key)} onBlur={() => setActive(null)}
                    className={`flex w-full items-center gap-1.5 rounded-control px-2 py-1 text-left text-[12px] hover:bg-[hsl(var(--brand-50))] focus-visible:bg-[hsl(var(--brand-50))] ${highlighted ? 'bg-[hsl(var(--brand-50))] ring-1 ring-[hsl(var(--brand-500)/0.5)]' : ''}`}
                  >
                    <span className="min-w-0 flex-1 truncate">{row.title}{row.group === 'credentials' && row.description && <span className="block truncate text-[11px] text-[hsl(var(--muted-foreground))]">{row.description}</span>}</span>
                    {row.required && <span className={CHIP}>必填</span>}
                    {row.availability && <span className={CHIP}>{AVAILABILITY[row.availability]}</span>}
                    {row.type && <span className={CHIP}>{row.type}</span>}
                  </button>
                  {open && (
                    <div id={tipId} role="tooltip" className="mx-1 mb-1 rounded-control border border-[hsl(var(--border))] bg-[hsl(var(--card))] px-2 py-1 text-[11px] leading-snug text-[hsl(var(--muted-foreground))]">
                      {row.type && <div>类型：{row.type}</div>}
                      <div>来源：{row.source}</div>
                      {row.sample !== undefined && <div>样例：{row.sample}</div>}
                      {row.description && <div>说明：{row.description}</div>}
                      <div>{row.isReference ? '点击复制引用' : '点击复制名称'}</div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
