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
const evidence = join(root, 'docs/design-system/verification/t3')
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
  await page.evaluate(() => {
    globalThis.__overlayTrace = []
    const record = type => {
      globalThis.__overlayTrace.push({ type, time: performance.now(), scroll: scrollY, layers: [...document.querySelectorAll('[data-overlay-depth]')].map(el => [el.getAttribute('data-overlay-depth'), el.getAttribute('data-state')]), popup: [...document.querySelectorAll('[data-af-popup]')].map(el => [el.closest('[data-overlay-depth]')?.getAttribute('data-overlay-depth'), el.hasAttribute('data-exiting')]) })
      globalThis.__overlayTrace = globalThis.__overlayTrace.slice(-24)
    }
    document.addEventListener('keydown', event => record(event.key), true)
    document.addEventListener('scroll', event => record('scroll:' + event.target.nodeName), true)
  })
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

  for (const zoom of [1, 1.25, 1.5, 2, 1, 1.25, 1.5, 2]) {
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
    assert.equal(await page.locator('[data-af-popup]').evaluate(el => el.closest('[data-overlay-depth]')?.getAttribute('data-overlay-depth')), '1')
    await page.keyboard.press('Escape')
    await expect(inner).toHaveAttribute('data-state', 'open')
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
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: '打开嵌套验证' })).toBeFocused()
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  const textSection = page.getByRole('region', { name: '按钮与文字控件' })
  const sampleSave = page.getByRole('button', { name: '保存样本', exact: true })
  await sampleSave.scrollIntoViewIfNeeded()
  const idleWidth = (await sampleSave.boundingBox()).width
  await sampleSave.click()
  await expect(sampleSave).toBeDisabled()
  assert.equal((await sampleSave.boundingBox()).width, idleWidth)
  await expect(sampleSave).toHaveText('保存样本正在保存…')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  assert.equal(await sampleSave.locator('.af-spinner').evaluate(el => getComputedStyle(el).animationName), 'none')
  await page.getByRole('button', { name: '结束加载样本' }).click()
  const searchSample = page.getByRole('searchbox', { name: '搜索样本', exact: true })
  await page.getByRole('button', { name: '清除搜索', exact: true }).click()
  await expect(searchSample).toHaveValue(''); await expect(searchSample).toBeFocused()
  const passwordSample = page.getByLabel('可显隐密码', { exact: true })
  await passwordSample.focus()
  await passwordSample.evaluate(el => el.setSelectionRange(0, 6))
  await page.getByRole('button', { name: '显示密码', exact: true }).click()
  await expect(passwordSample).toHaveAttribute('type', 'text')
  await expect(passwordSample).toHaveValue('sample-only-key')
  await expect(passwordSample).toBeFocused()
  await page.getByRole('button', { name: '隐藏密码', exact: true }).click()
  await expect(passwordSample).toHaveAttribute('type', 'password')
  const normalText = page.getByRole('textbox', { name: '常规文字', exact: true })
  assert.equal(await normalText.evaluate(el => getComputedStyle(el).fontSize), '14px')
  await page.getByRole('button', { name: '默认 40px' }).click()
  assert.equal(await normalText.evaluate(el => getComputedStyle(el).fontSize), '12px')
  assert.equal((await normalText.boundingBox()).height, 32)
  await page.getByRole('button', { name: '紧凑 32px' }).click()
  await textSection.evaluate(el => el.scrollIntoView({ block: 'start' }))
  await capture('05-text-controls.png')
  await searchSample.evaluate(el => el.scrollIntoView({ block: 'start' }))
  await capture('08-search-password.png')
  checks.push('T3 loading width/name, static reduced spinner, search clear, reveal and 32/40 typography')

  await page.getByRole('button', { name: '提交文字样本' }).click()
  const boundName = page.getByRole('textbox', { name: '绑定名称', exact: true })
  await expect(boundName).toBeFocused()
  await expect(boundName).toHaveAttribute('aria-invalid', 'true')
  await boundName.fill('中文样本 / English')
  await expect(boundName).not.toHaveAttribute('aria-invalid', 'true')
  await page.getByRole('button', { name: '提交文字样本' }).click()
  await expect(page.getByText('文字样本已保存：中文样本 / English')).toBeVisible()
  await page.getByRole('button', { name: '重置文字样本' }).click()
  await expect(boundName).toHaveValue('')
  await electron.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2))
  await page.getByRole('button', { name: '聚焦绑定名称' }).click()
  await expect(boundName).toBeFocused()
  await expect(boundName).toBeInViewport({ ratio: 1 })
  await capture('06-text-form-200.png')
  checks.push('T3 RHF error/ref/reset, Unicode fill and 200% focused field visibility; IME not claimed')

  await electron.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1))
  await page.goto(`http://127.0.0.1:${address.port}/#/profiles`)
  // The DEV lab is chosen at module bootstrap, so a hash change alone cannot leave it.
  await page.reload()
  await expect(page.getByText('本地服务正常', { exact: true })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: '新建配置', exact: true }).click()
  const realDialog = page.getByRole('dialog', { name: '新建浏览器配置', exact: true })
  const realName = realDialog.getByRole('textbox', { name: '名称', exact: true })
  await expect(realName).toBeVisible()
  assert.equal(await realName.evaluate(el => getComputedStyle(el).borderTopColor), 'rgb(139, 131, 119)')
  await realName.focus()
  await capture('07-real-browser-form.png')
  await realDialog.getByRole('button', { name: '取消', exact: true }).click()
  await expect(realDialog).toHaveCount(0)
  assert.deepEqual(errors, [])
  checks.push('real browser configuration form opens against isolated sidecar, shared input focus/style and cancel; no saved data')
  await writeFile(join(evidence, 'results.json'), JSON.stringify({ date: new Date().toISOString(), platform: process.platform, arch: process.arch, osVersion: process.platform === 'darwin' ? execFileSync('sw_vers', ['-productVersion'], { encoding: 'utf8' }).trim() : release(), runtime, codeBaseCommit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), sourceIncludesWorkingChanges: Boolean(execFileSync('git', ['status', '--porcelain', '--', 'apps/desktop/src', 'scripts/smoke-ui-controls.mjs', 'apps/desktop/package.json', 'package.json', 'package-lock.json'], { cwd: root, encoding: 'utf8' }).trim()), zoomSamples, checks, errors }, null, 2) + '\n')
  console.log(JSON.stringify({ passed: checks.length, platform: process.platform, checks }, null, 2))
} catch (error) {
  if (electron) {
    const page = await electron.firstWindow()
    console.log('OVERLAY_TRACE', JSON.stringify(await page.evaluate(() => globalThis.__overlayTrace)))
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
