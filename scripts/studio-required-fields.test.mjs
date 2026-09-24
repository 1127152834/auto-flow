import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {createHash} from 'node:crypto'
import {spawnSync} from 'node:child_process'
const root = new URL('../', import.meta.url)
const read = path => JSON.parse(fs.readFileSync(new URL(path, root), 'utf8'))
const metadata = () => read('apps/desktop/src/renderer/domains/workflows/development/module-required-fields.json')
const removedNotifications = ['notify_discord','notify_dingtalk','notify_wecom','notify_bark','notify_slack','notify_msteams','notify_pushover','notify_pushbullet','notify_gotify','notify_serverchan','notify_pushplus','notify_ntfy','notify_matrix','notify_rocketchat']
const python = code => {
  const result = spawnSync('python3', ['-c', code], {cwd: root, encoding: 'utf8'})
  assert.equal(result.status, 0, result.stderr + result.stdout)
  return JSON.parse(result.stdout)
}

// Independent oracle: inspect the frozen update call sites by source line and
// read their literal definitions. Never import/exec either reference module.
const sourceOracle = () => python(`
import ast,json
from pathlib import Path
base=Path('reference/WebRPA/backend/app/services')
tree=ast.parse((base/'ai_assistant_module_schemas.py').read_text())
groups={n.target.id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name)}
patch=ast.parse((base/'ai_assistant_module_schemas_autofix.py').read_text())
groups.update({n.target.id:ast.literal_eval(n.value) for n in patch.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name)})
initial=next(n for n in tree.body if isinstance(n,ast.For))
names=[n.id for n in initial.iter.elts]
updates=sorted((n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='_ALL_SCHEMAS' and n.func.attr=='update'),key=lambda n:n.lineno)
names += [n.args[0].id for n in updates if n.args[0].id != initial.target.id]
schemas={}
for name in names: schemas.update(groups[name])
print(json.dumps(schemas,ensure_ascii=False))
`)

function projectRules(schemas, approved) {
  const result = {requiredFields: {}, conditionalRequired: {}, fieldLabels: {}}
  for (const name of approved) {
    const schema = schemas[name]
    assert.ok(schema, `frozen source must actually define ${name}`)
    const defaults = schema.defaults || {}
    const fields = (schema.required || []).filter(field => !Object.hasOwn(defaults, field))
    if (fields.length) result.requiredFields[name] = fields
    const labels = Object.fromEntries(Object.entries(schema.desc || {}).filter(([,label]) => typeof label === 'string' && label.trim()))
    if (Object.keys(labels).length) result.fieldLabels[name] = labels
    const condition = schema.conditional_required
    if (condition?.map && Object.keys(condition.map).length) {
      result.conditionalRequired[name] = {
        field: condition.field, default: condition.default ?? null,
        map: Object.fromEntries(Object.entries(condition.map).map(([mode,fields]) => [mode,fields.filter(field => !Object.hasOwn(defaults,field))])),
      }
    }
  }
  result.fieldLabels.python_script.useBuiltinPython = 'True 使用 AutoFlow 随包 Python；False 可通过 pythonPath 指定已安装的 Python'
  return result
}

test('all three frozen metadata targets regenerate exactly without executing source modules', () => {
  const result = spawnSync('python3', ['scripts/export-studio-required-fields.py', '--check'], {cwd: root, encoding: 'utf8'})
  assert.equal(result.status, 0, result.stderr + result.stdout)
})

test('all 213 entries match final source update order and every excluded source node is absent', () => {
  const schemas = sourceOracle()
  const approved = read('docs/migration/studio-frontend-completion/capabilities.json').map(entry => entry.type).sort()
  const coverage = read('docs/migration/studio-frontend-completion/required-field-source-coverage.json')
  const data = metadata()
  assert.equal(approved.length, 213)
  assert.equal(new Set(approved).size, 213)
  assert.equal(coverage.approvedCount, 213)
  assert.equal(coverage.coveredCount, 213)
  assert.deepEqual(coverage.uncovered, [])
  assert.deepEqual(coverage.covered, approved)
  assert.deepEqual(data.coveredModules, approved)
  const expected = projectRules(schemas, approved)
  for (const name of ['requiredFields','conditionalRequired','fieldLabels']) assert.deepEqual(data[name], expected[name])
  for (const excluded of Object.keys(schemas).filter(name => !approved.includes(name))) {
    assert.ok(!data.coveredModules.includes(excluded), `${excluded} must not reappear`)
    for (const map of Object.values(expected)) assert.ok(!Object.hasOwn(map, excluded))
  }
  for (const removed of [...removedNotifications,'real_keyboard','db_connect','mongodb_connect','postgresql_connect','redis_connect','sqlite_connect','sqlserver_connect','oracle_connect','dp_open_page']) {
    assert.ok(!approved.includes(removed))
    assert.ok(!data.coveredModules.includes(removed))
  }
  assert.ok(data.coveredModules.includes('notify_telegram'))
  assert.ok(data.coveredModules.includes('notify_webhook'))
})

