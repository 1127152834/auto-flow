import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const domain = 'apps/desktop/src/renderer/domains/workflows'
const out = path.join(root, 'docs/migration/studio-frontend-completion')
const parse = file => ts.createSourceFile(file, fs.readFileSync(path.join(root, file), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const walk = (node, visit) => { visit(node); ts.forEachChild(node, child => walk(child, visit)) }
const unwrap = node => ts.isAsExpression(node) || ts.isParenthesizedExpression(node) ? unwrap(node.expression) : node
const strings = node => { const result=[]; walk(node,n=>{if(ts.isStringLiteral(n))result.push(n.text)});return result }
const sidebar = parse(`${domain}/lib/moduleCatalog.ts`)
let categories, excluded, extra
walk(sidebar,node=>{
  if(!ts.isVariableDeclaration(node))return
  const name=node.name.getText(sidebar)
  if(name==='sourceModuleCategories')categories=unwrap(node.initializer).elements.map(element=>{
    const properties=Object.fromEntries(element.properties.map(p=>[p.name.getText(sidebar),p.initializer]))
    return {name:properties.name.text,types:strings(properties.modules)}
  })
  if(name==='excludedCategories')excluded=new Set(strings(node.initializer))
  if(name==='excludedModuleTypes')extra=new Set(strings(node.initializer))
})
if(!categories || !excluded || !extra)throw Error('Catalog structure changed; inventory cannot silently skip it')
const retained=categories.filter(c=>!excluded.has(c.name)).flatMap(c=>c.types.filter(t=>!extra.has(t)).map(type=>({type,category:c.name})))
if(retained.length!==284 || new Set(retained.map(n=>n.type)).size!==284)throw Error('Approved 284-node scope changed')
const files=fs.readdirSync(path.join(root,domain,'components/config-panels')).filter(f=>f.endsWith('.tsx')).map(f=>`${domain}/components/config-panels/${f}`)
files.push(`${domain}/components/ConfigPanel.tsx`,`${domain}/editor-store.ts`)
const evidence=new Map(retained.map(n=>[n.type,[]]))
for(const file of files){const tree=parse(file);walk(tree,node=>{
  const comparison=ts.isBinaryExpression(node) && [ts.SyntaxKind.EqualsEqualsEqualsToken,ts.SyntaxKind.EqualsEqualsToken].includes(node.operatorToken.kind)
  const caseClause=ts.isCaseClause(node)
  if(!comparison && !caseClause)return
  const literal=caseClause ? node.expression : ts.isStringLiteral(node.right)?node.right:ts.isStringLiteral(node.left)?node.left:null
  if(!literal || !ts.isStringLiteral(literal))return
  if(!literal || !evidence.has(literal.text))return
  let scope=node
  while(scope.parent && !ts.isFunctionLike(scope) && !ts.isCaseClause(scope) && !ts.isIfStatement(scope) && !ts.isConditionalExpression(scope) && !ts.isJsxExpression(scope))scope=scope.parent
  // A lookup callback mentioning a type is not a configuration dispatch. Never expand it to the enclosing panel.
  if(ts.isFunctionLike(scope))scope=node
  const fields=new Set(),tools=new Set()
  walk(scope,n=>{
    if(ts.isPropertyAccessExpression(n)&&/^(config|data|nodeData|node\.data)$/.test(n.expression.getText(tree)))fields.add(n.name.text)
    if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n))tools.add(n.tagName.getText(tree))
  })
  evidence.get(literal.text).push({kind:scope===node&&!caseClause?'reference':'branch',file,line:tree.getLineAndCharacterOfPosition(node.getStart(tree)).line+1,condition:node.getText(tree),fields:[...fields].sort(),components:[...tools].sort()})
})}
// Resolve named JSX tools to their implementations; keep candidate branches for human review.
const definitions = new Map()
function componentFiles(dir) {
  return fs.readdirSync(path.join(root,dir),{withFileTypes:true}).flatMap(entry => entry.isDirectory() && entry.name !== '__tests__' ? componentFiles(`${dir}/${entry.name}`) : entry.isFile() && entry.name.endsWith('.tsx') ? [`${dir}/${entry.name}`] : [])
}
for (const file of componentFiles(`${domain}/components`)) {
  const tree=parse(file)
  walk(tree,node=>{
    const namedFunction=ts.isFunctionDeclaration(node) && node.name && /^[A-Z]/.test(node.name.text)
    const namedComponent=ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && /^[A-Z]/.test(node.name.text) && node.initializer && (ts.isArrowFunction(node.initializer) || ts.isCallExpression(node.initializer))
    if(!namedFunction && !namedComponent)return
    const fields=new Set(),tools=new Set(),conditions=[],bindings=[]
    walk(node,n=>{
      if(ts.isPropertyAccessExpression(n)&&/^(config|data|nodeData|node\.data)$/.test(n.expression.getText(tree)))fields.add(n.name.text)
      if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)) {const tag=n.tagName.getText(tree);if(/^[A-Z]/.test(tag))tools.add(tag)}
      if(ts.isJsxAttribute(n) && ['value','checked','defaultValue','onChange','onValueChange','onCheckedChange'].includes(n.name.getText(tree)) && n.initializer)bindings.push({line:tree.getLineAndCharacterOfPosition(n.getStart(tree)).line+1,attribute:n.name.getText(tree),expression:n.initializer.getText(tree)})
      if(ts.isConditionalExpression(n) || ts.isIfStatement(n))conditions.push({line:tree.getLineAndCharacterOfPosition(n.getStart(tree)).line+1,expression:(ts.isIfStatement(n)?n.expression:n.condition).getText(tree)})
    })
    const row={component:node.name.text,file,line:tree.getLineAndCharacterOfPosition(node.getStart(tree)).line+1,fields:[...fields].sort(),tools:[...tools].sort(),conditions,bindings}
    if(!definitions.has(node.name.text))definitions.set(node.name.text,[])
    definitions.get(node.name.text).push(row)
  })
}
function dependencies(type) {
  const pending=evidence.get(type).flatMap(row=>row.components).filter(name=>/^[A-Z]/.test(name)),seen=new Set(),resolved=[],unresolved=[]
  while(pending.length){const name=pending.pop();if(seen.has(name))continue;seen.add(name);const matches=definitions.get(name);if(!matches){unresolved.push(name);continue}for(const row of matches){resolved.push(`${row.file}#${row.component}`);pending.push(...row.tools)}}
  return {resolved,unresolved:unresolved.sort()}
}
const scenarios=[
 ['defaults','从动作库添加节点，查看默认配置','显示默认值；不触发外部服务','节点配置与目录/Store 默认值一致'],
 ['branches','逐一切换所有已登记的枚举、开关和条件分支','显隐及错误提示符合字段合同','隐藏字段按明确规则保留或清空'],
 ['validation','输入合法、空、边界和错误类型参数','错误定位到具体字段','无效输入不得伪造服务成功'],
 ['references','选择变量、资源和凭据，并修改或移除引用目标','引用及失效提示正确','序列化保留正确引用身份'],
 ['roundtrip','配置后保存，关闭重开并加载','配置和布局恢复','保存/读取请求内容保持语义一致'],
 ['history','修改配置、复制节点、撤销并重做','每次操作恢复预期内容','复制标识更新，历史不丢配置'],
 ['tools','逐个打开本节点配套工具，覆盖成功/空/失败/取消和迟到结果','正确结果可应用，取消/过期不写回','工具上下文和请求身份匹配'],
]
const capabilities=retained.map(n=>({...n,id:`node:${n.type}`,status:'待核对',evidence:evidence.get(n.type),toolDependencies:dependencies(n.type),reviewRequired:'AST 是候选证据；需核对动态分发、共享组件及所有具体字段分支，不能自动标通过'}))
const tests=capabilities.flatMap(n=>scenarios.map(([kind,steps,expectedUI,stateAssertion])=>({id:`NODE.${n.type}.${kind}`,capability:n.id,status:'待细化',preconditions:{workspace:'独立测试工作区',document:'空草稿',nodeType:n.type},steps,expectedUI,stateAssertion,expectedIO:kind==='roundtrip'?'工作区文档保存/读取合同；F1 冻结具体 operation ID':kind==='tools'?'逐工具操作合同；需按组件证据展开': '本地编辑；不应隐式启动运行',level:kind==='roundtrip'||kind==='tools'?'Electron E2E + contract':'component + editor rule',evidencePath:null,sourceEvidenceCapability:n.id,remaining:'需将全部字段/分支/工具拆为独立可执行用例；本条不是通过证据'})))
fs.mkdirSync(out,{recursive:true})
for(const [name,value] of [['capabilities.json',capabilities],['test-cases.json',tests],['component-tools.json',[...definitions.values()].flat()]])fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)+'\n')
console.log(JSON.stringify({nodes:capabilities.length,caseTemplates:tests.length,withoutDirectBranchEvidence:capabilities.filter(n=>!n.evidence.length).map(n=>n.type)}))
