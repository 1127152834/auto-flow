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
if(retained.length!==213 || new Set(retained.map(n=>n.type)).size!==213)throw Error('Approved 213-node scope changed')
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
const imports = new Map()
const starExports = new Map()
function componentFiles(dir) {
  return fs.readdirSync(path.join(root,dir),{withFileTypes:true}).flatMap(entry => entry.isDirectory() && entry.name !== '__tests__' ? componentFiles(`${dir}/${entry.name}`) : entry.isFile() && /\.tsx?$/.test(entry.name) ? [`${dir}/${entry.name}`] : [])
}
for (const file of componentFiles(`${domain}/components`)) {
  const tree=parse(file)
  const fileImports = new Map()
  const stars=[]
  for (const node of tree.statements) {
    if(ts.isExportAssignment(node) && ts.isIdentifier(node.expression))fileImports.set('default',{specifier:'',symbol:node.expression.text})
    if(ts.isFunctionDeclaration(node) && node.name && node.modifiers?.some(m=>m.kind===ts.SyntaxKind.DefaultKeyword))fileImports.set('default',{specifier:'',symbol:node.name.text})
    if (ts.isExportDeclaration(node)) {
      const specifier=node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)?node.moduleSpecifier.text:''
      if(node.exportClause && ts.isNamedExports(node.exportClause))for(const binding of node.exportClause.elements){
        const symbol=(binding.propertyName??binding.name).text
        if(specifier || symbol!==binding.name.text) fileImports.set(binding.name.text,{specifier,symbol})
      }
      else if(specifier)stars.push(specifier)
    }
    if (!ts.isImportDeclaration(node) || !ts.isStringLiteral(node.moduleSpecifier)) continue
    const specifier = node.moduleSpecifier.text
    const bindings = node.importClause?.namedBindings
    if (bindings && ts.isNamedImports(bindings)) for (const binding of bindings.elements) {
      fileImports.set(binding.name.text, { specifier, symbol: (binding.propertyName ?? binding.name).text })
    }
    if (bindings && ts.isNamespaceImport(bindings)) fileImports.set(bindings.name.text, { specifier, symbol: '*' })
    if (node.importClause?.name) fileImports.set(node.importClause.name.text, { specifier, symbol: 'default' })
  }
  imports.set(file, fileImports)
  starExports.set(file,stars)
  walk(tree,node=>{
    if(ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer &&
       (ts.isIdentifier(node.initializer)||ts.isPropertyAccessExpression(node.initializer))) {
      fileImports.set(node.name.text,{specifier:'',symbol:node.initializer.getText(tree)})
    }
    const namedFunction=ts.isFunctionDeclaration(node) && node.name && /^[A-Z]/.test(node.name.text)
    const namedComponent=ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && /^[A-Z]/.test(node.name.text) && node.initializer && (ts.isArrowFunction(node.initializer) || ts.isCallExpression(node.initializer))
    if(!namedFunction && !namedComponent)return
    const fields=new Set(),tools=new Set(),conditions=[],bindings=[],lazyImports=[]
    if(namedComponent && ts.isCallExpression(node.initializer) && /(^|\.)lazy$/.test(node.initializer.expression.getText(tree))){
      const specifiers=[];let symbol='default'
      walk(node.initializer,part=>{
        if(ts.isCallExpression(part)&&part.expression.kind===ts.SyntaxKind.ImportKeyword&&ts.isStringLiteral(part.arguments[0]))specifiers.push(part.arguments[0].text)
        if(ts.isPropertyAssignment(part)&&part.name.getText(tree)==='default'&&ts.isPropertyAccessExpression(part.initializer))symbol=part.initializer.name.text
      })
      lazyImports.push(...specifiers.map(specifier=>({specifier,symbol})))
    }
    walk(node,n=>{
      if(ts.isPropertyAccessExpression(n)&&/^(config|data|nodeData|node\.data)$/.test(n.expression.getText(tree)))fields.add(n.name.text)
      if(ts.isJsxOpeningElement(n)||ts.isJsxSelfClosingElement(n)) {const tag=n.tagName.getText(tree);if(/^[A-Z]/.test(tag))tools.add(tag)}
      if(ts.isJsxAttribute(n) && ['value','checked','defaultValue','onChange','onValueChange','onCheckedChange'].includes(n.name.getText(tree)) && n.initializer)bindings.push({line:tree.getLineAndCharacterOfPosition(n.getStart(tree)).line+1,attribute:n.name.getText(tree),expression:n.initializer.getText(tree)})
      if(ts.isConditionalExpression(n) || ts.isIfStatement(n))conditions.push({line:tree.getLineAndCharacterOfPosition(n.getStart(tree)).line+1,expression:(ts.isIfStatement(n)?n.expression:n.condition).getText(tree)})
    })
    const row={component:node.name.text,file,line:tree.getLineAndCharacterOfPosition(node.getStart(tree)).line+1,fields:[...fields].sort(),tools:[...tools].sort(),conditions,bindings,lazyImports}
    if(!definitions.has(node.name.text))definitions.set(node.name.text,[])
    definitions.get(node.name.text).push(row)
  })
}
function resolveFile(file,specifier){
  if(!specifier)return file
  const stem=path.posix.normalize(path.posix.join(path.posix.dirname(file),specifier))
  return [`${stem}.tsx`,`${stem}.ts`,`${stem}/index.tsx`,`${stem}/index.ts`].find(candidate=>fs.existsSync(path.join(root,candidate)))
}
function resolveSymbol(file,name,seen=new Set()){
  const key=`${file}#${name}`
  if(!file || seen.has(key))return []
  const next=new Set([...seen,key])
  const local=(definitions.get(name)||[]).filter(row=>row.file===file)
  if(local.length)return local
  const [base,...member]=name.split('.'),binding=imports.get(file)?.get(base)
  if(binding){
    const symbol=binding.symbol==='*'?member.join('.'):binding.symbol
    if(binding.specifier && !binding.specifier.startsWith('.'))return [{external:`${binding.specifier}#${symbol}`}]
    return resolveSymbol(resolveFile(file,binding.specifier),symbol,next)
  }
  return (starExports.get(file)||[]).flatMap(specifier=>resolveSymbol(resolveFile(file,specifier),name,next))
}
function dependencies(type) {
  const pending=evidence.get(type).flatMap(row=>row.components.filter(name=>/^[A-Z]/.test(name)).map(name=>({file:row.file,name})))
  const seen=new Set(),resolved=new Set(),unresolved=new Set(),external=new Set()
  while(pending.length){
    const {file,name}=pending.pop(), key=`${file}#${name}`
    if(seen.has(key))continue
    seen.add(key)
    const matches=resolveSymbol(file,name)
    if(!matches.length){unresolved.add(key);continue}
    for(const row of matches){
      if(row.external){external.add(row.external);continue}
      resolved.add(`${row.file}#${row.component}`)
      pending.push(...row.tools.map(name=>({file:row.file,name})))
      pending.push(...row.lazyImports.map(binding=>({file:resolveFile(row.file,binding.specifier),name:binding.symbol})))
    }
  }
  return {resolved:[...resolved].sort(),unresolved:[...unresolved].sort(),external:[...external].sort()}
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
const verified=JSON.parse(fs.readFileSync(path.join(out,'verified-cases.json'),'utf8'))
const sharedAdvancedCase=verified.find(row=>row.id==='F2.ADV.shared' && ['通过','已实现且已验收'].includes(row.status))
const previousCapabilitiesPath=path.join(out,'capabilities.json')
const previousCapabilities=fs.existsSync(previousCapabilitiesPath)?JSON.parse(fs.readFileSync(previousCapabilitiesPath,'utf8')):[]
const previousById=new Map(previousCapabilities.map(row=>[row.id,row]))
const capabilities=retained.map(n=>{
  const id=`node:${n.type}`
  const previous=previousById.get(id)
  const cases=verified.filter(row=>['通过','已实现且已验收'].includes(row.status) && (row.capability===id || row.preconditions?.nodeType===n.type))
  if(sharedAdvancedCase)cases.push(sharedAdvancedCase)
  const supplementalEvidence=(previous?.evidence??[]).filter(item=>typeof item==='string')
  return {...n,id,status:previous?.status??'缺验收',deliveryBlock:'F2.2',differenceClass:'原版功能迁入',
    verifiedCases:cases.map(row=>({id:row.id,status:'已实现且已验收',level:row.level,evidencePath:row.evidencePath})),
    remaining:previous?.remaining??[{id:`NODE.${n.type}.field-map-and-unique-branches`,status:'缺验收',reason:'注册与默认创建往返已有证据；仅核销 verifiedCases 中已实际验证的字段，剩余独有字段/分支与工具接入尚未逐项核销，不能推定无缺实现'}],
    evidence:[...evidence.get(n.type),...supplementalEvidence.filter((item,index)=>supplementalEvidence.indexOf(item)===index)],toolDependencies:dependencies(n.type),
    reviewRequired:'仅使用既有证据核销；AST 仅提供源码位置，不能自动证明字段行为。共享规则集中验证，各节点验证接入及独有分支。',
    ...(previous?.fieldVerification?{fieldVerification:previous.fieldVerification}:{}),
    ...(previous?.remainingDetails?{remainingDetails:previous.remainingDetails}:{}),
    ...(previous?.backendMigration?{backendMigration:previous.backendMigration}:{}),
  }
})
const tests=capabilities.flatMap(n=>scenarios.map(([kind,steps,expectedUI,stateAssertion])=>({id:`NODE.${n.type}.${kind}`,capability:n.id,status:'缺验收',deliveryBlock:'F2.2',verifiedCases:n.verifiedCases.map(row=>row.id),preconditions:{workspace:'独立测试工作区',document:'空草稿',nodeType:n.type},steps,expectedUI,stateAssertion,expectedIO:kind==='roundtrip'?'工作区文档保存/读取合同；F1 冻结具体 operation ID':kind==='tools'?'逐工具操作合同；需按组件证据展开': '本地编辑；不应隐式启动运行',level:kind==='roundtrip'||kind==='tools'?'Electron E2E + contract':'component + editor rule',evidencePath:null,sourceEvidenceCapability:n.id,remaining:'需将全部字段/分支/工具拆为独立可执行用例；本条不是通过证据'})))
fs.mkdirSync(out,{recursive:true})
for(const [name,value] of [['capabilities.json',capabilities],['test-cases.json',tests],['component-tools.json',[...definitions.values()].flat()]])fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2)+'\n')
console.log(JSON.stringify({nodes:capabilities.length,caseTemplates:tests.length,withoutDirectBranchEvidence:capabilities.filter(n=>!n.evidence.length).map(n=>n.type)}))
