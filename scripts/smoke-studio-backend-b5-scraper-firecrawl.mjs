import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b5')
const evidenceDir = await mkdtemp(join(await mkdir(evidenceRoot, { recursive: true }).then(() => evidenceRoot), 'formal-scraper-firecrawl-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b5-scraper-'))
const workflowName = 'B5 AI网页分析与Firecrawl正式闭环'
const checks = []
const fixture = await startFixture()
let desktop, main, studio
let model
const modules = [
  { type: 'open_page', label: '打开网页', model: false },
  { type: 'ai_smart_scraper', label: 'AI智能爬虫', model: true },
  { type: 'ai_element_selector', label: 'AI元素选择器', model: true },
  { type: 'firecrawl_scrape', label: 'AI单页数据抓取', model: false },
  { type: 'firecrawl_map', label: 'AI网站链接抓取', model: false },
  { type: 'firecrawl_crawl', label: 'AI全站数据抓取', model: false },
]

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] }); main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', { method: 'POST', body: {
    name: 'B5 AI网页验收配置', description: '临时工作区；网页分析与Firecrawl正式验收', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
  } })
  model = await startModel()
  const provider = await api(runtime, '/v1/model-providers/connect', { method: 'POST', body: {
    provider: { name: 'B5 网页分析受控模型', presetId: 'custom-openai-compatible', providerKind: 'openai-compatible', baseUrl: model.baseUrl, apiKey: '', enabled: true, description: '正式 UI 受控验收' },
    selectedModels: [{ modelKey: 'b5-scraper-fixture', displayName: 'B5 AI Task Fixture', tagsJson: ['chat'], contextWindow: 32768, enabled: true, description: '' }],
  } })
  const modelId = provider.models[0].id

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口真实点击打开正式 Studio；动作库为 213，Profile 和模型均来自主应用')

  await click(studio, '新建'); await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  const nodeIds = []
  for (const module of modules) {
    const id = await addNode(studio, module.label, module.type); nodeIds.push(id)
    if (module.type === 'open_page') await setInput(studio, 'input[placeholder="https://example.com"]', fixture.url)
    if (module.type === 'ai_smart_scraper') {
      await chooseFirstModel(studio); await setInput(studio, 'input[placeholder="https://example.com，支持 {变量名}"]', fixture.url); await setInput(studio, 'textarea[placeholder="示例：提取前10项并返回JSON数组"]', '提取页面标题并返回JSON数组'); await setInput(studio, 'input[placeholder="变量名"]', 'scraper_result')
    }
    if (module.type === 'ai_element_selector') {
      await chooseFirstModel(studio); await setInput(studio, 'input[placeholder="https://example.com，支持 {变量名}"]', fixture.url); await setInput(studio, 'textarea[placeholder="如：登录按钮、搜索输入框"]', '页面主标题'); await setInput(studio, 'input[placeholder="变量名"]', 'selector_result')
    }
    if (module.type === 'firecrawl_scrape') {
      await setInput(studio, 'input[placeholder="https://example.com，支持 {变量名}"]', fixture.url); await setInput(studio, 'input[placeholder="scrape_result"]', 'scrape_result'); await setInput(studio, '#timeout', '60000'); await clickLoose(studio, 'span', 'Screenshot')
    }
    if (module.type === 'firecrawl_map') {
      await setInput(studio, 'input[placeholder="https://example.com，支持 {变量名}"]', fixture.url); await setInput(studio, 'input[placeholder="map_result"]', 'map_result'); await setInput(studio, 'input[placeholder="只返回包含关键词的链接，支持 {变量名}"]', 'docs'); await selectNativeOption(studio, '#ignoreSitemap', 'last'); await selectNativeOption(studio, '#ignoreSitemap', 'first')
    }
    if (module.type === 'firecrawl_crawl') {
      await setInput(studio, 'input[placeholder="https://example.com，支持 {变量名}"]', fixture.url); await setInput(studio, 'input[placeholder="crawl_result"]', 'crawl_result'); await setInput(studio, '#maxDepth', '1'); await setInput(studio, '#limit', '2'); await selectNativeOption(studio, '#ignoreSitemap', 'last')
    }
  }
  for (let i = 0; i < nodeIds.length - 1; i++) await connectNodes(studio, nodeIds[i], nodeIds[i + 1])
  await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${modules.length - 1}`, 'workflow edges')
  checkpoint('通过正式画布和属性面板配置 AI 智能爬虫、元素选择器及三个 Firecrawl 节点')

  await click(studio, '保存'); await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName); assert.ok(saved)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), modules.map(item => item.type)); assert.equal(saved.edges.length, modules.length - 1)
  assert.ok(saved.nodes.filter(node => ['ai_smart_scraper', 'ai_element_selector'].includes(node.data.moduleType)).every(node => node.data.modelId === modelId))
  assert.equal(JSON.stringify(saved).includes(model.baseUrl), false)
  checkpoint('正式保存接口写入六节点和模型稳定 ID，不保存模型地址或密钥')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]'); await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0], 'run creation', 20_000)
  const terminal = await waitForValue(async () => { const value = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null }, 'terminal run', 180_000)
  assert.equal(terminal.status, 'completed', JSON.stringify(terminal)); await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered completion', 10_000)
  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/results?cursor=0&limit=20`); const byNode = Object.fromEntries(results.items.map(item => [item.nodeId, item.values]))
  const scraperValue = parseValue(byNode[nodeIds[1]])
  const selectorValue = parseValue(byNode[nodeIds[2]])
  const scrapeValue = parseValue(byNode[nodeIds[3]])
  const mapValue = parseValue(byNode[nodeIds[4]])
  const crawlValue = parseValue(byNode[nodeIds[5]])
  assert.deepEqual(scraperValue, { title: 'Controlled page', items: ['Page A'] })
  assert.equal(selectorValue, 'main h1')
  assert.ok(String(scrapeValue.markdown).includes('Controlled page'))
  assert.ok(!String(scrapeValue.html).includes('fixtureSecret'))
  assert.deepEqual(mapValue.filter(item => item.includes('/docs/')), [fixture.origin + '/docs/a'])
  assert.deepEqual(crawlValue.map(item => item.url), [fixture.url, fixture.origin + '/docs/a'])
  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/artifacts?cursor=0&limit=20`); assert.equal(artifacts.items.length, 1)
  assert.equal((await artifactBytes(runtime, run.runId, artifacts.items[0].artifactId)).subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
  assert.equal(model.requests.filter(request => request.path === '/v1/chat/completions').length, 2)
  checkpoint('真实 worker 经主应用模型完成页面提取和 CSS 选择器生成，Firecrawl 完成单页、链接映射、全站抓取和 PNG 产物')
  await wait(500); assert.deepEqual(cloakProcesses(userData), []); checkpoint('运行结束后 CloakBrowser、临时页和 worker 均已清理')
  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = { evidenceId: 'BE-B5-scraper-firecrawl-formal-electron', checkedAt: new Date().toISOString(), gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build', workflowId: saved.id, profileId: profile.id, modelId, runId: run.runId, checks, nodes: modules.map((module, index) => ({ moduleType: module.type, nodeId: nodeIds[index], result: byNode[nodeIds[index]] })), artifactIds: artifacts.items.map(item => item.artifactId), buildSha256: await buildHash(), boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'CloakBrowser via selected main-application Profile', model: 'local controlled OpenAI-compatible HTTP fixture configured through main application model management', interaction: 'formal Electron via CDP mouse and keyboard; public sidecar APIs only for fixture setup and evidence reads; no Store or page-internal business function access', externalWaiting: 'third-party model providers and Windows/macOS Intel remain separately unverified' } }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n'); console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) { if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined); await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n'); throw error
} finally { studio?.close(); main?.close(); await stop(desktop?.child); await model?.close(); await fixture.close(); await rm(userData, { recursive: true, force: true }) }

function checkpoint(message) { checks.push(message); console.log(message) }
function parseValue(value) { const raw = value && typeof value === 'object' && 'value' in value ? value.value : value; if (typeof raw !== 'string') return raw; try { return JSON.parse(raw) } catch { return raw } }
async function startModel() { const requests = []; const server = createServer(async (request, response) => { const url = new URL(request.url, 'http://127.0.0.1'); let raw = ''; for await (const chunk of request) raw += chunk; const body = raw ? JSON.parse(raw) : {}; requests.push({ method: request.method, path: url.pathname, body }); if (request.method === 'GET' && url.pathname === '/v1/models') return json(response, { data: [{ id: 'b5-scraper-fixture', context_length: 32768 }] }); if (request.method !== 'POST' || url.pathname !== '/v1/chat/completions') return json(response, { error: { message: 'not found' } }, 404); const messages = JSON.stringify(body.messages ?? []); const content = messages.includes('只输出JSON对象') ? '{"selector":"main h1","description":"页面主标题","confidence":99}' : '{"title":"Controlled page","items":["Page A"]}'; return json(response, { choices: [{ message: { content } }] }) }); await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) }); return { baseUrl: `http://127.0.0.1:${server.address().port}/v1`, requests, close: () => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }) } }
function json(response, body, status = 200) { const encoded = Buffer.from(JSON.stringify(body)); response.writeHead(status, { 'content-type': 'application/json', 'content-length': encoded.length }); response.end(encoded) }
async function startFixture() { const server = createServer(async (request, response) => { const url = new URL(request.url, 'http://127.0.0.1'); const origin = `http://127.0.0.1:${server.address()?.port}`; let body, contentType = 'text/html; charset=utf-8'; if (url.pathname === '/sitemap.xml') { body = `<urlset><url><loc>${origin}/docs/from-map</loc></url></urlset>`; contentType = 'application/xml' } else if (url.pathname === '/docs/a') body = '<html><body><main><h1>Page A</h1></main></body></html>'; else body = `<html lang="zh"><head><title>Firecrawl Fixture</title><meta name="description" content="fixture"></head><body><main><h1>Controlled page</h1><a href="${origin}/docs/a">A</a><a href="${origin}/outside">Outside</a></main><script>window.fixtureSecret='not-content'</script></body></html>`; const encoded = Buffer.from(body); response.writeHead(200, { 'content-type': contentType, 'content-length': encoded.length }); response.end(encoded) }); await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) }); const origin = `http://127.0.0.1:${server.address().port}`; return { origin, url: `${origin}/docs/start`, close: () => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }) } }
async function api(runtime, path, options = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) }); if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`); return response.status === 204 ? undefined : response.json() }
async function artifactBytes(runtime, runId, artifactId) { const response = await fetch(`${runtime.sidecar.baseUrl}/api/workflow-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } }); if (!response.ok) throw new Error(`artifact read: ${response.status}`); return Buffer.from(await response.arrayBuffer()) }
async function openStudioFromMain(cdp, origin) { await click(cdp, '工作流工作台'); const target = await waitForValue(async () => (await (await fetch(`${origin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target', 20_000); return connectCdp(target.webSocketDebuggerUrl) }
async function waitForValue(read, description, timeoutMs) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function clickLoose(cdp, selector, text) { const p = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.getClientRects().length&&e.textContent.includes(${JSON.stringify(text)}));if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `visible ${text}`); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.getClientRects().length);if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `input ${selector}`); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100) }
async function selectNativeOption(cdp, selector, edge) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); const key = edge === 'last' ? 'End' : 'ArrowUp'; const vk = edge === 'last' ? 35 : 38; await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 }); await wait(100) }
async function chooseFirstModel(cdp) { const picker = `(()=>{const e=[...document.querySelectorAll('[role="combobox"]')].find(e=>e.getClientRects().length&&e.dataset.disabled===undefined&&e.textContent.includes('请选择'));if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`; let p = await cdp.evaluate(picker); if (!p) { await click(cdp, 'AI 模型设置', 'summary'); p = await waitFor(cdp, picker, 'managed model select') } await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); const option = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll('[role="option"]')].find(e=>e.textContent.includes('B5 AI Task Fixture'));if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, 'managed model option'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...option, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...option, button: 'left', clickCount: 1 }); await waitFor(cdp, `([...document.querySelectorAll('[role="combobox"]')].some(e=>e.getClientRects().length&&e.textContent.includes('B5 AI Task Fixture')))`, 'selected managed model') }
async function addNode(cdp, label, moduleType) { const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),nodes=[...document.querySelectorAll('.react-flow__node')];for(const yf of [.16,.37,.58,.79])for(const xf of [.10,.32,.54,.76]){const x=r.x+r.width*xf,y=r.y+r.height*yf,clear=nodes.every(node=>{const n=node.getBoundingClientRect();return Math.abs((n.left+n.right)/2-x)>170||Math.abs((n.top+n.bottom)/2-y)>90});if(clear&&document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, 'workflow canvas'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]'); const nodeId = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`); await selectNode(cdp, nodeId, moduleType); return nodeId }
async function selectNode(cdp, nodeId, moduleType) { const p = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node ${nodeId}`); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');return !!e?.classList.contains('selected')&&[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))})()`, `${moduleType} config`) }
async function connectNodes(cdp, sourceId, targetId) { const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])')||document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 }); for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 10, y: points.a.y + (points.b.y - points.a.y) * step / 10, button: 'left', buttons: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 }); await wait(120) }
function cloakProcesses(workspace) { return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line)) }
async function capture(cdp, path) { const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(path, data, 'base64') }
async function buildHash() { const hash = createHash('sha256'); for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file))); return hash.digest('hex') }
