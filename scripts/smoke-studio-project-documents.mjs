import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/project-integration')
await mkdir(evidenceRoot, { recursive: true })
const evidence = await mkdtemp(join(evidenceRoot, 'formal-documents-electron-'))
const workspace = await mkdtemp(join(tmpdir(), 'autoflow-project-studio-'))
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
const checks = []
let desktop, main, studio, native
const checkpoint = text => { checks.push(text); console.log(text) }
const name = '项目工作流正式验收'
const workflowName = '项目内创建的真实流程'

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');qaElectron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true")
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'real sidecar', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  assert.ok(runtime.workspaceKey.includes(workspace), 'only the isolated workspace may be tested')
  await click(main, '项目', 'a, button')
  await click(main, '新建项目')
  await input(main, '#project-name', name)
  await click(main, '创建项目')
  await waitFor(main, `document.body?.innerText.includes(${JSON.stringify(name)})`, 'created project')
  if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main, name, '[role="button"],button')
  await waitForProjectPage(main)
  const projectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
  assert.ok(projectId)
  await click(main, '自动化', '[aria-label="项目功能"] button, [aria-label="项目功能"] [role="tab"]')
  await waitFor(main, "document.body?.innerText.includes('还没有自动化')", 'empty project directory')
  checkpoint('通过主窗口真实点击新建项目并进入空自动化目录')

  studio = await openStudio()
  assert.equal(await studio.evaluate("new URL(location.href).searchParams.get('projectId')"), projectId)
  await input(studio, 'input[placeholder="工作流名称"]', workflowName)
  const pane = await waitFor(studio, "(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x+r.width*.5,y:r.y+r.height*.35}})()", 'canvas')
  await studio.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 })
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 })
  await input(studio, '[placeholder="搜索模块（支持拼音）"]', '打开网页')
  await click(studio, '打开网页', '[role="button"]')
  await click(studio, '', '.react-flow__node')
  await input(studio, '[placeholder="https://example.com"]', 'https://example.com/project-owned')
  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'real save')
  const rows = await api(runtime, `/workflows?projectId=${encodeURIComponent(projectId)}`)
  const saved = rows.find(row => row.name === workflowName)
  assert.ok(saved)
  assert.equal(saved.projectId, projectId)
  assert.equal(saved.revision, 1)
  assert.equal(saved.nodes.length, 1)
  assert.equal(saved.nodes[0].data.url, 'https://example.com/project-owned')
  checkpoint('空项目可直接打开绑定项目的 Studio；真实 UI 配置节点并保存到 SQLite')
  await capture(studio, '01-project-workflow-saved.png')

  await input(studio, 'input[placeholder="工作流名称"]', `${workflowName} · 关窗保存`)
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value===${JSON.stringify(`${workflowName} · 关窗保存`)}`, 'edited name before close')
  await closeThroughOs()
  await waitFor(studio, "document.body?.innerText.includes('保存当前工作流？')", 'normal close guard')
  await click(studio, '取消')
  assert.equal((await api(runtime, `/workflows/${saved.id}?projectId=${projectId}`)).revision, 1)
  assert.equal(await studio.evaluate('document.querySelector(\'input[placeholder="工作流名称"]\').value'), `${workflowName} · 关窗保存`)
  checkpoint('系统窗口关闭按钮触发正常关闭保护，取消保留项目草稿和原修订')
  await closeThroughOs()
  await waitFor(studio, "document.body?.innerText.includes('保存当前工作流？')", 'second normal close guard')
  await click(studio, '保存后继续')
  await waitForClosed()
  studio.close(); studio = undefined
  const after = await api(runtime, `/workflows/${saved.id}?projectId=${projectId}`)
  assert.equal(after.revision, 2)
  assert.equal(after.projectId, projectId)
  checkpoint('保存成功后正常关闭；项目归属和修订 2 持久化')

  studio = await openStudio()
  await click(studio, '打开')
  await click(studio, `打开工作流 ${workflowName} · 关窗保存`, '[role="button"]')
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value===${JSON.stringify(`${workflowName} · 关窗保存`)} && document.querySelectorAll('.react-flow__node').length===1`, 'reopened project document')
  await click(studio, '', '.react-flow__node')
  assert.equal(await studio.evaluate('document.querySelector(\'[placeholder="https://example.com"]\').value'), 'https://example.com/project-owned')
  await capture(studio, '02-project-workflow-reopened.png')
  checkpoint('从项目入口重开并通过打开列表恢复名称、节点和参数')
  await closeThroughOs()
  await waitForClosed()
  studio.close(); studio = undefined

  await click(main, '新建自动化')
  await input(main, '[aria-label="自动化名称"],#automation-name', '关联已保存流程')
  await click(main, '', '[aria-label="关联工作流"]')
  await click(main, `${workflowName} · 关窗保存`, '[role="option"]')
  await click(main, '打开 Studio')
  studio = await connectStudio()
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value===${JSON.stringify(`${workflowName} · 关窗保存`)}`, 'selected workflow context')
  assert.equal(await studio.evaluate("new URL(location.href).searchParams.get('workflowId')"), saved.id)
  checkpoint('新建自动化选中项目流程后，可从配置页直接打开对应文档')
  await capture(studio, '03-selected-workflow-context.png')
  await closeThroughOs()
  await waitForClosed()
  studio.close(); studio = undefined
  const report = { result: 'passed', checks, checkedAt: new Date().toISOString(), platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged' : 'development-build', gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), rendererSha256: createHash('sha256').update(await readFile(join(root, 'apps/desktop/out/renderer/studio.html'))).digest('hex'), projectId, workflowId: saved.id, revision: after.revision, boundaries: ['isolated temporary workspace; no user database touched', 'UI mouse/keyboard only; API reads assert persistence', 'document and normal-close acceptance only; no browser execution or project statistics claim'] }
  await writeFile(join(evidence, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidence, ...report }, null, 2))
} catch (error) {
  for (const [label, page] of [['main', main], ['studio', studio]]) if (page) {
    await capture(page, `failure-${label}.png`).catch(() => {})
    await writeFile(join(evidence, `failure-${label}.txt`), await page.evaluate('document.body.innerText').catch(() => 'unavailable'))
  }
  await writeFile(join(evidence, 'result.json'), JSON.stringify({ result: 'failed', checks, error: String(error.stack ?? error), platform: `${process.platform}-${process.arch}` }, null, 2) + '\n')
  console.error(evidence)
  throw error
} finally {
  studio?.close(); native?.close(); main?.close()
  if (desktop) await stop(desktop.child)
  await rm(workspace, { recursive: true, force: true })
}

async function api(runtime, path) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
  assert.ok(response.ok, `read ${path}: ${response.status}`)
  return response.json()
}
async function point(page, selector, text = '') {
  return waitFor(page, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, text || selector)
}
async function click(page, text, selector = 'button') {
  const p = await point(page, selector, text)
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...p, button: 'left', clickCount: 1 })
  await wait(100)
}
async function input(page, selector, text) {
  const p = await point(page, selector)
  for (const type of ['mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...p, button: 'left', clickCount: 3 })
  await page.command('Input.insertText', { text })
  for (const type of ['keyDown', 'keyUp']) await page.command('Input.dispatchKeyEvent', { type, key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
}
async function connectStudio() {
  for (let i = 0; i < 150; i++) {
    const target = (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('studio.html'))
    if (target) {
      const page = await connectCdp(target.webSocketDebuggerUrl)
      await waitFor(page, "document.body?.innerText.includes('模块库')", 'Studio loaded', 30_000)
      return page
    }
    await wait(100)
  }
  throw new Error('Studio target missing')
}
async function openStudio() { await click(main, '工作流工作台'); return connectStudio() }
async function waitForClosed() {
  for (let i = 0; i < 150; i++) {
    if (!(await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).some(t => t.type === 'page' && t.url.includes('studio.html'))) return
    await wait(100)
  }
  throw new Error('Studio did not close normally')
}
async function closeThroughOs() {
  assert.equal(process.platform, 'darwin', 'native close requires separate acceptance on other platforms')
  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()"), true)
  await wait(250)
  execFileSync('osascript', ['-e', 'tell application "System Events"', '-e', `tell (first application process whose unix id is ${desktop.child.pid})`, '-e', 'click (first button of (first window whose name contains "工作流工作台") whose subrole is "AXCloseButton")', '-e', 'end tell', '-e', 'end tell'])
}
async function capture(page, name) {
  const { data } = await page.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(evidence, name), Buffer.from(data, 'base64'))
}
