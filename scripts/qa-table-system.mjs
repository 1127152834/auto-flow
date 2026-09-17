import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, writeFile, readFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import { createServer } from 'vite'
import { resolveConfig } from 'electron-vite'
import { launchElectron, connectCdp, waitFor, wait } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const parent = join(root, 'docs/ui/table-system/runs')
await mkdir(parent, { recursive: true })
const evidence = await mkdtemp(join(parent, 'components-'))
const workspace = await mkdtemp(join(tmpdir(), 'autoflow-table-qa-'))
await writeFile(join(workspace, '.table-qa.json'), JSON.stringify({ kind: 'autoflow-table-qa', evidence }))
const report = { kind: 'real-components-with-synthetic-props', status: 'running', sourceHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), screenshots: [], checks: [], workspace }
const sourceHash = createHash('sha256')
for (const file of (await readdir(join(root, 'apps/desktop/src/renderer'), { recursive: true })).filter(file => /\.(tsx?|css)$/.test(file)).sort()) sourceHash.update(file).update(await readFile(join(root, 'apps/desktop/src/renderer', file)))
report.sourceSha256 = sourceHash.digest('hex')
let server, desktop, native, page
async function key(key) {
  await page.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: ({ Enter: 13, Escape: 27, PageDown: 34, Tab: 9 })[key] })
  await page.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: ({ Enter: 13, Escape: 27, PageDown: 34, Tab: 9 })[key] })
}
async function click(text, selector = 'button') {
  const point = await waitFor(page, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(text)});if(!e)return null;e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, text)
  for (const type of ['mousePressed', 'mouseReleased']) await page.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
  await wait(150)
}
async function capture(name) {
  const geometry = await page.evaluate(`(()=>{
    const visible=e=>e.getClientRects().length;
    return {width:innerWidth,height:innerHeight,dpr:devicePixelRatio,documentWidth:document.documentElement.scrollWidth,font:getComputedStyle(document.body).fontFamily,
      tables:[...document.querySelectorAll('table')].filter(visible).map(t=>({classes:t.className,font:getComputedStyle(t).fontSize,header:[...t.querySelectorAll('thead th')].map(c=>({font:getComputedStyle(c).fontSize,height:c.getBoundingClientRect().height,line:getComputedStyle(c).borderRightWidth})),rows:[...t.querySelectorAll('tbody tr')].map(r=>r.getBoundingClientRect().height)})),
      tools:[...document.querySelectorAll('.af-table-toolbar .af-button,.af-table-toolbar [data-af-control]')].filter(visible).map(e=>({name:e.getAttribute('aria-label')||e.textContent.trim(),height:e.getBoundingClientRect().height,font:getComputedStyle(e).fontSize}))};
  })()`)
  assert.ok(geometry.documentWidth <= geometry.width + 1, name + ': no application-wide overflow')
  assert.ok(geometry.tables.length > 0, name + ': table present')
  for (const table of geometry.tables) { assert.equal(table.font, '14px'); for (const cell of table.header) { assert.equal(cell.font, '14px'); assert.ok(cell.height >= 31 && cell.height <= 33) } }
  for (const tool of geometry.tools) { assert.ok(tool.height >= 31 && tool.height <= 33, JSON.stringify(tool)); assert.equal(tool.font, '14px') }
  if (name.startsWith('basic')) for (const row of geometry.tables[0].rows) assert.ok(row >= 31 && row <= 33, 'plain rows are 32px')
  const { data } = await page.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(join(evidence, name + '.png'), data, 'base64')
  report.screenshots.push({ name, geometry, zoom: await native.evaluate('tableElectron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()') })
}
try {
  const { config } = await resolveConfig({ root: join(root, 'apps/desktop') }, 'serve', 'development')
  server = await createServer({ ...config.renderer, root: join(root, 'apps/desktop/src/renderer'), server: { host: '127.0.0.1', port: 0 } })
  await server.listen()
  const url = server.resolvedUrls.local[0] + 'development/table-system/index.html'
  process.env.ELECTRON_RENDERER_URL = url
  desktop = await launchElectron(root, { launchArgs: ['--user-data-dir=' + workspace, '--inspect=0'], cliArgs: [] })
  page = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.tableElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');tableElectron.BrowserWindow.getAllWindows()[0].setContentSize(1484,1060);true")
  // Boot directly into the dev-only component entry; avoid navigating a loading main renderer.
  await waitFor(page, "document.body?.innerText.includes('组件验收')&&!!document.querySelector('.af-table')", 'component page', 30000)
  for (const [scene, name] of [['基础', 'basic'], ['代理', 'proxy'], ['模型', 'models']]) {
    await click(scene)
    await capture(name + '-100')
    await native.evaluate('tableElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2);true'); await wait(200)
    await capture(name + '-200')
    await native.evaluate('tableElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1);true'); await wait(200)
  }
  const before = await page.evaluate('document.documentElement.scrollWidth')
  await page.evaluate("document.querySelector('[aria-label=模型状态]').focus()"); await key('Enter')
  await waitFor(page, "!!document.querySelector('[role=listbox]')", 'custom select popup')
  assert.equal(await page.evaluate('document.documentElement.scrollWidth'), before)
  await click('已停用', '[role=option]')
  assert.equal(await page.evaluate("document.querySelectorAll('.af-table tbody tr').length"), 1)
  await page.evaluate("document.querySelector('[aria-label=模型状态]').focus()"); await key('Enter'); await key('Escape')
  assert.equal(await page.evaluate("document.activeElement.getAttribute('aria-label')"), '模型状态')
  await capture('models-filtered')
  report.checks.push('three real component scenes at 100/200%: 14px header/body, 32px tools, internal overflow', 'Radix model filtering, unchanged application width, Escape focus restore')
  await click('Studio')
  await capture('studio-100')
  await page.evaluate("document.querySelector('.af-studio-grid-body').focus()")
  await key('PageDown')
  await waitFor(page, "document.querySelector('.af-studio-grid-body').scrollTop>100", 'keyboard scrolls real grid body')
  assert.ok(await page.evaluate("document.querySelectorAll('.af-studio-grid-row').length<100"), '10,000 rows stay virtualized')
  await page.evaluate("document.querySelector('.af-studio-grid-body').scrollLeft=800")
  await waitFor(page, "(()=>{const b=document.querySelector('.af-studio-grid-body');return b.scrollLeft>0&&document.querySelector('.af-studio-grid-header').style.transform==='translateX(-'+b.scrollLeft+'px)'})()", 'horizontal header sync')
  await capture('studio-scrolled')
  await page.evaluate("[...document.querySelectorAll('.af-studio-grid-header button')].at(-1).focus()")
  const alignment = await page.evaluate("(()=>{const h=document.querySelector('.af-studio-grid-header'),r=document.querySelector('.af-studio-grid-row'),b=document.querySelector('.af-studio-grid-body');return {headerX:h.getBoundingClientRect().x,rowX:r.getBoundingClientRect().x,headerClipScroll:h.parentElement.scrollLeft,bodyScroll:b.scrollLeft}})()")
  report.headerFocusAlignment = alignment
  assert.ok(Math.abs(alignment.headerX-alignment.rowX)<2, 'Focusing offscreen column header must keep body aligned: '+JSON.stringify(alignment))
  await native.evaluate('tableElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2);true'); await wait(200)
  await capture('studio-200')
  report.checks.push('Studio 10,000 rows / 12 columns: virtualized rows, PageDown, horizontal header and focus alignment; actual documentation and assistant tables')
  report.status = 'passed'
  console.log(JSON.stringify({ evidence, url, workspace }))
  if (process.argv.includes('--manual')) { await writeFile(join(evidence, 'report.json'), JSON.stringify(report, null, 2)); await new Promise(resolve => process.once('SIGINT', resolve)) }
} catch (error) {
  report.status = 'failed'; report.error = String(error)
  if (page) { const shot = await page.command('Page.captureScreenshot', { format: 'png' }).catch(() => null); if (shot) await writeFile(join(evidence, 'failure.png'), shot.data, 'base64') }
  throw error
} finally {
  await writeFile(join(evidence, 'report.json'), JSON.stringify(report, null, 2))
  page?.close(); native?.close(); if (desktop) await stop(desktop.child); await server?.close()
  console.log('Table evidence: ' + evidence)
}
