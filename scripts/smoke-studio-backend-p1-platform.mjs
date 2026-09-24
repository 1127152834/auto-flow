import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { createServer } from 'node:http'
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/p1')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-platform-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-p1-platform-'))
const workspaceDir = join(userData, 'workspace')
const downloads = join(userData, 'downloads')
const fixturePng = join(userData, 'p1-resource.png')
const workflowName = 'P1 WebDAV 正式流程'
const credentialName = `P1临时凭据-${randomUUID().slice(0, 8)}`
const credentialSecret = `P1-secret-${randomUUID()}`
const webdavPassword = `P1-webdav-${randomUUID()}`
const executableIndex = process.argv.indexOf('--executable')
const packagedExecutable = executableIndex === -1 ? null : process.argv[executableIndex + 1]
const checks = []
const webdav = await startWebDav()
let desktop, main, studio, native, runtime

await mkdir(downloads, { recursive: true })
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(fixturePng, Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XwM7WQAAAABJRU5ErkJggg==', 'base64'))

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  runtime = await main.evaluate('window.autoflow.getRuntimeContext()')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await studio.command('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: downloads })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)

  await openSettings(studio)
  await click(studio, '凭据库', 'nav button')
  await click(studio, '新增凭据')
  await setInput(studio, 'input[placeholder="如：我的邮箱"]', credentialName)
  await setInput(studio, 'input[placeholder="用途备注"]', 'P1 正式 Electron 临时验收')
  await setInput(studio, 'input[placeholder="值"]', credentialSecret)
  await click(studio, '保存', 'fieldset button')
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(credentialName)}) && document.body.innerText.includes('••••••')`, 'masked credential metadata')
  const credentials = await api(runtime, '/credentials')
  const credential = credentials.credentials.find(item => item.name === credentialName)
  assert.ok(credential)
  assert.equal(credential.fields[0].masked, '••••••')
  assert.equal(JSON.stringify(credential).includes(credentialSecret), false)
  checkpoint('通过正式凭据库界面写入系统凭据，服务只返回字段名和打码值')

  await click(studio, '留存清理', 'nav button')
  await waitFor(studio, 'document.querySelector(\'input[aria-label="数据保留天数"]\') !== null', 'retention settings')
  await setInput(studio, 'input[aria-label="数据保留天数"]', '9')
  await click(studio, '保存策略')
  await waitFor(studio, "document.body.innerText.includes('清理策略已保存')", 'retention save')
  await click(studio, '立即清理一次')
  await waitFor(studio, "document.body.innerText.includes('清理完成：')", 'manual retention cleanup')
  const retention = await api(runtime, '/retention/config')
  assert.equal(retention.config.data_max_days, 9)
  checkpoint('通过正式留存界面保存策略并执行一次真实工作区清理')

  await click(studio, '存储', 'nav button')
  await waitFor(studio, 'document.querySelector(\'input[placeholder^="WebDAV 地址"]\') !== null', 'WebDAV settings')
  await clickExpression(studio, "(()=>{const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes('WebDAV 远程存储'));return label?.closest('.p-4')?.querySelector('[role=switch]')})()", 'WebDAV enable switch')
  await waitFor(studio, "(()=>{const label=[...document.querySelectorAll('label')].find(e=>e.textContent.includes('WebDAV 远程存储'));return label?.closest('.p-4')?.querySelector('[role=switch]')?.getAttribute('data-state')==='checked'})()", 'WebDAV enabled')
  await setInput(studio, 'input[placeholder^="WebDAV 地址"]', webdav.baseUrl)
  await setInput(studio, 'input[placeholder="用户名"]', 'p1-user')
  await setInput(studio, 'input[placeholder="密码"]', webdavPassword)
  await setInput(studio, 'input[placeholder^="子目录"]', 'workflows')
  await click(studio, '测试连接')
  await waitFor(studio, "document.body.innerText.includes('连接成功！')", 'real WebDAV connection')
  await click(studio, '保存配置')
  await waitFor(studio, "document.body.innerText.includes('配置已保存')", 'WebDAV settings save')
  assert.equal((await api(runtime, '/local-workflows/webdav-config')).config.enabled, true)
  assert.ok(webdav.requests.some(item => item.method === 'PROPFIND' && item.authorization?.startsWith('Basic ')))
  const storedWebDav = JSON.parse(await readFile(join(workspaceDir, 'studio-webdav.json'), 'utf8'))
  assert.equal('password' in storedWebDav, false)
  checkpoint('通过正式存储界面连接本地真实 WebDAV；配置文件不含密码且请求使用系统凭据')
  await click(studio, '关闭全局配置', 'button')

  await click(studio, '图像资源', 'button')
  await waitFor(studio, "document.body.innerText.includes('上传图像')", 'image assets panel')
  await chooseFile(studio, () => click(studio, '上传图像'), fixturePng)
  const asset = await waitForValue(async () => (await api(runtime, '/image-assets')).find(item => item.originalName === 'p1-resource.png'), 'uploaded image asset', 15_000)
  await waitFor(studio, "document.body.innerText.includes('p1-resource.png')", 'uploaded image in formal UI')
  checkpoint('通过正式图像资源面板和原生文件选择输入上传 PNG，文件及索引写入临时工作区')

  const workflow = {
    name: workflowName,
    nodes: [{ id: 'p1-open', type: 'moduleNode', position: { x: 240, y: 180 }, data: { moduleType: 'open_page', label: '打开网页', url: 'https://example.test', config: { imageAssetId: asset.id } } }],
    edges: [], variables: [],
  }
  await api(runtime, '/local-workflows/save-to-folder', { method: 'POST', body: { filename: workflowName, content: workflow } })
  assert.ok(webdav.files.has(`${workflowName}.json`))
  assert.equal((await api(runtime, '/local-workflows/list', { method: 'POST', body: {} })).workflows[0].filename, `${workflowName}.json`)
  assert.equal((await api(runtime, `/local-workflows/load/${encodeURIComponent(`${workflowName}.json`)}`)).content.name, workflowName)
  checkpoint('正式界面保存的 WebDAV 配置驱动真实远程保存、列表与读取；未回退本地目录')

  await click(studio, '', 'button[aria-label="更多操作"]')
  await click(studio, '本地/远程工作流', '[role="menuitem"]')
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(workflowName)})`, 'WebDAV workflow in formal dialog')
  await click(studio, workflowName, '.row-card')
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value===${JSON.stringify(workflowName)} && document.querySelectorAll('.react-flow__node').length===1`, 'WebDAV workflow loaded through formal UI')
  checkpoint('通过正式工具栏入口列出并打开 WebDAV 工作流，草稿替换经过共享离开保护')
  await click(studio, '保存')
  await waitForValue(async () => (await api(runtime, '/workflows')).find(item => item.name === workflowName), 'database workflow save before bundle export', 15_000)

  await click(studio, '导出')
  await click(studio, '整包（含依赖）', 'button')
  await click(studio, '立即导出')
  const bundlePath = await waitForValue(async () => {
    const files = (await readdir(downloads)).filter(name => name.endsWith('.bundle.json') && !name.endsWith('.crdownload'))
    return files.length ? join(downloads, files[0]) : null
  }, 'downloaded workflow bundle', 15_000)
  const bundle = JSON.parse(await readFile(bundlePath, 'utf8'))
  assert.equal(bundle.type, 'webrpa-workflow-bundle')
  assert.equal(bundle.workflow.nodes[0].data.moduleType, 'open_page')
  assert.equal(bundle.images[0].id, asset.id)
  checkpoint('正式导出界面下载工作流整包，并携带已引用图像资源')

  await api(runtime, `/image-assets/${asset.id}`, { method: 'DELETE' })
  await chooseFile(studio, () => click(studio, '导入整包'), bundlePath)
  await click(studio, '执行日志', 'button')
  await waitFor(studio, "document.body.innerText.includes('整包已导入（还原模块 0 个、图片 1 张）')", 'bundle import acknowledgement')
  assert.equal((await api(runtime, '/image-assets')).some(item => item.id === asset.id), true)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 1)
  checkpoint('正式导入入口恢复工作流及已删除图像资源，未直接调用页面 Store 或业务函数')

  await click(studio, '保存')
  await waitForValue(async () => (await api(runtime, '/workflows')).find(item => item.name === workflowName), 'database workflow save after bundle import', 15_000)
  await openSettings(studio)
  await click(studio, '凭据库', 'nav button')
  await click(studio, `删除凭据 ${credentialName}`, 'button')
  await click(studio, '删除', 'button')
  await waitFor(studio, `!document.body.innerText.includes(${JSON.stringify(credentialName)})`, 'credential deleted')
  assert.equal((await api(runtime, '/credentials')).credentials.some(item => item.name === credentialName), false)
  checkpoint('临时凭据通过正式删除确认清理，系统凭据和元数据同步移除')
  await click(studio, '关闭全局配置', 'button')

  await closeStudioWindow()
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  await openSettings(studio)
  await click(studio, '留存清理', 'nav button')
  await waitFor(studio, "document.querySelector('input[aria-label=\"数据保留天数\"]')?.value === '9'", 'retention persisted after normal close')
  await click(studio, '存储', 'nav button')
  await waitFor(studio, `document.querySelector('input[placeholder^="WebDAV 地址"]')?.value === ${JSON.stringify(webdav.baseUrl)} && document.querySelector('input[placeholder="密码"]')?.value === ''`, 'WebDAV metadata persisted without password exposure')
  checkpoint('正常关闭并重开 Studio 后，留存与 WebDAV 配置恢复，密码字段保持为空')

  await capture(studio, join(evidenceDir, 'platform-settings-reopened.png'))
  await click(studio, '关闭全局配置', 'button')
  await click(studio, '图像资源', 'button')
  await waitFor(studio, "document.body.innerText.includes('p1-resource.png')", 'image asset persisted after normal close')
  await capture(studio, join(evidenceDir, 'resource-persisted.png'))
  const buildSha256 = await hashTree(join(root, 'apps/desktop/out'))
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify({
    evidenceId: 'BE-P1-platform-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', buildSha256,
    ...(packagedExecutable ? { executableSha256: createHash('sha256').update(await readFile(packagedExecutable)).digest('hex') } : {}),
    checks, webdavRequestCount: webdav.requests.length,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, webdav: 'local controlled real HTTP WebDAV fixture', credentialStore: 'native OS backend with UI-created temporary credential deleted before shutdown', interaction: 'formal Electron through CDP mouse/keyboard, download and file chooser; public API only for fixture setup, cleanup between bundle operations and evidence reads; no Store or page-internal business function access' },
  }, null, 2) + '\n')
  console.log(`P1 platform formal smoke passed: ${evidenceDir}`)
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  await cleanupSecrets(workspaceDir, credentialName).catch(() => undefined)
  await webdav.close(); await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

async function startWebDav() {
  const files = new Map(), requests = []
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1')
    requests.push({ method: request.method, path: url.pathname, authorization: request.headers.authorization })
    const name = decodeURIComponent(url.pathname.split('/').filter(Boolean).at(-1) ?? '')
    if (request.method === 'PROPFIND') {
      if (request.headers.depth === '0') return response.writeHead(207, { 'content-type': 'application/xml' }).end(multistatus([]))
      return response.writeHead(207, { 'content-type': 'application/xml' }).end(multistatus([...files]))
    }
    if (request.method === 'MKCOL') return response.writeHead(405).end()
    if (request.method === 'PUT') {
      const chunks = []; for await (const chunk of request) chunks.push(chunk)
      files.set(name, Buffer.concat(chunks)); return response.writeHead(201).end()
    }
    if (request.method === 'GET' || request.method === 'HEAD') {
      const value = files.get(name)
      if (!value) return response.writeHead(404).end()
      response.writeHead(200, { 'content-type': 'application/json', 'content-length': value.length })
      return request.method === 'HEAD' ? response.end() : response.end(value)
    }
    if (request.method === 'DELETE') { files.delete(name); return response.writeHead(204).end() }
    response.writeHead(404).end()
  })
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  return { baseUrl: `http://127.0.0.1:${server.address().port}/dav/`, files, requests, close: () => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }) }
}

