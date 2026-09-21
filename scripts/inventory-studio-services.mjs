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
const registeredRequests = new Set()
function event(name) {
  if (!events.has(name)) events.set(name, { id: `event:${name}`, name, subscriptions: [], emissions: [] })
  return events.get(name)
}
function requestContract(node, tree) {
  const options = node.arguments[1]
  const literalOptions = options && ts.isObjectLiteralExpression(options)
  const property = name => literalOptions ? options.properties.find(member => member.name?.getText(tree) === name) : undefined
  const method = property('method')
  return {
    endpoint: node.arguments[0]?.getText(tree) ?? null,
    method: method && ts.isPropertyAssignment(method) && ts.isStringLiteral(method.initializer)
      ? method.initializer.text : (!options || (literalOptions && !options.properties.some(ts.isSpreadAssignment) && !method) ? 'GET' : 'dynamic'),
    body: property('body')?.getText(tree) ?? null,
    responseType: node.typeArguments?.map(type => type.getText(tree)).join(', ') ?? null,
  }
}
for (const { file, tree } of sources) walk(tree, node => {
  if (!ts.isVariableDeclaration(node) || !node.initializer || !ts.isObjectLiteralExpression(node.initializer) || !/Api$/.test(node.name.getText(tree))) return
  for (const member of node.initializer.properties) {
    if (!member.name) continue
    const id = `${node.name.getText(tree)}.${member.name.getText(tree)}`
    const requests = []
    walk(member, child => {
      if (!ts.isCallExpression(child) || !/^(apiRequest|studioFetch|fetch)$/.test(child.expression.getText(tree))) return
      registeredRequests.add(`${file}:${child.pos}`)
      requests.push({ ...requestContract(child, tree), call: child.getText(tree), ...site(file, tree, child) })
    })
    services.set(id, { id: `service:${id}`, operation: id, ...site(file, tree, member), requests, consumers: [], status: '已登记' })
  }
})
for (const { file, tree } of sources) walk(tree, node => {
  if (ts.isCallExpression(node)) {
    const callee = node.expression.getText(tree)
    const known = services.get(callee)
    if (known) known.consumers.push({ ...site(file, tree, node), call: node.getText(tree) })
    if (/^(studioFetch|fetch)$/.test(callee) || (callee === 'apiRequest' && !registeredRequests.has(`${file}:${node.pos}`))) directRequests.push({ ...requestContract(node, tree), ...site(file, tree, node), call: node.getText(tree) })
    const first = node.arguments[0]
    if (first && ts.isStringLiteral(first)) {
      if (/^(onAssistantUiEvent|window\.addEventListener|(?:this\.)?socket\.on)$/.test(callee)) event(first.text).subscriptions.push({ ...site(file, tree, node), via: callee })
      if (/^(emitAssistantUiEvent|(?:this\.)?socket\??\.emit)$/.test(callee)) event(first.text).emissions.push({ ...site(file, tree, node), via: callee })
    }
  }
  if (ts.isNewExpression(node) && ['CustomEvent', 'Event'].includes(node.expression.getText(tree)) && node.arguments?.[0] && ts.isStringLiteral(node.arguments[0])) {
    event(node.arguments[0].text).emissions.push({ ...site(file, tree, node), via: node.expression.getText(tree), call: node.getText(tree) })
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

const cell = value => String(value ?? '未显式声明').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\|/g, '&#124;').replace(/\r?\n/g, ' ').replace(/`/g, '&#96;')
const location = row => `${row.file}:${row.line}`
const lines = [
  '# F1 服务消费契约矩阵', '',
  '本文件由 scripts/inventory-studio-services.mjs 从当前源码生成，配合 service-inventory.json 阅读。每个操作 ID、实际请求表达式和静态消费入口均已登记；共享传输、事件、命令和业务响应的验证证据集中记录在 contract-matrix-validation.md。dynamic 表示方法由调用参数决定，不能假定为 GET；没有显式响应类型也不能解释为任意响应都合法。', '',
  '## 共享合同与证据', '',
  '| 范围 | 已冻结的前端行为 | 真实后端边界 |', '|---|---|---|',
  '| 命令公共包络 | commandId、success、httpStatus、所有权、同 ID 恢复和冲突拒绝；见 command-schema-validation.md、command-identity-validation.md | 真实动作及持久化由后端实现 |',
  '| 图像元数据和变更响应 | 上传/重命名/移动/删除包络、分页和缺失资源错误；见 image-schema-validation.md、image-command-validation.md | 实际文件系统及原生资源端点 |',
  '| HTTP/SSE | 受控鉴权传输、连接代际隔离、序号补读、断帧不确认和监听器隔离；见 authenticated-transport.md、sse-framing-validation.md | 服务进程重启及真实事件生产 |',
  '| Debug 与运行 | pauseId/controlRevision/runId/executionId、断点、变量、日志和产物分页；见 F3 协议及诊断证据 | 真实浏览器执行、暂停和清理 |',
  '| 节点必填字段 | 生成 DTO、覆盖列表、条件规则、失败重试及连接隔离；见 required-field-service-contract.md | 后端必须按 213 节点目录实现真实预检 |',
  '| 系统路径选择 | 生成请求/响应 DTO、成功/取消/失败和错误码；见 path-service-contract.md 和 path-tool-delivery.md | 真实宿主对话框及平台实机 |',
  '| MCP、凭据与 WebDAV | 保存确认、修订/命令身份、跨连接隔离、离开保护及扩展字段保留；见 mcp-service-contract.md 与 F5 专项证据 | 真实 MCP、秘密存储和远程文件服务 |',
  '| 拾取与录制 | 会话/页面/请求身份、分页、迟到结果隔离、停止及恢复；见 F4 专项证据 | 真实浏览器采集和进程清理 |', '',
  '## 静态服务方法', '',
  '| 操作 ID | 方法与端点表达式 | 请求体表达式 | 声明的响应类型 | 静态消费者数 | 定义位置 | 登记状态 |',
  '|---|---|---|---|---:|---|---|',
]
for (const service of result.services) lines.push(`| ${cell(service.id)} | ${cell(service.requests.map(r => `${r.method} ${r.endpoint}`).join('; '))} | ${cell(service.requests.map(r => r.body).filter(Boolean).join('; ') || null)} | ${cell(service.requests.map(r => r.responseType).filter(Boolean).join('; ') || null)} | ${service.consumers.length} | ${location(service)} | 已登记；验证证据见 contract-matrix-validation.md |`)
lines.push('', '## 事件订阅与发送', '', '| 事件 ID | 订阅位置 | 发送位置 | 状态 |', '|---|---|---|---|')
for (const event of result.events) lines.push(`| ${cell(event.id)} | ${cell(event.subscriptions.map(location).join('; ') || '无静态订阅')} | ${cell(event.emissions.map(location).join('; ') || '无静态发送')} | 已登记；服务事件语义由事件合同专项验证 |`)
lines.push('', '## 直接网络消费入口', '', '| 位置 | 方法与端点表达式 | 请求体 | 状态 |', '|---|---|---|---|')
for (const request of result.directRequests) lines.push(`| ${location(request)} | ${cell(`${request.method} ${request.endpoint}`)} | ${cell(request.body)} | 已登记；共享鉴权、取消和错误语义由传输专项验证 |`)
lines.push('', '## 完整性边界', '',
  '本矩阵冻结前端实际消费入口；必填字段、成功/空结果/拒绝、错误码、读写及幂等、分页、取消和恢复由 contract-matrix-validation.md 引用的共享协议及能力专项验证。上表的类型名不替代 schema 验证。', '',
  '对象 Api 方法的静态扫描不能完整解析 class 方法、动态别名、运行时 URL、IPC 和资源标签请求。静态消费者数为 0 只表示本扫描未发现，不授权删除；这类候选在后端交接中保留为未接入当前 UI。共享 schema-only OpenAPI 已接通，不新增第二套 contracts 包。', '',
  `当前扫描：${result.services.length} 个服务方法、${result.events.length} 个事件、${result.directRequests.length} 个直接请求；AI 画布操作 ${result.assistantActions.length} 项仍在 service-inventory.json 独立登记，不当作 HTTP 操作。`, '')
fs.writeFileSync(path.join(path.dirname(output), 'contract-matrix.md'), lines.join('\n'))
