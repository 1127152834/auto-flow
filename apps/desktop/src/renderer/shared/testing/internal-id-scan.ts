// Runtime render scan (AC5-03): finds internal identifiers and banned terms in what a user can actually see.
import glossary from '../../../shared/copy/glossary.json'

export type InternalIdRule = 'uuid' | 'internal-expression' | 'glossary'
export type InternalIdHit = { text: string; rule: InternalIdRule; where: string; term?: string }
export type ScanOptions = { allowlist?: (string | RegExp)[]; terms?: string[] }

const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi
const EXPRESSION = /PROJECT_INPUTS\[/g
const ATTRIBUTES = ['title', 'aria-label', 'placeholder', 'alt']

const describe = (el: Element) => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}`
const allowed = (text: string, allowlist: (string | RegExp)[]) => allowlist.some(item => typeof item === 'string' ? text.includes(item) : item.test(text))

export function findInternalIds(container: Element, options: ScanOptions = {}): InternalIdHit[] {
  const allowlist = options.allowlist ?? []
  const terms = options.terms ?? (glossary as { term: string }[]).map(entry => entry.term)
  const hits: InternalIdHit[] = []
  const scan = (value: string, where: string) => {
    const found = (text: string, rule: InternalIdRule, term?: string) => {
      if (!allowed(text, allowlist)) hits.push({ text, rule, where, ...(term ? { term } : {}) })
    }
    for (const m of value.matchAll(UUID)) found(m[0], 'uuid')
    for (const m of value.matchAll(EXPRESSION)) found(m[0], 'internal-expression')
    for (const term of terms) if (value.includes(term)) found(value, 'glossary', term)
  }
  const walker = container.ownerDocument.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement
    if (parent && !/^(SCRIPT|STYLE)$/.test(parent.tagName)) scan(node.textContent ?? '', describe(parent))
  }
  for (const el of [container, ...container.querySelectorAll('*')]) {
    for (const name of ATTRIBUTES) {
      const value = el.getAttribute(name)
      if (value) scan(value, `${describe(el)}[${name}]`)
    }
    if ((el instanceof HTMLInputElement && el.type !== 'password' || el instanceof HTMLTextAreaElement) && el.value) scan(el.value, `${describe(el)}[value]`)
  }
  return hits
}