function multistatus(files) {
  const rows = files.map(([name, value]) => `<d:response><d:href>/dav/workflows/${encodeURIComponent(name)}</d:href><d:propstat><d:prop><d:getcontentlength>${value.length}</d:getcontentlength><d:getlastmodified>${new Date().toUTCString()}</d:getlastmodified></d:prop></d:propstat></d:response>`).join('')
  return `<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">${rows}</d:multistatus>`
}

async function api(context, path, options = {}) {
  const response = await fetch(`${context.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': context.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function openSettings(cdp) { await click(cdp, '', 'button[aria-label="更多操作"]'); await click(cdp, '全局配置', '[role="menuitem"]') }
async function openStudioFromMain(cdp, origin) { await click(cdp, '工作流工作台'); const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target', 30_000); return connectCdp(target.webSocketDebuggerUrl) }
async function waitForTarget(origin, predicate, description, timeoutMs = 15_000) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const target = (await (await fetch(`${origin}/json/list`)).json()).find(predicate); if (target) return target; await wait(100) } throw new Error(`timed out waiting for ${description}`) }
async function waitForNoStudio(origin, timeoutMs = 15_000) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const targets = await (await fetch(`${origin}/json/list`)).json(); if (!targets.some(target => target.type === 'page' && target.url.includes('studio.html'))) return; await wait(100) } throw new Error('timed out waiting for Studio window close') }
async function waitForValue(read, description, timeoutMs) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(150) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();for(const py of [.5,.25,.75])for(const px of [.5,.25,.75]){const x=r.x+r.width*px,y=r.y+r.height*py;if(e.contains(document.elementFromPoint(x,y)))return{x,y}}return null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', buttons: 0, clickCount: 1 }); await wait(100) }
async function clickExpression(cdp, expression, description) { const p = await waitFor(cdp, `(()=>{const e=${expression};if(!e||e.disabled)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, description); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await wait(80) }

async function chooseFile(cdp, trigger, file) {
  await cdp.command('Page.enable')
  await cdp.command('Page.setInterceptFileChooserDialog', { enabled: true })
  const opened = waitForEvent(cdp, 'Page.fileChooserOpened', 10_000)
  await trigger()
  const event = await opened
  await cdp.command('DOM.setFileInputFiles', { files: [file], backendNodeId: event.backendNodeId })
  await cdp.command('Page.setInterceptFileChooserDialog', { enabled: false })
}
function waitForEvent(cdp, method, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { cdp.socket.removeEventListener('message', receive); reject(new Error(`CDP ${method} event timeout`)) }, timeoutMs)
    function receive(event) { const message = JSON.parse(event.data); if (message.method !== method) return; clearTimeout(timer); cdp.socket.removeEventListener('message', receive); resolve(message.params) }
    cdp.socket.addEventListener('message', receive)
  })
}
async function closeStudioWindow() { assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;w.close();return true})()"), true); await wait(250) }
async function capture(cdp, path) { const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(path, data, 'base64') }

async function cleanupSecrets(workspace, name) {
  const workspaceDigest = createHash('sha256').update(resolve(workspace)).digest('hex')
  const credentialDigest = createHash('sha256').update(name).digest('hex')
  const keys = [`studio-webdav:${workspaceDigest}`, `studio-credential:${credentialDigest}`]
  execFileSync('uv', ['run', '--directory', 'apps/backend', 'python', '-c', `from autoflow.infrastructure.credentials.system import SystemCredentialStore; s=SystemCredentialStore(); [s.delete(k) for k in ${JSON.stringify(keys)}]`], { cwd: root, stdio: 'ignore' })
}
async function hashTree(directory) { const hash = createHash('sha256'); for (const name of (await readdir(directory, { recursive: true })).filter(name => /\.(js|css|html)$/.test(name)).sort()) { const path = join(directory, name); if ((await stat(path)).isFile()) hash.update(name).update(await readFile(path)) } return hash.digest('hex') }
