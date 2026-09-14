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
    services.set(id, { id: `service:${id}`, operation: id, ...site(file, tree, member), requests, consumers: [], status: '待核对' })
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
  '本文件由 scripts/inventory-studio-services.mjs 从当前源码生成，配合 service-inventory.json 阅读。它逐项登记实际声明及静态消费入口，不是全量已冻结合同或验收通过声明。dynamic 表示必须追踪调用参数，不能假定为 GET；没有显式响应类型也不能解释为任意响应都合法。', '',
  '## 已有局部合同与证据', '',
  '| 范围 | 当前约束 | 尚未完成 |', '|---|---|---|',
  '| 命令公共包络 | commandId、success、查询 httpStatus 由 OpenAPI 生成；见 command-schema-validation.md、command-identity-validation.md | 各事件业务 payload、持久化命令、独立运行身份 |',
  '| 图像元数据和变更响应 | 上传/重命名 asset 包络，目录位置及删除数量；见 image-schema-validation.md、image-command-validation.md | 全量网络运行时校验、实际文件系统及宿主资源端点 |',
  '| HTTP/SSE | 共用受控传输；空行确认事件，序号补读，EOF 半包不提交；见 authenticated-transport.md、sse-framing-validation.md | epoch/服务重启后的状态重建 |',
  '| Debug | resume/step 绑定 pauseId/controlRevision/commandId，并发幂等、原 ID 查询恢复；404/405/409/422；见 debug-pause-command-contract.md | 断点修订、变量修改、独立 runId、真实执行及清理 |',
  '| 必填字段规则 | 生成DTO、覆盖列表、条件规则、失败重试及连接代际隔离；见 required-field-service-contract.md | 冻结源仅覆盖69个保留节点，215个无源规则，不当作完整校验 |',
  '| 系统路径选择 | 生成请求/响应DTO、POST/405/422、成功/取消/失败校验；见 path-service-contract.md 和 path-tool-delivery.md | 真实宿主对话框、运行中取消宿主请求、各平台实机 |',
  '| MCP 配置 | 生成 DTO、保存确认、跨连接在途隔离、离开保护及扩展字段保留；见 mcp-service-contract.md、mcp-text-validation.md、mcp-leave-validation.md | 真实 MCP 服务、权限矩阵和跨客户端 revision |',
  '| WebDAV 设置 | HTTP/业务确认、失败重试、互斥和迟到保护，Mock不声称真实连接；见 webdav-settings-protection.md | 生成DTO、写入修订、真实远程文件与凭据服务 |',
  '| 拾取 | 原文档/节点/字段响应隔离；见 picker-context-validation.md、similar-atomic-validation.md | 跨入口 session/request 所有权、启动取消和清理重试 |', '',
  '## 静态服务方法', '',
  '| 操作 ID | 方法与端点表达式 | 请求体表达式 | 声明的响应类型 | 静态消费者数 | 定义位置 | 验收状态 |',
  '|---|---|---|---|---:|---|---|',
]
for (const service of result.services) lines.push(`| ${cell(service.id)} | ${cell(service.requests.map(r => `${r.method} ${r.endpoint}`).join('; '))} | ${cell(service.requests.map(r => r.body).filter(Boolean).join('; ') || null)} | ${cell(service.requests.map(r => r.responseType).filter(Boolean).join('; ') || null)} | ${service.consumers.length} | ${location(service)} | 待逐项核对；局部已验证项见上表 |`)
lines.push('', '## 事件订阅与发送', '', '| 事件 ID | 订阅位置 | 发送位置 | 状态 |', '|---|---|---|---|')
for (const event of result.events) lines.push(`| ${cell(event.id)} | ${cell(event.subscriptions.map(location).join('; ') || '无静态订阅')} | ${cell(event.emissions.map(location).join('; ') || '无静态发送')} | 字段/关联身份/恢复语义仍需核对 |`)
lines.push('', '## 直接网络消费入口', '', '| 位置 | 方法与端点表达式 | 请求体 | 状态 |', '|---|---|---|---|')
for (const request of result.directRequests) lines.push(`| ${location(request)} | ${cell(`${request.method} ${request.endpoint}`)} | ${cell(request.body)} | 需核对鉴权、取消、错误及资源读取 |`)
lines.push('', '## 完整性边界', '',
  '每个保留操作仍须登记必填字段、成功/空结果/拒绝示例、错误码、读写及幂等规则、分页上限、取消后的查询与清理，并关联 verified-cases.json 中的实际用例。上表的类型名不替代 schema 验证。', '',
  '对象 Api 方法的静态扫描不能完整解析 class 方法、动态别名、运行时 URL、IPC 和资源标签请求。静态消费者数为 0 只表示本扫描未发现，不授权删除。共享 schema-only OpenAPI 已接通，不新增第二套 contracts 包。', '',
  `当前扫描：${result.services.length} 个服务方法、${result.events.length} 个事件、${result.directRequests.length} 个直接请求；AI 画布操作 ${result.assistantActions.length} 项仍在 service-inventory.json 独立登记，不当作 HTTP 操作。`, '')
fs.writeFileSync(path.join(path.dirname(output), 'contract-matrix.md'), lines.join('\n'))
