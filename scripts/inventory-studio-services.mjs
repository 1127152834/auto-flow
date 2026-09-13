import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const domain = 'apps/desktop/src/renderer/domains/workflows'
const output = path.join(root, 'docs/migration/studio-frontend-completion/service-inventory.json')
const manifest = new Map(JSON.parse(fs.readFileSync(path.join(root, domain, 'source-manifest.json'), 'utf8')).map(row => [row.target, row.source]))
const walk = (node, visit) => { visit(node); ts.forEachChild(node, child => walk(child, visit)) }
const files = dir => fs.readdirSync(path.join(root, dir), { withFileTypes: true }).flatMap(entry => {
  if (entry.isDirectory()) return ['tests', '__tests__'].includes(entry.name) ? [] : files(`${dir}/${entry.name}`)
  return /\.tsx?$/.test(entry.name) && !entry.name.endsWith('.d.ts') ? [`${dir}/${entry.name}`] : []
})
const sources = [...files(domain), 'apps/desktop/src/renderer/app/StudioApp.tsx'].map(file => ({ file, tree: ts.createSourceFile(file, fs.readFileSync(path.join(root, file), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX) }))
const site = (file, tree, node) => ({ file, line: tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1, source: manifest.get(file) ?? null })
const services = new Map(), events = new Map(), directRequests = [], assistantActions = []
function event(name) {
  if (!events.has(name)) events.set(name, { id: `event:${name}`, name, subscriptions: [], emissions: [] })
  return events.get(name)
}
for (const { file, tree } of sources) walk(tree, node => {
  if (!ts.isVariableDeclaration(node) || !node.initializer || !ts.isObjectLiteralExpression(node.initializer) || !/Api$/.test(node.name.getText(tree))) return
  for (const member of node.initializer.properties) {
    if (!member.name) continue
    const id = `${node.name.getText(tree)}.${member.name.getText(tree)}`
    const requests = []
    walk(member, child => {
      if (!ts.isCallExpression(child) || !/^(apiRequest|studioFetch|fetch)$/.test(child.expression.getText(tree))) return
      requests.push({ call: child.getText(tree), ...site(file, tree, child) })
    })
    services.set(id, { id: `service:${id}`, operation: id, ...site(file, tree, member), requests, consumers: [], status: '待核对' })
  }
})
for (const { file, tree } of sources) walk(tree, node => {
  if (ts.isCallExpression(node)) {
    const callee = node.expression.getText(tree)
    const known = services.get(callee)
    if (known) known.consumers.push({ ...site(file, tree, node), call: node.getText(tree) })
    if (/^(studioFetch|fetch)$/.test(callee)) directRequests.push({ ...site(file, tree, node), call: node.getText(tree) })
    const first = node.arguments[0]
    if (first && ts.isStringLiteral(first)) {
      if (/^(onAssistantUiEvent|window\.addEventListener|(?:this\.)?socket\.on)$/.test(callee)) event(first.text).subscriptions.push({ ...site(file, tree, node), via: callee })
      if (/^(emitAssistantUiEvent|(?:this\.)?socket\??\.emit)$/.test(callee)) event(first.text).emissions.push({ ...site(file, tree, node), via: callee })
    }
  }
  if (ts.isNewExpression(node) && node.expression.getText(tree) === 'CustomEvent' && node.arguments?.[0] && ts.isStringLiteral(node.arguments[0])) {
    event(node.arguments[0].text).emissions.push({ ...site(file, tree, node), via: 'CustomEvent', call: node.getText(tree) })
  }
  if (file.endsWith('/aiAssistantSkills.ts') && ts.isCaseClause(node) && ts.isStringLiteral(node.expression)) {
    let parent = node.parent
    while (parent && !ts.isSwitchStatement(parent)) parent = parent.parent
    if (parent?.expression.getText(tree) === 'action') assistantActions.push({ id: `assistant:${node.expression.text}`, action: node.expression.text, ...site(file, tree, node), status: '待核对' })
  }
})
const result = {
  scope: '源码调用候选，不等于已实现服务或已验证可达性；包含待移除死代码，动态别名/字符串需人工核对。',
  services: [...services.values()].sort((a, b) => a.id.localeCompare(b.id)),
  events: [...events.values()].sort((a, b) => a.id.localeCompare(b.id)),
  assistantActions,
  directRequests,
}
fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n')
console.log(JSON.stringify({ services: services.size, events: events.size, assistantActions: assistantActions.length, directRequests: directRequests.length }))
