import {test} from 'node:test'
import assert from 'node:assert/strict'
import {auditSources} from './audit-ui-controls.mjs'

test('follows aliases, reexports and dynamic imports; reports dormant sources separately',()=>{
 const files=new Map([
 ['main.tsx',`import {Screen as App} from './barrel'; const lazy=()=>import('./lazy'); export const root=<App/>`],
 ['barrel.ts',`export {Screen} from './domains/page'`],
 ['domains/page.tsx',`import {Input as Field} from '../shared/input'; export const Screen=()=> <>{[1,2].map(x=><input key={x}/>)}<Field/></>`],
 ['shared/input.tsx',`export const Input=()=> <input data-af-control/>`],
 ['lazy.tsx',`export const Lazy=()=> <select/>`],
 ['preview.tsx',`export const Preview=()=> <datalist/>`],
 ])
 const report=auditSources(files,{entries:['main.tsx'],allowlist:[{file:'shared/input.tsx',element:'input',reason:'shared field'}]})
 assert.ok(report.reachable.includes('domains/page.tsx'));assert.ok(report.reachable.includes('lazy.tsx'))
 assert.deepEqual(report.unconnected,['preview.tsx'])
 assert.deepEqual(report.violations.map(x=>`${x.file}:${x.element}`).sort(),['domains/page.tsx:input','lazy.tsx:select','preview.tsx:datalist'])
 assert.ok(report.controls.some(x=>x.element==='Field'&&x.source==='shared/input.tsx'&&x.export==='Input'))
})
test('catches string aliases and style hints, with precise native and CSS exceptions',()=>{
 const report=auditSources(new Map([['main.tsx',`const Native='input'; export const Page=()=> <><Native/><button className="outline-none z-[999]"/></>`],['styles.css','a { color: #fff; }']]),{entries:['main.tsx'],allowlist:[]})
 assert.equal(report.violations.length,2);assert.ok(report.styles.some(x=>x.signal==='z-['));assert.ok(report.styles.some(x=>x.signal==='#fff'))
 const allowed=auditSources(new Map([['shared/input.tsx','export const Input=()=> <input/>']]),{entries:['shared/input.tsx'],allowlist:[{file:'shared/input.tsx',element:'input',reason:'own input appearance'}]})
 assert.equal(allowed.violations.length,0)
})
test('a hidden form-value exception never permits a visible input',()=>{
 const report=auditSources(new Map([['select.tsx','export const Select=()=> <><input type="hidden"/><input type="text"/></>']]),{entries:['select.tsx'],allowlist:[{file:'select.tsx',element:'input',attributes:{type:'hidden'},reason:'form submission only'}]})
 assert.equal(report.violations.length,1)
})
