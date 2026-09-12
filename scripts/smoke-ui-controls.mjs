import assert from 'node:assert/strict'
import { mkdtemp, mkdir, rm, writeFile, realpath } from 'node:fs/promises'
import { tmpdir, release } from 'node:os'
import { execFileSync } from 'node:child_process'
import { join, resolve } from 'node:path'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'
import { _electron, expect } from '@playwright/test'

const root = resolve(import.meta.dirname, '..')
const evidence = join(root, 'docs/design-system/verification/g0')
await mkdir(evidence, { recursive: true })
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-ui-g0-')))
let electron
let server
const checks = []
const errors = []
const zoomSamples = []
try {
  server = await createServer({
    root: join(root, 'apps/desktop/src/renderer'), configFile: false,
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
  const capture = async name => {
    const png = await electron.evaluate(async ({ BrowserWindow }) => (await BrowserWindow.getAllWindows()[0].webContents.capturePage()).toPNG().toString('base64'))
    await writeFile(join(evidence, name), Buffer.from(png, 'base64'))
  }
  page.setDefaultTimeout(8000)
  page.on('pageerror', error => errors.push(error.message))
  await expect(page.getByRole('heading', { name: 'AutoFlow 控件实验室' })).toBeVisible()
  const swatches = await page.locator('[data-token-swatch]').evaluateAll(elements => elements.map(el => ({ name: el.getAttribute('data-token-swatch'), token: getComputedStyle(el).getPropertyValue(`--color-${el.getAttribute('data-token-swatch')}`).trim(), background: getComputedStyle(el).backgroundColor })))
  for (const swatch of swatches) {
    assert.ok(swatch.token, `Missing runtime token: ${swatch.name}`)
    assert.notEqual(swatch.background, 'rgba(0, 0, 0, 0)', `Transparent swatch: ${swatch.name}`)
  }
  const readOnlyBackground = await page.getByLabel('只读输入').evaluate(el => getComputedStyle(el).backgroundColor)
  const disabledBackground = await page.getByLabel('禁用输入').evaluate(el => getComputedStyle(el).backgroundColor)
  assert.notEqual(disabledBackground, readOnlyBackground, 'Disabled and read-only surfaces must remain distinct')
  const densityInput = page.getByLabel('常规输入')
  assert.equal((await densityInput.boundingBox()).height, 40)
  await page.getByRole('button', { name: '默认 40px' }).click()
  assert.equal((await densityInput.boundingBox()).height, 32)
  await page.getByRole('button', { name: '紧凑 32px' }).click()
  assert.equal((await densityInput.boundingBox()).height, 40)
  await capture('01-lab.png')
  checks.push('isolated userData, development lab entry, runtime colors, read-only/disabled surfaces and 32/40 density')

  await page.getByRole('button', { name: '验证保存' }).click()
  const formChoice = page.getByRole('combobox', { name: '验证内核', exact: true })
  await expect(formChoice).toBeFocused()
  await expect(formChoice).toHaveAttribute('aria-invalid', 'true')
  await formChoice.fill('#0249')
  await page.getByRole('option', { name: 'CloakBrowser 146 · #0249' }).click()
  await expect(page.getByText('表单有修改', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '定位验证内核' }).click()
  await expect(formChoice).toBeFocused()
  await page.getByRole('button', { name: '验证保存' }).click()
  await expect(page.getByText('已保存验证值：kernel-249')).toBeVisible()
  await page.getByRole('button', { name: '重置表单' }).click()
  await expect(formChoice).toHaveValue('')
  await expect(page.getByText('表单未修改', { exact: true })).toBeVisible()
  checks.push('RHF error focus/setFocus, 500-item search/select, dirty, submit and reset')

  await page.getByRole('button', { name: '打开嵌套验证' }).click()
  await page.getByRole('button', { name: '管理内核 · 验证' }).click()
  const inner = page.getByRole('dialog', { name: '内核管理 · 验证' })
  const choice = page.getByRole('combobox', { name: '内层内核', exact: true })
  await page.getByRole('button', { name: '展开 内层内核', exact: true }).click()
  await expect(page.getByRole('listbox')).toBeVisible()
  assert.equal(await page.getByRole('listbox').evaluate(el => el.closest('[role="dialog"]')?.getAttribute('data-overlay-depth')), '1')
  const popupBox = await page.getByRole('listbox').boundingBox()
  assert.ok(popupBox && popupBox.height > 0)
  await expect(page.locator('[data-af-popup]')).toBeInViewport({ ratio: 1 })
  await capture('02-nested-choice.png')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('listbox')).toHaveCount(0)
  await expect(inner).toHaveAttribute('data-state', 'open')
  await expect(choice).toBeFocused()
  for (const key of [...Array(9).fill('Tab'), ...Array(9).fill('Shift+Tab')]) {
    await page.keyboard.press(key)
    assert.equal(await page.evaluate(() => document.activeElement?.closest('[data-overlay-depth]')?.getAttribute('data-overlay-depth')), '1')
  }
  checks.push('nested popup and Tab/Shift+Tab stay inside focus scope; first Escape only closes popup')

  await page.getByRole('button', { name: '模拟忙状态' }).click()
  await page.keyboard.press('Escape')
  await expect(inner).toBeVisible()
  await page.getByRole('button', { name: '结束忙状态' }).click()
  await page.getByRole('button', { name: '打开删除确认' }).click()
  await expect(page.getByRole('button', { name: '取消删除' })).toBeFocused()
  assert.equal(await page.getByRole('alertdialog').getAttribute('data-overlay-depth'), '2')
  await capture('03-third-layer.png')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: '打开删除确认' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: '管理内核 · 验证' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: '打开嵌套验证' })).toBeFocused()
  checks.push('busy guard, third-layer cancel focus and sequential return focus')

  for (const zoom of [1, 1.25, 1.5, 2]) {
    console.log(`Checking zoom ${zoom}`)
    await electron.evaluate(({ BrowserWindow }, factor) => {
      const window = BrowserWindow.getAllWindows()[0]
      window.setSize(1280, 800)
      window.webContents.setZoomFactor(factor)
    }, zoom)
    await page.getByRole('button', { name: '打开嵌套验证' }).click()
    await page.getByRole('button', { name: '管理内核 · 验证' }).click()
    await expect(page.getByRole('button', { name: '关闭内核验证' })).toBeInViewport({ ratio: 1 })
    // Wait for the dialog's real entrance animation before the first pointer hit.
    await expect.poll(() => inner.evaluate(el => el.getAnimations().filter(animation => animation.playState === 'running').length)).toBe(0)
    const toggle = page.getByRole('button', { name: '展开 内层内核', exact: true })
    await toggle.click()
    await expect(page.getByRole('listbox')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('listbox')).toHaveCount(0)
    await expect(choice).toBeFocused()
    await page.keyboard.press('ArrowDown')
    await expect(page.locator('[data-af-popup]')).toBeInViewport({ ratio: 1 })
    await page.keyboard.press('Escape')
    await expect(inner).toHaveAttribute('data-state', 'open')
    zoomSamples.push(await page.evaluate(factor => ({ factor, viewport: [innerWidth, innerHeight], devicePixelRatio }), zoom))
    if (zoom === 2) await capture('04-zoom-200.png')
    const sample = page.getByLabel('滚动样本', { exact: true })
    await sample.focus()
    await page.keyboard.press('End')
    await expect.poll(() => sample.evaluate(el => el.scrollTop)).toBeGreaterThan(0)
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: '管理内核 · 验证' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('button', { name: '打开嵌套验证' })).toBeFocused()
  }
  checks.push('1280x800 at 100/125/150/200%; first mouse and keyboard popup opening, visible actions and keyboard scrolling')
  await electron.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1))
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: '打开嵌套验证' }).click()
  const animation = await page.getByRole('dialog', { name: '浏览器配置 · 验证' }).evaluate(el => getComputedStyle(el).animationDuration)
  assert.ok(parseFloat(animation) < .001)
  assert.deepEqual(errors, [])
  checks.push('reduced-motion and no renderer exceptions')
  await writeFile(join(evidence, 'results.json'), JSON.stringify({ date: new Date().toISOString(), platform: process.platform, arch: process.arch, osVersion: process.platform === 'darwin' ? execFileSync('sw_vers', ['-productVersion'], { encoding: 'utf8' }).trim() : release(), runtime, codeBaseCommit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), sourceIncludesWorkingChanges: Boolean(execFileSync('git', ['status', '--porcelain', '--', 'apps/desktop/src', 'scripts/smoke-ui-controls.mjs', 'apps/desktop/package.json', 'package.json', 'package-lock.json'], { cwd: root, encoding: 'utf8' }).trim()), zoomSamples, checks, errors }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: checks.length, platform: process.platform, checks }, null, 2))
} catch (error) {
  if (electron) {
    const page = await electron.firstWindow()
    await page.screenshot({ path: join(evidence, 'failure.png') }).catch(() => {})
    await writeFile(join(evidence, 'failure-aria.txt'), await page.locator('body').ariaSnapshot()).catch(() => {})
    console.log(JSON.stringify(await page.evaluate(() => ({ viewport: [innerWidth, innerHeight], visual: [visualViewport?.width, visualViewport?.height, visualViewport?.offsetTop], scroll: [scrollX, scrollY], bodyStyle: document.body.style.cssText, dialogs: [...document.querySelectorAll('[role=dialog]')].map(el => ({ rect: el.getBoundingClientRect().toJSON(), state: el.getAttribute('data-state') })), choices: [...document.querySelectorAll('[role=combobox]')].map(el => ({ expanded: el.getAttribute('aria-expanded'), rect: el.getBoundingClientRect().toJSON() })) })), null, 2))
  }
  throw error
} finally {
  await electron?.close()
  await server?.close()
  await rm(userData, { recursive: true, force: true })
}
