import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
execFileSync(process.execPath, ['scripts/inventory-studio-services.mjs'], { cwd: root })
const directory = path.join(root, 'docs/migration/studio-frontend-completion')
const inventory = JSON.parse(fs.readFileSync(path.join(directory, 'service-inventory.json'), 'utf8'))
const matrix = fs.readFileSync(path.join(directory, 'contract-matrix.md'), 'utf8')
const operation = name => inventory.services.find(row => row.operation === name)

test('resource upload keeps multipart body and generated response type in the handoff inventory', () => {
  assert.equal(operation('imageAssetApi.upload').requests[0].method, 'POST')
  assert.equal(operation('imageAssetApi.upload').requests[0].body, 'body: formData')
  assert.match(operation('imageAssetApi.upload').requests[0].responseType, /StudioImageUploadResult/)
  assert.equal(operation('imageAssetApi.list').requests[0].method, 'GET')
  assert.equal(operation('imageAssetApi.delete').requests[0].method, 'DELETE')
})
test('transport forwarding is marked dynamic instead of inventing a GET contract', () => {
  const forwarded = inventory.directRequests.find(row => row.file.endsWith('/api/transport.ts'))
  assert.equal(forwarded.method, 'dynamic')
  assert.equal(forwarded.endpoint, 'input')
})
test('the matrix registers every discovered service and event without treating registration as runtime backend proof', () => {
  for (const row of [...inventory.services, ...inventory.events]) assert.ok(matrix.includes(row.id), row.id)
  assert.ok(inventory.services.every(row => row.status === '已登记'))
  assert.match(matrix, /验证证据集中记录在 contract-matrix-validation\.md/)
  assert.match(matrix, /静态消费者数为 0 只表示本扫描未发现，不授权删除/)
})

test('every service family is assigned to the frozen frontend contract matrix', () => {
  const coveredFamilies = new Set([
    'aiAssistantApi', 'browserApi', 'browserScriptTestsApi', 'credentialApi',
    'customModulesApi', 'elementPickerApi', 'executorApi', 'featurePackApi',
    'imageAssetApi', 'inputPromptApi', 'jsScriptApi', 'localWorkflowApi',
    'mcpApi', 'pluginApi', 'recorderApi', 'retentionApi', 'scheduledTaskApi',
    'speechApi', 'sponsorApi', 'systemApi', 'variableTrackingApi', 'workflowApi',
    'workflowBundleApi',
  ])
  const discovered = new Set(inventory.services.map(row => row.operation.split('.')[0]))
  assert.deepEqual([...discovered].sort(), [...coveredFamilies].sort())
})
test('inventory and matrix regenerate deterministically', () => {
  const before = fs.readFileSync(path.join(directory, 'service-inventory.json'), 'utf8')
  execFileSync(process.execPath, ['scripts/inventory-studio-services.mjs'], { cwd: root })
  assert.equal(fs.readFileSync(path.join(directory, 'service-inventory.json'), 'utf8'), before)
  assert.equal(fs.readFileSync(path.join(directory, 'contract-matrix.md'), 'utf8'), matrix)
})
test('direct apiRequest helpers outside Api objects remain visible in the contract inventory',()=>{
  const metadata=inventory.directRequests.find(row=>row.file.endsWith('/lib/requiredFields.ts') && row.endpoint === "'/system/module-required-fields'")
  assert.ok(metadata);assert.equal(metadata.method,'GET');assert.equal(metadata.responseType,'RequiredFieldMetadata')
  const wrapper=inventory.directRequests.find(row=>row.file.endsWith('/api/browserScriptTests.ts') && row.endpoint==='path')
  assert.ok(wrapper);assert.equal(wrapper.method,'dynamic')
})
test('plain Event emissions are recorded alongside CustomEvent emissions',()=>{
  const changed=inventory.events.find(row=>row.name==='studio:transport-changed')
  assert.ok(changed.emissions.some(row=>row.file.endsWith('/api/transport.ts') && row.via==='Event'))
  assert.ok(changed.subscriptions.some(row=>row.file.endsWith('/lib/requiredFields.ts')))
})

test('MCP requests nested in validation helpers keep explicit endpoints and consumers',()=>{
  for(const [name,method] of [['config','GET'],['status','GET'],['save','PUT'],['reload','POST']]){
    const item=operation(`mcpApi.${name}`)
    assert.equal(item.requests[0].method,method)
    assert.ok(item.requests[0].endpoint.includes('/ai-assistant/mcp/'))
    assert.ok(item.consumers.some(row=>row.file.endsWith('/components/MCPConfigPanel.tsx')))
  }
  assert.match(matrix,/mcp-service-contract.md/)
})
