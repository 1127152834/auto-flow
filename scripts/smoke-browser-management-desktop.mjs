import assert from 'node:assert/strict'
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import { launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { kernelExecutablePath, smokeCooperativeShutdown } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const version = '146.0.7680.80'
const originalName = 'Browser desktop smoke'
const editedName = 'Browser desktop smoke edited'
const copyName = 'Browser desktop smoke copy'
const userData = await mkdtemp(join(tmpdir(), 'autoflow-browser-desktop-smoke-'))
let desktop

try {
  for (const installedVersion of [version, '145.0.7632.6']) {
    const kernelDirectory = join(userData, 'data', 'kernels', `chromium-${installedVersion}`)
    const kernelExecutable = kernelExecutablePath(kernelDirectory)
    await mkdir(resolve(kernelExecutable, '..'), { recursive: true })
    await writeFile(kernelExecutable, 'autoflow browser desktop smoke fixture\n', { mode: 0o755 })
  }

  process.env.PYTHONTZPATH = ''
  delete process.env.CLOAKBROWSER_BINARY_PATH
  delete process.env.CLOAKBROWSER_LICENSE_KEY
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  const { cdp } = desktop
  const sidecar = await waitFor(cdp, `(async () => {
    const status = await window.autoflow.getSidecarStatus()
    if (status.state !== 'ready') return null
    const response = await fetch(status.baseUrl + '/health', { headers: { 'x-autoflow-token': status.token } })
    const health = response.ok ? await response.json() : null
    return health?.status === 'ok' && health?.instanceId === status.instanceId ? status : null
  })()`, 'authenticated sidecar health', 30_000)

  await clickText(cdp, '浏览器配置')
  await waitFor(cdp, `document.querySelector('main h1')?.textContent === '浏览器配置'`, 'browser management page')
  await setViewport(cdp, 1280, 900)
  await assertNoHorizontalOverflow(cdp, '1280px empty profile list')

  await clickText(cdp, '新建配置')
  await waitFor(cdp, `document.body?.innerText.includes('新建浏览器配置')`, 'new profile dialog')
  await setValue(cdp, '#profile-name', originalName)
  await setValue(cdp, '#profile-description', 'Created through the real Electron workspace')
  await clickText(cdp, '内核与代理')
  await waitFor(cdp, `Boolean(document.querySelector('#profile-browser-kernel option[value="public|${version}"]'))`, 'installed kernel option')

  await assertNoHorizontalOverflow(cdp, '1280px profile form', '新建浏览器配置')
  await setViewport(cdp, 1024, 800)
  await assertNoHorizontalOverflow(cdp, '1024px profile form', '新建浏览器配置')
  await clickText(cdp, '管理内核')
  await waitFor(cdp, `document.body?.innerText.includes('CloakBrowser 内核管理')`, 'kernel manager dialog')
  await setViewport(cdp, 1280, 900)
  await assertNoHorizontalOverflow(cdp, '1280px kernel manager', 'CloakBrowser 内核管理')
  await assertCardColumns(cdp, '内核版本卡片', 2)
  await setViewport(cdp, 1024, 800)
  await assertNoHorizontalOverflow(cdp, '1024px kernel manager', 'CloakBrowser 内核管理')
  await assertCardColumns(cdp, '内核版本卡片', 2)
  await setViewport(cdp, 640, 800)
  await assertNoHorizontalOverflow(cdp, '640px kernel manager', 'CloakBrowser 内核管理')
  await assertCardColumns(cdp, '内核版本卡片', 1)
  await setViewport(cdp, 1024, 800)
  await clickAria(cdp, '关闭内核管理')
  await waitFor(cdp, `![...document.querySelectorAll('[role=dialog]')].some(node => node.getClientRects().length && node.textContent?.includes('CloakBrowser 内核管理'))`, 'kernel manager close')
  await clickText(cdp, '基础信息')
  assert.equal(await valueOf(cdp, '#profile-name'), originalName)
  assert.equal(await valueOf(cdp, '#profile-description'), 'Created through the real Electron workspace')

  await clickText(cdp, '内核与代理')
  await setSelectValue(cdp, '#profile-browser-kernel', `public|${version}`)
  await clickText(cdp, '创建配置')
  await waitFor(cdp, `document.querySelector('[aria-label="浏览器配置列表"]')?.innerText.includes(${JSON.stringify(originalName)})`, 'created profile list')

  let saved = await profileList(sidecar)
  assert.equal(saved.total, 1)
  assert.equal(saved.items[0].name, originalName)
  assert.equal(saved.items[0].browserVersion, version)
  assert.equal(saved.items[0].timezone, 'Asia/Shanghai')
  const firstSeed = saved.items[0].fingerprintSeed

  // The local fixture is deliberately not executable browser code: verify the
  // real button/API path reports the startup failure on its own card.
  await activateAria(cdp, `打开 ${originalName} 的测试浏览器`)
  await waitFor(cdp, `document.querySelector('[aria-label="浏览器配置列表"] [role="alert"]')?.textContent.includes('测试浏览器启动失败')`, 'test browser startup failure', 30_000)
  assert.ok(await cdp.evaluate(`![...document.querySelectorAll('button')].find(button => button.getAttribute('aria-label') === ${JSON.stringify(`打开 ${originalName} 的测试浏览器`)})?.disabled`))

  await cdp.command('Page.reload', { ignoreCache: true })
  await waitFor(cdp, `document.querySelector('[aria-label="浏览器配置列表"]')?.innerText.includes(${JSON.stringify(originalName)})`, 'profile after full reload', 30_000)
  await setViewport(cdp, 1280, 900)
  await assertNoHorizontalOverflow(cdp, '1280px populated profile list')
  await setViewport(cdp, 1024, 800)
  await assertNoHorizontalOverflow(cdp, '1024px populated profile list')

  await activateAria(cdp, `编辑 ${originalName}`)
  await waitFor(cdp, `document.body?.innerText.includes('编辑浏览器配置')`, 'edit profile dialog')
  await setValue(cdp, '#profile-name', editedName)
  await setValue(cdp, '#profile-description', 'Updated through Electron')
  await clickText(cdp, '保存')
  await waitFor(cdp, `document.querySelector('[aria-label="浏览器配置列表"]')?.innerText.includes(${JSON.stringify(editedName)})`, 'updated profile list')
  saved = await profileList(sidecar)
  assert.equal(saved.items[0].name, editedName)
  assert.equal(saved.items[0].description, 'Updated through Electron')

  await activateAria(cdp, `重新生成 ${editedName} 的指纹`)
  await waitFor(cdp, `document.body?.innerText.includes('指纹已重新生成')`, 'fingerprint regeneration')
  saved = await waitForProfileList(sidecar, list => list.items[0]?.fingerprintSeed !== firstSeed)
  const regeneratedSeed = saved.items[0].fingerprintSeed

  await activateAria(cdp, `复制 ${editedName}`)
  await waitFor(cdp, `document.body?.innerText.includes('复制浏览器配置')`, 'duplicate profile dialog')
  await setValue(cdp, '#profile-copy-name', copyName)
  await clickText(cdp, '创建副本')
  await waitFor(cdp, `document.querySelector('[aria-label="浏览器配置列表"]')?.innerText.includes(${JSON.stringify(copyName)})`, 'duplicated profile list')
  saved = await waitForProfileList(sidecar, list => list.total === 2)
  const original = saved.items.find(profile => profile.name === editedName)
  const copied = saved.items.find(profile => profile.name === copyName)
  assert.equal(original?.fingerprintSeed, regeneratedSeed)
  assert.notEqual(copied?.fingerprintSeed, regeneratedSeed)
  await setViewport(cdp, 1280, 900)
  await assertCardColumns(cdp, '浏览器配置列表', 2)
  await assertNoHorizontalOverflow(cdp, '1280px profile cards')
  await setViewport(cdp, 1024, 800)
  await assertCardColumns(cdp, '浏览器配置列表', 2)
  await assertNoHorizontalOverflow(cdp, '1024px profile cards')
  await setViewport(cdp, 640, 800)
  await assertCardColumns(cdp, '浏览器配置列表', 1)
  await assertNoHorizontalOverflow(cdp, '640px profile cards')
  await setViewport(cdp, 1280, 900)

  await activateAria(cdp, `删除 ${copyName}`)
  await clickText(cdp, '确认删除')
  await waitFor(cdp, `!document.querySelector('[aria-label="浏览器配置列表"]')?.innerText.includes(${JSON.stringify(copyName)})`, 'copied profile deletion')
  await activateAria(cdp, `删除 ${editedName}`)
  await clickText(cdp, '确认删除')
  await waitFor(cdp, `document.body?.innerText.includes('还没有浏览器配置')`, 'empty profile list')
  assert.deepEqual(await profileList(sidecar), { items: [], total: 0 })

  await smokeCooperativeShutdown(desktop.child, sidecar.baseUrl, sidecar.token,
    () => cdp.evaluate('window.autoflow.quitApplication()'))

  console.log(`browser management desktop smoke passed (${desktop.packaged ? 'packaged' : 'development'}, ${process.platform}/${process.arch})`)
} finally {
  desktop?.cdp.close()
  await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}

async function evaluate(cdp, fn, ...args) {
  return cdp.evaluate(`(${fn})(${args.map(value => JSON.stringify(value)).join(',')})`)
}

async function clickText(cdp, text) {
  const point = await evaluate(cdp, value => {
    const element = [...document.querySelectorAll('button,[role="tab"]')].find(node => node.textContent?.trim() === value && node.getClientRects().length)
    if (!element) return null
    element.scrollIntoView({ block: 'center' })
    const rect = element.getBoundingClientRect()
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
  }, text)
  if (!point) throw new Error(`control not found: ${text}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 })
  await wait(100)
}

async function clickAria(cdp, label) {
  const point = await evaluate(cdp, value => {
    const element = [...document.querySelectorAll(`[aria-label="${CSS.escape(value)}"]`)].find(node => node.getClientRects().length)
    if (!element) return null
    element.scrollIntoView({ block: 'center' })
    const rect = element.getBoundingClientRect()
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
  }, label)
  if (!point) throw new Error(`aria control not found: ${label}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 })
  await wait(100)
}

