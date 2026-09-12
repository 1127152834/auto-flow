import assert from 'node:assert/strict'
import { mkdtemp, mkdir, rm, writeFile, realpath } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'
import { _electron, expect } from '@playwright/test'

const root = resolve(import.meta.dirname, '..')
const evidence = join(root, 'docs/design-system/verification/t5-g0')
await mkdir(evidence, { recursive: true })
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-ui-g0-')))
let electron
let server
const errors = []
try {
  server = await createServer({
    root: join(root, 'apps/desktop/src/renderer'), configFile: false,
    cacheDir: join(userData, 'node_modules/.vite'),
    optimizeDeps: { include: ['@radix-ui/react-radio-group'] },
    plugins: [react(), tailwind()], server: { host: '127.0.0.1', port: 0 },
  })
  await server.listen()
  const address = server.httpServer.address()
  assert.ok(address && typeof address !== 'string')
  electron = await _electron.launch({
    args: [join(root, 'apps/desktop'), `--user-data-dir=${userData}`], cwd: root,
    env: { ...process.env, ELECTRON_RENDERER_URL: `http://127.0.0.1:${address.port}/#/__ui` },
  })
  const actualDirectory = await electron.evaluate(({ app }) => app.getPath('userData'))
  assert.equal(await realpath(actualDirectory), userData)
  const runtime = await electron.evaluate(() => ({ electron: process.versions.electron, chromium: process.versions.chrome }))
  const page = await electron.firstWindow()
  const settle = async () => page.evaluate(async () => {
    await new Promise(requestAnimationFrame)
    await Promise.all(document.getAnimations().filter(animation => animation.effect?.getTiming().iterations !== Infinity).map(animation => animation.finished.catch(() => {})))
    await new Promise(requestAnimationFrame)
  })
  page.setDefaultTimeout(8000)
  page.on('pageerror', error => errors.push(error.stack ?? error.message))
  await page.evaluate(() => {
    globalThis.__overlayTrace = []
    globalThis.__scrollCalls = []
    for (const [prototype, method] of [[HTMLElement.prototype, 'focus'], [Element.prototype, 'scrollIntoView'], [Element.prototype, 'scrollTo']]) {
      const original = prototype[method]
      prototype[method] = function (...args) {
        const before = [...document.querySelectorAll('[aria-label="内核滚动内容"]')].map(el => el.scrollTop)
        const active = document.activeElement?.getAttribute('id')
        const result = original.apply(this, args)
        globalThis.__scrollCalls.push({ method, tag: this.tagName, id:this.id, active, name: this.getAttribute('aria-label'), depth:this.closest('[data-overlay-depth]')?.getAttribute('data-overlay-depth'), before, after:[...document.querySelectorAll('[aria-label="内核滚动内容"]')].map(el => el.scrollTop), args, stack: new Error().stack })
        globalThis.__scrollCalls = globalThis.__scrollCalls.slice(-30)
        return result
      }
    }
    const record = type => {
      globalThis.__overlayTrace.push({ type, time: performance.now(), scroll: scrollY, layers: [...document.querySelectorAll('[data-overlay-depth]')].map(el => [el.getAttribute('data-overlay-depth'), el.getAttribute('data-state')]), popup: [...document.querySelectorAll('[data-af-popup]')].map(el => [el.closest('[data-overlay-depth]')?.getAttribute('data-overlay-depth'), el.hasAttribute('data-exiting')]) })
      globalThis.__overlayTrace = globalThis.__overlayTrace.slice(-24)
    }
    document.addEventListener('keydown', event => record(event.key), true)
    document.addEventListener('scroll', event => record('scroll:' + event.target.nodeName + ':' + event.target.className + ':top=' + event.target.scrollTop), true)
  })
  await expect(page.getByRole('heading', { name: 'AutoFlow 控件实验室' })).toBeVisible()
  const samples = []
  for (let round = 0; round < 24; round++) {
    const zoom = [1, 1.25, 1.5, 2][round % 4]
    await electron.evaluate(({ BrowserWindow }, factor) => BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(factor), zoom)
    await page.getByRole('button', { name: '打开嵌套验证' }).click()
    await page.getByRole('button', { name: '管理内核 · 验证' }).click()
    const inner = page.getByRole('dialog', { name: '内核管理 · 验证' })
    const popup = page.locator('[data-af-popup]')
    const toggle = page.getByRole('button', { name: '展开 内层内核', exact: true })
    await toggle.scrollIntoViewIfNeeded()
    await settle()
    await toggle.click()
    await expect(popup).toBeVisible()
    const atOpen = await popup.evaluate(el => ({ owner: el.closest('[data-overlay-depth]')?.getAttribute('data-overlay-depth'), scroll: scrollY }))
    if (round % 3 === 1) await settle()
    if (round % 3 === 2) {
      // A real ancestor scroll dismisses React Aria's non-modal popup before Escape.
      await inner.getByLabel('内核滚动内容').evaluate(el => el.dispatchEvent(new Event('scroll')))
      await expect(popup).toHaveCount(0)
      await toggle.scrollIntoViewIfNeeded()
      await settle()
      await toggle.click()
      await expect(popup).toBeVisible()
    }
    const beforeEscape = await popup.count()
    await page.keyboard.press('Escape')
    await expect(inner).toHaveAttribute('data-state', 'open')
    await expect(popup).toHaveCount(0)
    samples.push({ round, zoom, atOpen, beforeEscape })
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: '管理内核 · 验证' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: '打开嵌套验证' })).toBeFocused()
    console.log('G0 round', round + 1, zoom)
  }
  assert.deepEqual(errors, [])
  await writeFile(join(evidence, 'stress-results.json'), JSON.stringify({ date: new Date().toISOString(), runtime, samples, errors }, null, 2))
} catch (error) {
  if (electron) {
    const page = await electron.firstWindow()
    console.log('OVERLAY_TRACE', JSON.stringify(await page.evaluate(() => globalThis.__overlayTrace)))
    await page.screenshot({ path: join(evidence, 'failure.png') }).catch(() => {})
    await writeFile(join(evidence, 'failure-aria.txt'), await page.locator('body').ariaSnapshot()).catch(() => {})
    console.log(JSON.stringify(await page.evaluate(() => ({ viewport: [innerWidth, innerHeight], visual: [visualViewport?.width, visualViewport?.height, visualViewport?.offsetTop], scroll: [scrollX, scrollY], bodyStyle: document.body.style.cssText, dialogs: [...document.querySelectorAll('[role=dialog]')].map(el => ({ rect: el.getBoundingClientRect().toJSON(), state: el.getAttribute('data-state') })), choices: [...document.querySelectorAll('[role=combobox]')].map(el => ({ expanded: el.getAttribute('aria-expanded'), rect: el.getBoundingClientRect().toJSON() })) })), null, 2))
  }
  await writeFile(join(evidence, 'failure-trace.json'), JSON.stringify(await (await electron.firstWindow()).evaluate(() => ({events:globalThis.__overlayTrace, calls:globalThis.__scrollCalls})), null, 2))
  throw error
} finally {
  await electron?.close()
  await server?.close()
  await rm(userData, { recursive: true, force: true })
}
