import ts from 'typescript'
import {readdirSync,readFileSync,writeFileSync,existsSync} from 'node:fs'
import {dirname,join,posix,resolve} from 'node:path'
import {fileURLToPath} from 'node:url'

const native = new Set(['input','textarea','select','datalist','button','summary','details'])
const sourceFile = file => /\.(tsx?|css)$/.test(file) && !/\.test\.|\/tests\/|\/testing\//.test(file)
function resolveImport(files,from,specifier){
 if(!specifier.startsWith('.'))return null
 const base=posix.normalize(posix.join(posix.dirname(from),specifier))
 return [base,...['.ts','.tsx','/index.ts','/index.tsx'].map(ext=>base+ext)].find(file=>files.has(file))??null
}
export function auditSources(files,{entries,allowlist}){
 const graph=new Map(), controls=[], violations=[], styles=[]
 for(const [file,text] of files){
  const ast=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,file.endsWith('.tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS)
  const edges=new Set(),imports=new Map(),aliases=new Map()
  const location=node=>ast.getLineAndCharacterOfPosition(node.getStart()).line+1
  function collect(node){
   if((ts.isImportDeclaration(node)||ts.isExportDeclaration(node))&&node.moduleSpecifier&&ts.isStringLiteral(node.moduleSpecifier)){
    const source=resolveImport(files,file,node.moduleSpecifier.text)
    if(source)edges.add(source)
    if(ts.isImportDeclaration(node)){
     const clause=node.importClause
     if(clause?.name)imports.set(clause.name.text,{source:source??node.moduleSpecifier.text,export:'default'})
     if(clause?.namedBindings&&ts.isNamedImports(clause.namedBindings))for(const item of clause.namedBindings.elements)imports.set(item.name.text,{source:source??node.moduleSpecifier.text,export:item.propertyName?.text??item.name.text})
    }
   }
   if(ts.isCallExpression(node)&&node.expression.kind===ts.SyntaxKind.ImportKeyword&&ts.isStringLiteral(node.arguments[0])){const source=resolveImport(files,file,node.arguments[0].text);if(source)edges.add(source)}
   if(ts.isVariableDeclaration(node)&&ts.isIdentifier(node.name)&&node.initializer&&ts.isStringLiteral(node.initializer))aliases.set(node.name.text,node.initializer.text)
   ts.forEachChild(node,collect)
  }
  collect(ast);graph.set(file,[...edges])
  function inspect(node){
   if(ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node)){
    const tag=node.tagName.getText(ast),element=aliases.get(tag)??tag
    const row={file,line:location(node),element,...imports.get(tag)}
    if(native.has(element)){
     const exception=allowlist.find(entry=>entry.file===file&&entry.element===element&&entry.reason&&Object.entries(entry.attributes??{}).every(([key,value])=>{const attr=node.attributes.properties.find(item=>item.name?.getText(ast)===key);return attr?.initializer&&ts.isStringLiteral(attr.initializer)&&attr.initializer.text===value}))
     controls.push({...row,kind:'native',reason:exception?.reason})
     if(!exception)violations.push(row)
    }else if(/^[A-Z]/.test(tag))controls.push({...row,kind:'component'})
   }
   ts.forEachChild(node,inspect)
  }
  if(!file.endsWith('.css'))inspect(ast)
  // Hints are review evidence, not proof of rendered appearance. Tokens define the palette.
  if(file!=='styles/tokens.css')for(const match of text.matchAll(/appearance-|accent-|outline-none|z-\[|#[0-9a-fA-F]{3,8}\b|overflow-(?:[xy]-)?(?:auto|scroll)/g))styles.push({file,line:text.slice(0,match.index).split('\n').length,signal:match[0]})
 }
 const reachable=new Set()
 function visit(file){if(!files.has(file)||reachable.has(file))return;reachable.add(file);for(const next of graph.get(file)??[])visit(next)}
 entries.forEach(visit)
 const dev=[...files.keys()].filter(file=>file.startsWith('shared/ui-lab/'))
 return {entries,reachable:[...reachable].filter(file=>!dev.includes(file)).sort(),development:dev.sort(),unconnected:[...files.keys()].filter(file=>!reachable.has(file)&&!dev.includes(file)&&!file.endsWith('.css')).sort(),violations,controls,styles}
}
function collectFiles(root,dir=''){
 return readdirSync(join(root,dir),{withFileTypes:true}).flatMap(entry=>{
  const path=posix.join(dir,entry.name)
  return entry.isDirectory()?collectFiles(root,path):sourceFile(path)?[[path,readFileSync(join(root,path),'utf8')]]:[]
 })
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const root=resolve(dirname(fileURLToPath(import.meta.url)),'..')
 const report=auditSources(new Map(collectFiles(join(root,'apps/desktop/src/renderer'))),{entries:['main.tsx'],allowlist:JSON.parse(readFileSync(join(root,'scripts/ui-controls-allowlist.json'),'utf8'))})
 const production=join(root,'apps/desktop/out/renderer')
 const markers=['autoflow-ui-controls-lab','kernel-0249','AutoFlow 控件实验室']
 function findLeaks(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?findLeaks(join(dir,entry.name)):/\.(js|html)$/.test(entry.name)&&markers.some(marker=>readFileSync(join(dir,entry.name),'utf8').includes(marker))?[join(dir,entry.name)]:[])}
 report.production={checked:existsSync(production),leaks:existsSync(production)?findLeaks(production):[]}
 writeFileSync(join(root,'docs/design-system/verification/ui-controls-audit.json'),JSON.stringify(report,null,2)+'\n')
 console.log(JSON.stringify({reachable:report.reachable.length,development:report.development.length,unconnected:report.unconnected,violations:report.violations,styleHints:report.styles.length,production:report.production},null,2))
 if(report.violations.length||report.production.leaks.length)process.exitCode=1
}
