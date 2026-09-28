import assert from 'node:assert/strict'
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, connectCdp, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-source-studio-')))
const qaIndex = process.argv.indexOf('--qa-directory')
const qa = qaIndex < 0 ? await mkdtemp(join(root, 'docs/qa/studio-smoke-')) : resolve(process.argv[qaIndex + 1])
await mkdir(qa, { recursive: true })
let desktop, studio, native, devServer
const checks = []

try {
  if (process.argv.includes('--dev')) {
    const { resolveConfig } = await import('electron-vite')
    const { createServer } = await import('vite')
    const { config } = await resolveConfig({ root: join(root, 'apps/desktop') }, 'serve', 'development')
    devServer = await createServer({ ...config.renderer, root: join(root, 'apps/desktop/src/renderer'), server: { host: '127.0.0.1', port: 0 } })
    await devServer.listen()
    process.env.ELECTRON_RENDERER_URL = devServer.resolvedUrls.local[0]
  }
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.smokeElectron = process.getBuiltinModule('module').createRequire(process.cwd() + '/package.json')('electron'); true")
  const main = desktop.cdp
  await waitFor(main, `document.body?.innerText.includes('工作流工作台')`, 'overview Studio menu', 30000)
  const status = await waitFor(main, `(async () => { const s = await window.autoflow.getSidecarStatus(); return s.state === 'ready' ? s : null })()`, 'healthy sidecar')
  const headers = { 'x-autoflow-token': status.token }
  assert.equal((await fetch(`${status.baseUrl}/health`, { headers })).status, 200)
  const schema = await (await fetch(`${status.baseUrl}/openapi.json`, { headers })).json()
  assert.ok(schema.paths['/api/workflows']?.get, 'production Studio document route is registered')
  const listing = await fetch(`${status.baseUrl}/api/workflows`, { headers })
  assert.equal(listing.status, 200)
  assert.deepEqual(await listing.json(), [], 'dedicated workspace starts with an empty real document catalog')
  checks.push('main application and sidecar start; production SQLite document route is available')

  assert.ok(await main.evaluate(`(() => { const b = [...document.querySelectorAll('button')].find(b => b.textContent.includes('工作流工作台')); if (!b) return false; b.click(); return true })()`))
  studio = await studioTarget()
  await waitFor(studio, `Boolean(document.querySelector('[aria-label="工作流工作台"]'))`, 'source Studio editor')
  await waitFor(studio, `Boolean(document.querySelector('.react-flow')) && !document.body.innerText.includes('Mock 接口')`, 'production Studio canvas without development mock tools')
  assert.ok((await studio.evaluate(`location.pathname`)).endsWith('/studio.html'))
  const originalId = await studioId()
  await main.evaluate('window.autoflow.openAutomationStudio()')
  assert.equal((await targets()).filter(t => t.url.includes('view=automation-studio')).length, 1)
  assert.equal(await studioId(), originalId)
  await native.evaluate(`smokeElectron.BrowserWindow.fromId(${originalId}).minimize()`)
  await waitFor(native, `smokeElectron.BrowserWindow.fromId(${originalId}).isMinimized()`, 'Studio minimized')
  await main.evaluate('window.autoflow.openAutomationStudio()')
  await waitFor(native, `!smokeElectron.BrowserWindow.fromId(${originalId}).isMinimized()`, 'Studio restored')
  checks.push('overview opens source Studio; repeat open reuses and restores the same window')

  await native.evaluate(`smokeElectron.BrowserWindow.fromId(${originalId}).close()`)
  await waitFor(native, `!smokeElectron.BrowserWindow.fromId(${originalId})`, 'unchanged Studio closes')
  studio.close()
  await main.evaluate('window.autoflow.openAutomationStudio()')
  studio = await studioTarget()
  const reopenedId = await studioId()
  assert.notEqual(reopenedId, originalId)
  await waitFor(studio, `Boolean(document.querySelector('[aria-label="工作流工作台"]'))`, 'reopened source Studio')
  checks.push('unchanged Studio closes and reopens its source editor')

  await native.evaluate(`smokeElectron.BrowserWindow.getAllWindows().find(w => w.id !== ${reopenedId}).close()`)
  await waitFor(native, `(()=>{const w=smokeElectron.BrowserWindow.getAllWindows().find(w=>w.id !== ${reopenedId});return w && !w.isVisible()})()`, 'main interaction owner retained but hidden')
  assert.equal(await studio.evaluate(`Boolean(document.querySelector('[aria-label="工作流工作台"]'))`), true)
  assert.equal((await fetch(`${status.baseUrl}/health`, { headers })).status, 200)
  checks.push('closing the main window hides its interaction owner while Studio and sidecar remain alive')

  const entry = desktop.packaged ? 'packaged' : devServer ? 'development-url' : 'built-html'
  const { data } = await studio.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(qa, `${entry}.png`), data, 'base64')
  // Normal application quit exercises the host shutdown path; finally also
  // terminates only this test's process if an assertion fails.
  await native.evaluate('setTimeout(() => smokeElectron.app.quit(), 50); true')
  // An attached Node inspector can keep the process waiting for its debugger
  // after app.quit. End test inspection before asserting process termination.
  native.close()
  native = undefined
  studio.close()
  desktop.cdp.close()
  for (let i = 0; i < 100 && desktop.child.exitCode === null && desktop.child.signalCode === null; i++) await wait(100)
  assert.ok(desktop.child.exitCode !== null || desktop.child.signalCode !== null, 'desktop exits after normal quit')
  let backendExited = false
  for (let i = 0; i < 50; i++) {
    try { await fetch(`${status.baseUrl}/health`, { signal: AbortSignal.timeout(500) }) }
    catch { backendExited = true; break }
    await wait(100)
  }
  assert.ok(backendExited, 'sidecar exits with desktop')
  checks.push('normal application quit cleans up the sidecar')
  const result = { result: 'passed', entry, platform: process.platform, arch: process.arch, checks }
  await writeFile(join(qa, `${entry}.json`), JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify(result, null, 2))
} finally {
  studio?.close(); desktop?.cdp.close(); native?.close()
  await stop(desktop?.child)
  await devServer?.close()
  await rm(userData, { recursive: true, force: true })
}

async function targets() { return (await fetch(`${desktop.debugOrigin}/json/list`)).json() }
async function studioId() { return native.evaluate("smokeElectron.BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('view=automation-studio')).id") }
async function studioTarget() {
  for (let i = 0; i < 100; i++) {
    const target = (await targets()).find(t => t.type === 'page' && t.url.includes('view=automation-studio'))
    if (target) return connectCdp(target.webSocketDebuggerUrl)
    await wait(100)
  }
  throw new Error('Studio window was not created')
}
