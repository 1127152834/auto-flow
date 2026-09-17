// Source: WebRPA@5ccb900e, components/workflow/documentation/MarkdownRenderer.tsx; see SOURCE.md for license and adaptation boundaries.
import { useEffect, useMemo, useRef } from 'react'
import '../../styles/table-system.css'

interface MarkdownRendererProps {
  content: string
  highlightKeyword?: string
}

// Mermaid 是个大库（~1MB），且大部分文档不会用到。
// 改成首次发现 .mermaid 节点时再 dynamic import，避免一打开教学文档就把它拉进来。
let mermaidModule: typeof import('mermaid') | null = null
let mermaidInitialized = false
let mermaidLoading: Promise<typeof import('mermaid')> | null = null

async function ensureMermaid() {
  if (mermaidModule) return mermaidModule
  if (mermaidLoading) return mermaidLoading
  mermaidLoading = import('mermaid').then((mod) => {
    mermaidModule = mod
    if (!mermaidInitialized) {
      mod.default.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontSize: 16,
        flowchart: {
          htmlLabels: true,
          curve: 'basis',
          padding: 20,
          nodeSpacing: 80,
          rankSpacing: 80,
        },
      })
      mermaidInitialized = true
    }
    return mod
  })
  return mermaidLoading
}

// HTML 实体转义（防止 markdown 里的 <、>、& 等被当成 HTML 解析）
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 在已转义的文本中插入高亮 <mark>。keyword 也已转义。
function applyHighlight(escapedText: string, escapedKeyword: string): string {
  if (!escapedKeyword) return escapedText
  // 全字符串匹配（不区分大小写）
  const lower = escapedText.toLowerCase()
  const lowerKw = escapedKeyword.toLowerCase()
  let out = ''
  let lastIdx = 0
  let i = 0
  while (i < lower.length) {
    const idx = lower.indexOf(lowerKw, i)
    if (idx === -1) break
    out += escapedText.slice(lastIdx, idx)
    out += `<mark class="bg-yellow-200 text-gray-900 px-0.5 rounded">${escapedText.slice(idx, idx + escapedKeyword.length)}</mark>`
    lastIdx = idx + escapedKeyword.length
    i = lastIdx
  }
  out += escapedText.slice(lastIdx)
  return out
}

// 处理行内样式：`code`、**bold**，并支持高亮
function processInline(text: string, escapedKeyword: string): string {
  // 拆分轮：先按 code 分段，再各段按 bold 分段
  // 最终把所有"普通文本"段经 escapeHtml + applyHighlight 处理；code/bold 内文本同样处理但不再二次解析

  type Seg =
    | { type: 'text'; raw: string }
    | { type: 'code'; raw: string }
    | { type: 'bold'; raw: string }

  let segs: Seg[] = [{ type: 'text', raw: text }]

  // 先按 code 拆
  const codeRe = /`([^`]+)`/g
  segs = segs.flatMap<Seg>((seg) => {
    if (seg.type !== 'text') return [seg]
    const out: Seg[] = []
    let lastIdx = 0
    let m: RegExpExecArray | null
    codeRe.lastIndex = 0
    while ((m = codeRe.exec(seg.raw)) !== null) {
      if (m.index > lastIdx) out.push({ type: 'text', raw: seg.raw.slice(lastIdx, m.index) })
      out.push({ type: 'code', raw: m[1] })
      lastIdx = m.index + m[0].length
    }
    if (lastIdx < seg.raw.length) out.push({ type: 'text', raw: seg.raw.slice(lastIdx) })
    return out
  })

  // 再按 bold 拆 text 段
  const boldRe = /\*\*([^*]+)\*\*/g
  segs = segs.flatMap<Seg>((seg) => {
    if (seg.type !== 'text') return [seg]
    const out: Seg[] = []
    let lastIdx = 0
    let m: RegExpExecArray | null
    boldRe.lastIndex = 0
    while ((m = boldRe.exec(seg.raw)) !== null) {
      if (m.index > lastIdx) out.push({ type: 'text', raw: seg.raw.slice(lastIdx, m.index) })
      out.push({ type: 'bold', raw: m[1] })
      lastIdx = m.index + m[0].length
    }
    if (lastIdx < seg.raw.length) out.push({ type: 'text', raw: seg.raw.slice(lastIdx) })
    return out
  })

  return segs
    .map((seg) => {
      const safe = applyHighlight(escapeHtml(seg.raw), escapedKeyword)
      switch (seg.type) {
        case 'code':
          return `<code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm font-mono text-pink-600">${safe}</code>`
        case 'bold':
          return `<strong class="font-semibold">${safe}</strong>`
        default:
          return safe
      }
    })
    .join('')
}