async function activateAria(cdp, label) {
  const activated = await evaluate(cdp, value => {
    const element = [...document.querySelectorAll(`[aria-label="${CSS.escape(value)}"]`)].find(node => node.getClientRects().length)
    if (!(element instanceof HTMLButtonElement) || element.disabled) return false
    element.click()
    return true
  }, label)
  if (!activated) throw new Error(`enabled aria button not found: ${label}`)
}

async function setValue(cdp, selector, value) {
  const changed = await evaluate(cdp, (query, next) => {
    const element = document.querySelector(query)
    if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) return false
    const prototype = element instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype
    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, next)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    return true
  }, selector, value)
  if (!changed) throw new Error(`input not found: ${selector}`)
}

async function setSelectValue(cdp, selector, value) {
  const changed = await evaluate(cdp, (query, next) => {
    const element = document.querySelector(query)
    if (!(element instanceof HTMLSelectElement)) return false
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(element, next)
    element.dispatchEvent(new Event('change', { bubbles: true }))
    return element.value === next
  }, selector, value)
  if (!changed) throw new Error(`select option not found: ${selector}/${value}`)
}

async function valueOf(cdp, selector) {
  return evaluate(cdp, query => document.querySelector(query)?.value, selector)
}

async function setViewport(cdp, width, height) {
  await cdp.command('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
  await cdp.evaluate(`(async () => {
    await new Promise(resolve => requestAnimationFrame(resolve))
    await Promise.all(document.getAnimations()
      .filter(animation => animation instanceof CSSTransition)
      .map(animation => animation.finished.catch(() => undefined)))
  })()`)
}

async function assertNoHorizontalOverflow(cdp, description, dialogTitle) {
  const result = await evaluate(cdp, title => {
    const visible = element => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    const target = title
      ? [...document.querySelectorAll('[role="dialog"]')].find(element => visible(element) && element.textContent?.includes(title))
      : document.querySelector('main')
    if (!target) return { error: 'target missing' }
    const bounds = target.getBoundingClientRect()
    const outside = [...target.querySelectorAll('button,input,select,[role="tab"]')]
      .filter(visible)
      .map(element => ({ text: element.getAttribute('aria-label') ?? element.textContent?.trim() ?? element.tagName, rect: element.getBoundingClientRect() }))
      .filter(item => item.rect.left < -1 || item.rect.right > innerWidth + 1)
      .slice(0, 5)
      .map(item => ({ text: item.text, left: item.rect.left, right: item.rect.right }))
    return {
      viewport: innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      target: { left: bounds.left, right: bounds.right },
      outside,
    }
  }, dialogTitle)
  assert.equal(result.error, undefined, `${description}: ${result.error}`)
  assert.ok(result.documentWidth <= result.viewport + 1, `${description}: document width ${result.documentWidth} > ${result.viewport}`)
  assert.ok(result.target.left >= -1 && result.target.right <= result.viewport + 1, `${description}: target outside viewport ${JSON.stringify(result.target)}`)
  assert.deepEqual(result.outside, [], `${description}: controls outside viewport`)
}

async function assertCardColumns(cdp, label, count) {
  const result = await waitFor(cdp, `(() => {
    const grid = document.querySelector(${JSON.stringify(`[aria-label="${label}"]`)})
    if (!grid || grid.children.length < 2) return null
    const columns = getComputedStyle(grid).gridTemplateColumns.split(' ').length
    const [first, second] = [...grid.children].map(card => card.getBoundingClientRect())
    return { columns, sameRow: Math.abs(first.top - second.top) < 1 }
  })()`, `${label} ready`)
  assert.equal(result.columns, count, `${label} column count`)
  assert.equal(result.sameRow, count === 2, `${label} cards flow into expected rows`)
}

async function profileList(sidecar) {
  const response = await fetch(`${sidecar.baseUrl}/api/v1/profiles`, {
    headers: { 'x-autoflow-token': sidecar.token }, signal: AbortSignal.timeout(5000),
  })
  if (!response.ok) throw new Error(`profile API verification failed: ${response.status}`)
  return response.json()
}

async function waitForProfileList(sidecar, predicate, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs
  let list
  while (Date.now() < deadline) {
    list = await profileList(sidecar)
    if (predicate(list)) return list
    await wait(100)
  }
  throw new Error(`timed out waiting for profile API state: ${JSON.stringify(list)}`)
}
