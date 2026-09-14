import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {spawnSync} from 'node:child_process'
const root=new URL('../',import.meta.url)
test('frozen required-field data regenerates exactly without executing source modules',()=>{
 const result=spawnSync('python3',['scripts/export-studio-required-fields.py','--check'],{cwd:root,encoding:'utf8'})
 assert.equal(result.status,0,result.stderr+result.stdout)
})
test('coverage accounts for every retained node and excludes removed nodes',()=>{
 const read=path=>JSON.parse(fs.readFileSync(new URL(path,root),'utf8'))
 const coverage=read('docs/migration/studio-frontend-completion/required-field-source-coverage.json')
 const retained=read('docs/migration/studio-frontend-completion/capabilities.json').map(x=>x.type)
 assert.equal(coverage.coveredCount,69);assert.equal(coverage.uncovered.length,215)
 assert.deepEqual([...coverage.covered,...coverage.uncovered].sort(),retained.sort())
 const data=read('apps/desktop/src/renderer/domains/workflows/development/module-required-fields.json')
 for(const map of [data.requiredFields,data.conditionalRequired,data.fieldLabels])assert.ok(Object.keys(map).every(key=>coverage.covered.includes(key)))
 assert.ok(!data.coveredModules.includes('real_keyboard'))
})