function buildHTML(content: string, keyword: string): string {
  const escapedKw = escapeHtml(keyword || '')
  const lines = content.split('\n')
  const out: string[] = []

  let inCodeBlock = false
  let codeBuf: string[] = []
  let codeLang = ''
  let inTable = false
  let tableRows: string[][] = []
  let inUList = false
  let inOList = false

  const flushList = () => {
    if (inUList) {
      out.push('</ul>')
      inUList = false
    }
    if (inOList) {
      out.push('</ol>')
      inOList = false
    }
  }
  const flushTable = () => {
    if (!inTable) return
    inTable = false
    if (tableRows.length === 0) return
    out.push('<div class="af-table-scroll af-studio-table-scroll max-w-full overflow-auto my-4" role="region" aria-label="文档表格" tabindex="0"><table class="af-table af-studio-table w-full border-collapse"><thead><tr>')
    const head = tableRows[0]
    for (const cell of head) {
      out.push(`<th scope="col">${processInline(cell, escapedKw)}</th>`)
    }
    out.push('</tr></thead><tbody>')
    for (let r = 1; r < tableRows.length; r++) {
      out.push('<tr>')
      for (const cell of tableRows[r]) {
        out.push(`<td>${processInline(cell, escapedKw)}</td>`)
      }
      out.push('</tr>')
    }
    out.push('</tbody></table></div>')
    tableRows = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 代码块
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        flushList()
        flushTable()
        inCodeBlock = true
        codeBuf = []
        codeLang = line.slice(3).trim().toLowerCase()
      } else {
        inCodeBlock = false
        const codeText = codeBuf.join('\n')
        if (codeLang === 'mermaid') {
          // mermaid 块原文不能转义（Mermaid 自己解析），但用 textContent 注入更安全
          // 这里用 escapeHtml 是因为我们注入到 <div class="mermaid">…</div>，渲染时 mermaid.run 会重新解析其文本内容
          out.push(`<div class="my-8 flex justify-center"><div class="mermaid bg-white p-8 rounded-lg border border-gray-200 shadow-sm w-full max-w-4xl" style="min-height:300px">${escapeHtml(codeText)}</div></div>`)
        } else {
          out.push(`<pre class="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-4"><code class="text-sm font-mono">${escapeHtml(codeText)}</code></pre>`)
        }
        codeLang = ''
      }
      continue
    }
    if (inCodeBlock) {
      codeBuf.push(line)
      continue
    }

    // 表格
    if (line.startsWith('|')) {
      flushList()
      if (!inTable) {
        inTable = true
        tableRows = []
      }
      const cells = line.split('|').slice(1, -1).map((c) => c.trim())
      // 跳过分隔行（"---|---"）
      if (!cells.every((c) => /^-+$/.test(c))) tableRows.push(cells)
      continue
    } else if (inTable) {
      flushTable()
    }

    // 标题
    if (line.startsWith('### ')) {
      flushList()
      out.push(`<h3 class="text-xl font-semibold mt-5 mb-2 text-gray-700">${processInline(line.slice(4), escapedKw)}</h3>`)
      continue
    }
    if (line.startsWith('## ')) {
      flushList()
      out.push(`<h2 class="text-2xl font-bold mt-6 mb-3 text-gray-800 border-b pb-2">${processInline(line.slice(3), escapedKw)}</h2>`)
      continue
    }
    if (line.startsWith('# ')) {
      flushList()
      out.push(`<h1 class="text-3xl font-bold mt-8 mb-4 text-gray-900">${processInline(line.slice(2), escapedKw)}</h1>`)
      continue
    }

    // 列表（无序）
    if (/^- /.test(line)) {
      if (inOList) { out.push('</ol>'); inOList = false }
      if (!inUList) { out.push('<ul class="my-2 space-y-1">'); inUList = true }
      out.push(`<li class="ml-6 list-disc">${processInline(line.slice(2), escapedKw)}</li>`)
      continue
    }
    // 列表（有序）
    const olm = line.match(/^(\d+)\. (.*)/)
    if (olm) {
      if (inUList) { out.push('</ul>'); inUList = false }
      if (!inOList) { out.push('<ol class="my-2 space-y-1">'); inOList = true }
      out.push(`<li class="ml-6 list-decimal">${processInline(olm[2], escapedKw)}</li>`)
      continue
    }

    if (/^---+$/.test(line)) {
      flushList()
      out.push('<hr class="my-6 border-gray-300" />')
      continue
    }
    if (line.trim() === '') {
      flushList()
      continue
    }
    flushList()
    out.push(`<p class="my-3 text-gray-700 leading-relaxed">${processInline(line, escapedKw)}</p>`)
  }

  // 收尾
  flushList()
  flushTable()
  if (inCodeBlock) {
    // 文件末尾未闭合，按已收集的代码块输出
    const codeText = codeBuf.join('\n')
    out.push(`<pre class="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-4"><code class="text-sm font-mono">${escapeHtml(codeText)}</code></pre>`)
  }
  return out.join('')
}

export function MarkdownRenderer({ content, highlightKeyword = '' }: MarkdownRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  // 把 markdown 一次性渲染成 HTML 字符串。比上千个 React 元素快得多。
  const html = useMemo(() => buildHTML(content, highlightKeyword), [content, highlightKeyword])

  // 仅当本次内容包含 mermaid 节点时才异步加载并渲染（一次性）
  useEffect(() => {
    if (!containerRef.current) return
    const elements = containerRef.current.querySelectorAll('.mermaid')
    if (elements.length === 0) return

    let cancelled = false
    ensureMermaid().then((mod) => {
      if (cancelled) return
      elements.forEach((element, index) => {
        const id = `mermaid-${Date.now()}-${index}`
        element.id = id
        try {
          mod.default.run({ nodes: [element as HTMLElement] })
        } catch (error) {
          console.error('Mermaid rendering error:', error)
          element.innerHTML = '<div class="text-red-500 text-sm p-4 border border-red-300 rounded">流程图渲染失败</div>'
        }
      })
    })
    return () => {
      cancelled = true
    }
  }, [html])

  return <div ref={containerRef} dangerouslySetInnerHTML={{ __html: html }} />
}