test('AUTOFIX then PRIORITY and mode overrides retain exact field names and empty rules', () => {
  const data = metadata()
  assert.deepEqual(data.requiredFields.ssh_connect, ['host','username','password'])
  assert.deepEqual(data.requiredFields.ssh_execute_command, ['command'])
  assert.deepEqual(data.requiredFields.set_variable, ['variableName','variableValue'])
  assert.deepEqual(data.requiredFields.send_email, ['recipientEmail','emailSubject','emailContent'])
  const originalKeyboard = sourceOracle().keyboard_action
  assert.deepEqual(originalKeyboard.required, ['keySequence'])
  assert.equal(data.requiredFields.keyboard_action, undefined)
  assert.ok(!data.coveredModules.includes('keyboard_action'))
  assert.deepEqual(data.requiredFields.open_page, ['url'])
  assert.deepEqual(data.conditionalRequired, {wait: {field: 'waitType', default: 'time', map: {time: [], selector: ['selector'], navigation: []}}})
  assert.equal(data.requiredFields.wait, undefined)
  for (const empty of ['group','note','screenshot']) {
    assert.ok(data.coveredModules.includes(empty))
    assert.equal(data.requiredFields[empty], undefined)
  }
  assert.equal(originalKeyboard.desc.keySequence, '按键序列，如 Enter / Ctrl+A / Ctrl+Shift+S')
  assert.equal(data.fieldLabels.keyboard_action, undefined)
  assert.equal(data.fieldLabels.send_email.recipientEmail, '收件人邮箱(多个用逗号分隔)')
})

test('source and license digests cover both frozen schema files and preserve provenance', () => {
  const coverage = read('docs/migration/studio-frontend-completion/required-field-source-coverage.json')
  const digest = path => createHash('sha256').update(fs.readFileSync(new URL(path,root))).digest('hex')
  assert.deepEqual(coverage.sources.map(item => item.source), [
    'reference/WebRPA/backend/app/services/ai_assistant_module_schemas.py',
    'reference/WebRPA/backend/app/services/ai_assistant_module_schemas_autofix.py',
  ])
  for (const source of coverage.sources) assert.equal(source.sha256, digest(source.source))
  assert.equal(coverage.source, coverage.sources[0].source)
  assert.equal(coverage.sha256, coverage.sources[0].sha256)
  assert.equal(coverage.license.path, 'reference/WebRPA/LICENSE')
  assert.equal(coverage.license.sha256, digest(coverage.license.path))
  assert.equal(coverage.sourceRevision, metadata().schemaRevision)
  assert.ok(coverage.mergeOrder.indexOf('AUTOFIX_SCHEMAS') < coverage.mergeOrder.indexOf('_MULTIMODE_REQUIRED_FIX'))
  assert.ok(coverage.mergeOrder.indexOf('_MULTIMODE_REQUIRED_FIX') < coverage.mergeOrder.indexOf('PRIORITY_SCHEMAS'))
  assert.ok(coverage.mergeOrder.indexOf('PRIORITY_SCHEMAS') < coverage.mergeOrder.indexOf('PRIORITY_SCHEMAS_2'))
  assert.ok(coverage.modifications.length > 0)
})

test('production domain literal matches frontend metadata and has no runtime source dependency', () => {
  const data = python(`
import ast,json
from pathlib import Path
p=Path('apps/backend/src/autoflow/domain/workflows/required_fields.py')
tree=ast.parse(p.read_text())
imports=[node.module for node in tree.body if isinstance(node,ast.ImportFrom)]
assert imports == ['typing']
assert all(isinstance(node,(ast.Expr,ast.ImportFrom,ast.AnnAssign)) for node in tree.body)
node=next(node for node in tree.body if isinstance(node,ast.AnnAssign))
assert node.target.id=='MODULE_REQUIRED_FIELDS'
print(json.dumps(ast.literal_eval(node.value),ensure_ascii=False))
`)
  assert.deepEqual(data, metadata())
})

test('Python runtime description preserves the explicit AutoFlow adaptation', () => {
  assert.match(sourceOracle().python_script.desc.useBuiltinPython, /Python313/)
  assert.match(metadata().fieldLabels.python_script.useBuiltinPython, /AutoFlow 随包 Python/)
  assert.doesNotMatch(metadata().fieldLabels.python_script.useBuiltinPython, /313/)
})
