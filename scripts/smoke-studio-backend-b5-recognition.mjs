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
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b5')
const evidenceDir = await mkdtemp(join(await mkdir(evidenceRoot, { recursive: true }).then(() => evidenceRoot), 'formal-recognition-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b5-recognition-'))
const fixtures = await mkdtemp(join(tmpdir(), 'autoflow-b5-recognition-fixtures-'))
const workflowName = 'B5 图像识别与验证码正式闭环'
const checks = []
const fixture = await createFixtures(fixtures)
const page = await startCaptchaPage()
let desktop, main, studio

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

const modules = [
  { type: 'face_recognition', label: '人脸识别', inputs: [fixture.face, fixture.face], resultVariable: 'face_result' },
  { type: 'image_ocr', label: '图片OCR', inputs: [fixture.text], resultVariable: 'ocr_result' },
  { type: 'open_page', label: '打开网页', inputs: [page.url], model: false },
  { type: 'ocr_captcha', label: 'OCR识别', inputs: ['#captcha', '#code', 'captcha_result'], autoSubmit: true, submitSelector: '#submit' },
  { type: 'slider_captcha', label: '滑块验证', inputs: ['#slider', 35] },
]

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B5 图像识别验收配置', description: '临时工作区；识别与验证码正式验收', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
      browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  assert.deepEqual(cloakProcesses(userData), [])

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口真实点击打开正式 Studio；动作库为 213，运行 Profile 来自主应用')

  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  const nodeIds = []
  for (const module of modules) {
    const nodeId = await addNode(studio, module.label, module.type)
    nodeIds.push(nodeId)
    if (module.type === 'face_recognition') {
      await setNthInput(studio, 'input[placeholder="输入图片路径或从资源选择"]', 0, module.inputs[0])
      await click(studio, '待识别图片路径', 'label')
      await setNthInput(studio, 'input[placeholder="输入图片路径或从资源选择"]', 1, module.inputs[1])
      await setInput(studio, 'input[placeholder="存储识别结果的变量"]', module.resultVariable)
    } else if (module.type === 'image_ocr') {
      await setInput(studio, 'input[placeholder="输入图片路径或从资源选择"]', module.inputs[0])
      await studio.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await studio.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await wait(100)
      await setInput(studio, 'input[placeholder="存储识别结果的变量"]', module.resultVariable)
    } else if (module.type === 'open_page') {
      await setInput(studio, 'input[placeholder="https://example.com"]', module.inputs[0])
    } else if (module.type === 'ocr_captcha') {
      await setSelectorField(studio, '验证码图片选择器', module.inputs[0])
      await setSelectorField(studio, '验证码输入框选择器（可选）', module.inputs[1])
      await setInput(studio, 'input[placeholder="存储识别出的验证码"]', module.inputs[2])
      await click(studio, '识别后自动提交', 'label')
      await setSelectorField(studio, '提交按钮选择器', module.submitSelector)
    } else if (module.type === 'slider_captcha') {
      await setSelectorField(studio, '滑块选择器', module.inputs[0])
      await setInput(studio, 'input[placeholder="滑动像素距离，支持 {变量名}"]', String(module.inputs[1]))
    }
  }
  for (let index = 0; index < nodeIds.length - 1; index++) await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
  await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${modules.length - 1}`, 'workflow edges')
  checkpoint('通过正式画布和属性面板配置人脸识别、图片OCR、OCR验证码、滑块验证码')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), modules.map(item => item.type))
  assert.equal(saved.edges.length, modules.length - 1)
  checkpoint('正式保存接口写入五节点、四条顺序连线及脱敏路径配置')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0], 'run creation', 20_000)
  const terminal = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'terminal run', 240_000)
  assert.equal(terminal.status, 'completed', JSON.stringify(terminal))
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered completion', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/results?cursor=0&limit=20`)
  const byNode = Object.fromEntries(results.items.map(item => [item.nodeId, item.values]))
  assert.equal(byNode[nodeIds[0]].matched, true)
  assert.ok(Number.isFinite(byNode[nodeIds[0]].confidence))
  assert.ok(String(byNode[nodeIds[1]].text).includes('AUTOFLOW'))
  assert.ok(String(byNode[nodeIds[1]].text).includes('123'))
  const captchaValue = byNode[nodeIds[3]]?.result ?? byNode[nodeIds[3]]?.value ?? byNode[nodeIds[3]]?.text ?? byNode[nodeIds[3]]
  assert.ok(['1234', '1234\n'].includes(String(captchaValue)))
  checkpoint('真实 worker 完成人脸匹配、EasyOCR 文字识别、验证码识别填充并自动提交')

  const pageState = await fetch(`${page.baseUrl}/state`).then(response => response.json())
  assert.equal(pageState.submitted, '1234')
  assert.equal(pageState.distance, 35)
  checkpoint('CloakBrowser 真实页面确认验证码提交值为 1234、滑块位移为 35px')

  await wait(500)
  assert.deepEqual(cloakProcesses(userData), [])
  checkpoint('运行结束后 CloakBrowser 与 worker 均已清理，Profile 锁已释放')
  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B5-recognition-captcha-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowId: saved.id, profileId: profile.id, runId: run.runId, checks,
    nodes: modules.map((module, index) => ({ moduleType: module.type, nodeId: nodeIds[index], result: byNode[nodeIds[index]] })),
    buildSha256: await buildHash(),
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false,
      browserLaunch: 'CloakBrowser via selected main-application Profile for open_page and captcha nodes',
      interaction: 'formal Electron via CDP mouse and keyboard; public sidecar APIs only for fixture setup and evidence reads; no Store or page-internal business function access',
      externalWaiting: 'screen-region OCR permission and Windows/macOS Intel remain separately unverified',
    },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
  await page.close()
  await rm(userData, { recursive: true, force: true })
  await rm(fixtures, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

async function createFixtures(directory) {
  const script = String.raw`from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from skimage import data
root = Path(sys.argv[1])
Image.fromarray(data.astronaut()).save(root / 'face.png')
font_paths = [Path('/System/Library/Fonts/Supplemental/Arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('C:/Windows/Fonts/arial.ttf')]
font = next((p for p in font_paths if p.exists()), None)
if font is None: raise SystemExit('no system font for OCR fixture')
image = Image.new('RGB', (800, 180), 'white')
ImageDraw.Draw(image).text((20, 30), 'AUTOFLOW 123', fill='black', font=ImageFont.truetype(str(font), 96))
image.save(root / 'text.png')
small = Image.new('RGB', (40, 15), 'white')
ImageDraw.Draw(small).text((2, 1), '1234', font=ImageFont.load_default(), fill='black')
small.resize((160, 60), Image.Resampling.NEAREST).save(root / 'captcha.png')
`
  execFileSync('uv', ['run', '--project', 'apps/backend', 'python', '-c', script, directory], { cwd: root, stdio: 'inherit' })
  return { face: join(directory, 'face.png'), text: join(directory, 'text.png'), captcha: join(directory, 'captcha.png') }
}

async function startCaptchaPage() {
  const image = (await readFile(fixture.captcha)).toString('base64')
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1')
    if (request.method === 'GET' && url.pathname === '/') {
      const body = Buffer.from(`<!doctype html><html><body><img id="captcha" src="data:image/png;base64,${image}"><input id="code"><button id="submit" type="button" onclick="document.body.dataset.submitted=document.querySelector('#code').value;fetch('/state?submitted='+encodeURIComponent(document.querySelector('#code').value))">提交</button><div id="slider" style="margin-top:30px;width:30px;height:30px;background:#666"></div><script>let start=0;slider.addEventListener('pointerdown',e=>start=e.clientX);document.addEventListener('pointerup',e=>{const distance=Math.round(e.clientX-start);document.body.dataset.distance=distance;fetch('/state?distance='+distance)});</script></body></html>`)
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'content-length': body.length }); return response.end(body)
    }
    if (request.method === 'GET' && url.pathname === '/state') {
      if (url.searchParams.has('submitted')) server.state.submitted = url.searchParams.get('submitted')
      if (url.searchParams.has('distance')) server.state.distance = Number(url.searchParams.get('distance'))
      const body = Buffer.from(JSON.stringify(server.state)); response.writeHead(200, { 'content-type': 'application/json', 'content-length': body.length }); return response.end(body)
    }
    response.writeHead(404); response.end()
  })
  server.state = { submitted: null, distance: null }
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  return {
    url: `http://127.0.0.1:${server.address().port}/`, baseUrl: `http://127.0.0.1:${server.address().port}`,
    close: () => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }),
  }
}

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function openStudioFromMain(cdp, origin) {
  await click(cdp, '工作流工作台')
  const target = await waitForValue(async () => (await (await fetch(`${origin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target', 20_000)
  return connectCdp(target.webSocketDebuggerUrl)
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) }
  throw new Error(`timed out waiting for ${description}`)
}

async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100)
}

async function setInput(cdp, selector, value) {
  const p = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.getClientRects().length);if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `input ${selector}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100)
}

async function setLabeledInput(cdp, labelText, value) {
  const selector = `(()=>{const l=[...document.querySelectorAll('label')].find(e=>e.textContent.includes(${JSON.stringify(labelText)}));let p=l;let e=null;for(let i=0;i<5&&p&&!e;i++,p=p.parentElement)e=p.querySelector('input');if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`
  const p = await waitFor(cdp, selector, `input ${labelText}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100)
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await wait(100)
}

async function setNthInput(cdp, selector, index, value) {
  const p = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length)[${index}];if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `input ${selector} ${index}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await wait(100)
}

async function setSelectorField(cdp, labelText, value) { await setLabeledInput(cdp, labelText, value) }

async function addNode(cdp, label, moduleType) {
  const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),nodes=[...document.querySelectorAll('.react-flow__node')];for(const yf of [.16,.37,.58,.79])for(const xf of [.10,.32,.54,.76]){const x=r.x+r.width*xf,y=r.y+r.height*yf,clear=nodes.every(node=>{const n=node.getBoundingClientRect();return Math.abs((n.left+n.right)/2-x)>170||Math.abs((n.top+n.bottom)/2-y)>90});if(clear&&document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, 'workflow canvas')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]')
  const nodeId = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`)
  await selectNode(cdp, nodeId, moduleType); return nodeId
}

async function selectNode(cdp, nodeId, moduleType) {
  const p = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node ${nodeId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await waitFor(cdp, `[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))`, `${moduleType} config`)
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])')||document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 }); for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 10, y: points.a.y + (points.b.y - points.a.y) * step / 10, button: 'left', buttons: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 }); await wait(120)
}

function cloakProcesses(workspace) { return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line)) }
async function capture(cdp, path) { const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(path, data, 'base64') }
async function buildHash() { const hash = createHash('sha256'); for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file))); return hash.digest('hex') }
