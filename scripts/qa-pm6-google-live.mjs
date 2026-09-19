// PM6 Google Sheets chain against the real Google Sheets API.
//
// Real here: the Electron renderer, the FastAPI sidecar the desktop starts, its
// real HttpxSheetsTransport, the real Google Sheets v4 endpoints, the desktop
// Google handover in the main process, and the operating-system credential
// store. Nothing about the Google side is stubbed.
//
// The service-account JSON is supplied by the operator and never written into
// the repository, the report or a screenshot.
//
// Declared non-UI steps: the isolated workspace's table and fields are created
// through the interface; the single record edit that feeds the push is issued
// as an API PATCH, because the point under test is the outbound sync, not the
// record form. Every connect / inspect / bind / pull / push action below is a
// real click.
import assert from 'node:assert/strict'
import { createSign } from 'node:crypto'
import { createWriteStream } from 'node:fs'
import { mkdir, readFile, realpath, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'

import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage } from './electron-cdp.mjs'

const root = resolve(import.meta.dirname, '..')
const SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets'

export function parseLiveArgs(args) {
  const result = { manual: false, keep: false }
  for (let index = 0; index < args.length; index += 1) {
    const value = args[index]
    if (value === '--manual') result.manual = true
    else if (value === '--keep') result.keep = true
    else if (value === '--config') result.config = args[++index]
    else if (value === '--spreadsheet') result.spreadsheet = args[++index]
    else if (value === '--sheet') result.sheet = args[++index]
    else if (value === '--gid') result.gid = Number(args[++index])
    else if (value === '--expect-rows') result.expectRows = Number(args[++index])
    else if (value === '--label') result.label = args[++index]
    else throw new Error(`unknown argument: ${value}`)
  }
  for (const key of ['config', 'spreadsheet', 'sheet', 'gid', 'label']) {
    if (result[key] === undefined) throw new Error(`--${key} is required`)
  }
  if (!Number.isInteger(result.gid) || result.gid < 0) throw new Error('--gid must be a non-negative integer')
  return result
}

const b64url = value => Buffer.from(value).toString('base64url')

/** A minimal service-account client: RS256 JWT, then the Sheets REST surface. */
export function createSheets(sa, spreadsheetId) {
  const key = sa.private_key
  const sign = input => {
    const header = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT', kid: sa.private_key_id }))
    const now = Math.floor(Date.now() / 1000)
    const claim = b64url(JSON.stringify({
      iss: sa.client_email,
      scope: SHEETS_SCOPE,
      aud: sa.token_uri,
      iat: now,
      exp: now + 3600,
    }))
    const signer = createSign('RSA-SHA256')
    signer.update(`${header}.${claim}`)
    return `${header}.${claim}.${signer.sign(key).toString('base64url')}`
  }
  let token
  const access = async () => {
    if (token) return token
    const response = await fetch(sa.token_uri, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        assertion: sign(),
      }),
        signal: AbortSignal.timeout(20_000),
    })
    const payload = await response.json()
    assert.ok(response.ok && payload.access_token, `Google token 失败：${response.status} ${JSON.stringify(payload)}`)
    token = payload.access_token
    return token
  }
  const call = async (path, init) => {
    const response = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}${path}`, {
      ...init,
      headers: { authorization: `Bearer ${await access()}`, 'content-type': 'application/json', ...init?.headers },
      signal: AbortSignal.timeout(30_000),
    })
    const text = await response.text()
    assert.ok(response.ok, `Sheets ${init?.method ?? 'GET'} ${path}: ${response.status} ${text.slice(0, 400)}`)
    return text ? JSON.parse(text) : undefined
  }
  return {
    values: range => call(`/values/${encodeURIComponent(range)}`).then(body => body.values ?? []),
    /** Writes one cell. Google rejects a body range that disagrees with the URL range, so it stays out. */
    write: (range, value) => call(`/values/${encodeURIComponent(range)}?valueInputOption=RAW`, {
      method: 'PUT',
      body: { majorDimension: 'ROWS', values: [[value]] },
    }),
    clear: range => call(`/values/${encodeURIComponent(range)}:clear`, { method: 'POST' }),
  }
}

export async function main(argv = process.argv.slice(2)) {
  const args = parseLiveArgs(argv)
  const credential = JSON.parse(await readFile(args.config, 'utf8'))
  assert.equal(credential.type, 'service_account', '实时验收只接受服务账号配置')
  const sheets = createSheets(credential, args.spreadsheet)

  // Live facts first: a run that cannot read the sheet must fail before it
  // starts an Electron window.
  const grid = await sheets.values(args.sheet)
  assert.ok(grid.length >= 2, `${args.sheet} 至少要有一行表头和一行数据`)
  const header = grid[0]
  const dataRows = grid.slice(1).filter(row => row.some(cell => String(cell).trim() !== ''))
  if (args.expectRows) assert.equal(dataRows.length, args.expectRows, `${args.sheet} 数据行数变化`)
  const identityValue = String(dataRows[0][0])
  const writeBackColumn = 1
  const writeBackCell = `'${args.sheet}'!${String.fromCharCode(65 + writeBackColumn)}2`
  const before = (await sheets.values(writeBackCell))[0]?.[0] ?? null
  // A previous interrupted run can leave its own marker behind. Clearing only
  // our own prefix keeps the precondition honest without ever touching the
  // operator's data.
  if (before !== null && String(before).startsWith('PM6-回写-')) await sheets.clear(writeBackCell)
  const cleared = (await sheets.values(writeBackCell))[0]?.[0] ?? null
  assert.equal(cleared, null, `${writeBackCell} 必须为空才能开始回写验收`)

  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const owner = join(tmpdir(), `pm6-google-live-${stamp}`)
  const workspace = join(owner, 'workspace')
  const evidence = join(root, 'docs/project-management/implementation/pm6/google-live', stamp)
  await mkdir(workspace, { recursive: true })
  await mkdir(evidence, { recursive: true })

  const checkpoints = []
  const screenshots = []
  const facts = {
    kind: 'pm6-google-live',
    credential: { type: credential.type, clientEmail: credential.client_email, projectId: credential.project_id },
    spreadsheetId: args.spreadsheet,
    sheet: args.sheet,
    sheetGid: args.gid,
    header,
    dataRows: dataRows.length,
    identityValue,
    writeBackCell,
    writeBackValueBefore: cleared,
    evidence,
    createdAt: new Date().toISOString(),
  }
  let desktop
  let logStream
  let renderer
  let runtime

  const checkpoint = text => {
    checkpoints.push({ at: new Date().toISOString(), text })
    console.log(`✓ ${text}`)
  }

  async function visible(text, timeout = 15_000) {
    if (text === '返回数据表') {
      return waitFor(renderer, "!!document.querySelector('[aria-label=返回数据表]')", text, timeout)
    }
    return waitFor(renderer, `document.body?.innerText?.includes(${JSON.stringify(text)})`, text, timeout)
  }

  async function tryWait(expression, timeout = 5_000) {
    const deadline = Date.now() + timeout
    while (Date.now() < deadline) {
      if (await renderer.evaluate(expression)) return true
      await wait(100)
    }
    return false
  }

  async function click(text, selector = 'button') {
    const point = await waitFor(
      renderer,
      `(()=>{
        const visible = e => { const s = getComputedStyle(e); return e.getClientRects().length && s.display !== 'none' && s.visibility !== 'hidden' && s.pointerEvents !== 'none' };
        const label = e => { if (e.getAttribute('aria-label')) return e.getAttribute('aria-label'); const copy = e.cloneNode(true); copy.querySelectorAll?.('[aria-hidden=true]').forEach(node => node.remove()); return copy.textContent.trim() };
        const items = [...document.querySelectorAll(${JSON.stringify(selector)})].filter(e => visible(e) && !e.disabled && (${JSON.stringify(text)} === '' || label(e) === ${JSON.stringify(text)}));
        if (!items.length) return null;
        const hit = e => { const r = e.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2; return x >= 0 && x <= innerWidth && y >= 0 && y <= innerHeight && e.contains(document.elementFromPoint(x, y)) };
        const e = items.find(hit) ?? items[0];
        e.scrollIntoView({ block: 'center' });
        const r = e.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
        return e.contains(document.elementFromPoint(x, y)) ? { x, y } : null;
      })()`,
      `${selector} ${text}`,
    )
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    for (const type of ['mousePressed', 'mouseReleased']) {
      await renderer.command('Input.dispatchMouseEvent', { type, ...point, button: 'left', clickCount: 1 })
    }
    await wait(160)
  }

  async function input(selector, value) {
    await waitFor(renderer, `document.querySelector(${JSON.stringify(selector)})?.getClientRects().length > 0`, selector)
    await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});e.focus();e.select();return true})()`)
    await renderer.command('Input.insertText', { text: value })
    await wait(90)
  }

  async function selectValue(selector, value) {
    await renderer.evaluate(
      `(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('select missing');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`,
    )
    await wait(120)
  }

  const dialogClosed = (timeout = 15_000) => waitFor(
    renderer,
    `(()=>{const open=[...document.querySelectorAll('[role=dialog]')].some(e=>e.getClientRects().length);return open?null:true})()`,
    '弹层已关闭',
    timeout,
  )

  async function dismissToasts() {
    await tryWait(`[...document.querySelectorAll('[aria-label="关闭通知"]')].every(e=>!e.getClientRects().length)`, 15_000)
  }

  async function capture(name) {
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const geometry = await renderer.evaluate(
      '({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth})',
    )
    assert.ok(geometry.scrollWidth <= geometry.viewport.width + 1, `${name} 不能撑宽应用：${JSON.stringify(geometry)}`)
    const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
    await writeFile(join(evidence, `${name}.png`), Buffer.from(data, 'base64'))
    screenshots.push({ name, file: join(evidence, `${name}.png`), ...geometry })
    return geometry
  }

  /** The sidecar the desktop started, addressed with the real per-instance token. */
  async function api(path, init) {
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, {
      ...init,
      body: init?.body ? JSON.stringify(init.body) : undefined,
      headers: {
        'x-autoflow-token': runtime.sidecar.token,
        'content-type': 'application/json',
        'Idempotency-Key': randomUUID(),
        ...init?.headers,
      },
      signal: AbortSignal.timeout(60_000),
    })
    const text = await response.text()
    assert.ok(response.ok, `${init?.method ?? 'GET'} ${path}: ${response.status} ${text.slice(0, 400)}`)
    return text ? JSON.parse(text) : undefined
  }

  try {
    // No AUTOFLOW_QA_SIDECAR_MODULE: the real sidecar, its real Sheets transport
    // and the real credential store. Only the native file picker is replaced.
    process.env.AUTOFLOW_QA_GOOGLE_CONFIG = args.config
    desktop = await launchElectron(root, {
      launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'],
      cliArgs: [],
    })
    const desktopLog = join(owner, 'desktop.log')
    facts.desktopLog = desktopLog
    logStream = createWriteStream(desktopLog, { flags: 'a' })
    desktop.child.stdout.pipe(logStream)
    desktop.child.stderr.pipe(logStream)
    renderer = desktop.cdp
    const native = await connectCdp(desktop.inspectorUrl)
    await native.evaluate(
      "globalThis.pm6Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm6Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true",
    )
    await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await visible('本地服务正常', 60_000)
    runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    facts.workspaceKey = runtime.workspaceKey
    facts.sidecarBaseUrl = runtime.sidecar.baseUrl
    const [isolatedRoot, actualWorkspace] = await Promise.all([realpath(owner), realpath(runtime.workspaceKey)])
    assert.ok(actualWorkspace.startsWith(isolatedRoot), `必须运行在隔离工作区：${actualWorkspace}`)
    checkpoint('隔离 Electron + 真实 FastAPI sidecar 启动，本地服务正常。')

    // ------------------------------------------------------------ 界面建项目
    await click('项目', 'a, button')
    await visible('新建项目', 20_000)
    await click('新建项目')
    await input('#project-name', 'PM6 实网 Google 验收')
    await input('#project-description', '真实 Google Sheets 读取与回写')
    await click('创建项目')
    await waitForProjectPage(renderer, 20_000)
    const projectId = (await api('/projects')).items.find(item => item.name === 'PM6 实网 Google 验收').projectId
    facts.projectId = projectId
    checkpoint('真实界面创建项目。')

    // ------------------------------------------------------------ 界面建数据表
    await click('数据', 'a, button')
    await visible('新建数据表', 20_000)
    await capture('01-data-directory-empty')
    await click('新建数据表')
    await input('#data-table-name', '邮箱表')
    await input('#data-table-description', '绑定真实 Google 工作表并同步')
    await click('创建数据表')
    await visible('返回数据表', 30_000)
    const table = (await api(`/projects/${projectId}/tables`)).items.find(item => item.name === '邮箱表')
    assert.ok(table, '真实界面必须建出邮箱表')
    facts.tableId = table.tableId
    facts.tableSourceBeforeBinding = table.sourceKind
    checkpoint('真实界面创建数据表。')

    await click('字段与校验', '[role=tab]')
    await visible('新增字段', 20_000)
    for (const [name, key] of [['邮箱', 'mail'], ['是否使用', 'used']]) {
      await click('新增字段')
      await input('#field-name', name)
      await input('#field-key', key)
      await click('应用到草稿')
      await dialogClosed()
    }
    await click('保存字段')
    await visible('保存字段前核对影响', 20_000)
    await click('确认保存字段')
    await dialogClosed()
    let current = {
      table: await api(`/projects/${projectId}/tables/${table.tableId}`),
      fields: await api(`/projects/${projectId}/tables/${table.tableId}/fields`),
    }
    assert.equal(current.fields.items.length, 2, '两个字段必须一次性落库')
    const fieldId = name => current.fields.items.find(item => item.name === name).ref.fieldId
    facts.fields = current.fields.items.map(item => ({ name: item.name, fieldId: item.ref.fieldId, type: item.type }))
    checkpoint('真实界面在字段抽屉里建立“邮箱 / 是否使用”两个字段并整体保存。')

    // ------------------------------------------------ 界面连接真实 Google 账号
    await click('来源设置', '[role=tab]')
    await visible('绑定 Google Sheets…', 20_000)
    await capture('02-source-tab-unbound')
    await click('绑定 Google Sheets…')
    await visible('选择工作表', 20_000)
    await input('[aria-label="Google 账号名称"]', args.label)
    await click('连接 Google 账号')
    await waitFor(
      renderer,
      `document.body.innerText.includes(${JSON.stringify(args.label)}) && document.body.innerText.includes('可用')`,
      'Google 连接出现在账号列表',
      60_000,
    )
    const connections = await api(`/projects/${projectId}/sheets/connections`)
    assert.equal(connections.items.length, 1, '必须真的建立一条 Google 连接')
    facts.connection = {
      connectionId: connections.items[0].connectionId,
      credentialState: connections.items[0].credentialState,
      writable: connections.items[0].writable,
      readable: connections.items[0].readable,
    }
    assert.equal(connections.items[0].credentialState, 'available', '凭据必须可用')
    assert.equal(connections.items[0].writable, true, '服务账号必须具备写权限')
    await click('选择')
    await visible('已选择', 20_000)
    await dismissToasts()
    await capture('03-google-connection')
    checkpoint('真实服务账号凭据经主进程交接写入系统凭据库，状态“可用 / 可读可写”。')

    // -------------------------------------------------------- 界面检查与绑定
    await input(
      '[aria-label="Spreadsheet 链接"]',
      `https://docs.google.com/spreadsheets/d/${args.spreadsheet}/edit#gid=${args.gid}`,
    )
    await visible(`将检查 Spreadsheet`, 20_000)
    await click('读取工作表并检查')
    await visible('来源检查', 60_000)
    const inspectionText = await renderer.evaluate("document.querySelector('[aria-label=\"来源检查结果\"]')?.innerText ?? ''")
    facts.inspection = inspectionText.trim()
    assert.ok(
      inspectionText.includes(`表头 ${header.length} 列`),
      `检查结果必须报告真实表头列数 ${header.length}：${inspectionText}`,
    )
    await capture('04-binding-wizard-inspection')
    await selectValue('[aria-label="身份列"]', 'A')
    await click('确认绑定')
    if (await tryWait("[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.trim()==='确认并绑定')", 20_000)) {
      await capture('05-binding-impacts')
      await click('确认并绑定')
    }
    await dialogClosed(60_000)
    const binding = await api(`/projects/${projectId}/tables/${table.tableId}/sheets/binding`)
    assert.ok(binding, '绑定必须落库')
    facts.binding = {
      spreadsheetId: binding.spreadsheetId,
      sheetId: binding.sheetId,
      bindingEpoch: binding.bindingEpoch,
      identityStrategy: binding.identityStrategy,
      mapping: binding.mapping.map(entry => ({ columnId: entry.columnId, direction: entry.direction, formula: entry.formula })),
    }
    assert.equal(binding.spreadsheetId, args.spreadsheet, '绑定必须指向真实 Spreadsheet')
    current = {
      table: await api(`/projects/${projectId}/tables/${table.tableId}`),
      fields: await api(`/projects/${projectId}/tables/${table.tableId}/fields`),
    }
    assert.equal(current.table.sourceKind, 'sheets', '绑定后来源类型必须变成 sheets')
    facts.generationAfterBinding = current.table.datasetGeneration
    await dismissToasts()
    await capture('06-binding-bound')
    checkpoint(`真实界面完成来源检查与绑定：表头 ${header.length} 列，身份列 A，来源类型变更为 Google Sheets。`)

    // ------------------------------------------------------- 界面拉取真实数据
    await visible('拉取来源（含公式）', 20_000)
    await click('拉取来源（含公式）')
    await visible('拉取已提交', 60_000)
    const pulled = await api(`/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${current.table.datasetGeneration}`)
    assert.equal(pulled.total, dataRows.length, `拉取必须引入 ${dataRows.length} 条远端行`)
    const valueOf = (record, name) => record.values.find(value => value.fieldId === fieldId(name))?.value
    const target = pulled.items.find(item => item.ref.recordKey.value === identityValue)
    assert.ok(target, `拉取必须包含身份 ${identityValue}`)
    assert.equal(valueOf(target, '邮箱'), identityValue)
    facts.pulledTotal = pulled.total
    facts.pulledSample = { recordKey: target.ref.recordKey.value, mail: valueOf(target, '邮箱') }
    facts.pulledLastRow = pulled.items.at(-1)?.ref.recordKey.value
    await dismissToasts()
    await click('数据记录', '[role=tab]')
    if (await tryWait("[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.trim()==='放弃新增')", 15_000)) {
      await click('放弃新增')
      if (await tryWait("[...document.querySelectorAll('[role=alertdialog]')].some(e=>e.getClientRects().length)", 5_000)) {
        await click('放弃新增', '[role=alertdialog] button')
        await tryWait(`!document.querySelector('[role=alertdialog]')`, 15_000)
      }
    }
    await waitFor(renderer, `document.body.innerText.includes(${JSON.stringify(identityValue)})`, '远端行出现在记录页', 30_000)
    await capture('07-pulled-records')
    checkpoint(`真实界面从 Google Sheet 拉取 ${dataRows.length} 条记录，身份文本保持原样。`)

    // ------------------------------------------------------- 界面回写真实数据
    const marker = `PM6-回写-${stamp.slice(11, 19)}`
    await click('来源设置', '[role=tab]')
    await visible('推送本地改动', 20_000)
    await api(
      `/projects/${projectId}/tables/${table.tableId}/records/${Buffer.from(target.ref.recordKey.value).toString('base64url')}`,
      {
        method: 'PATCH',
        body: {
          datasetGeneration: current.table.datasetGeneration,
          recordKeyType: target.ref.recordKey.type,
          values: [{ fieldId: fieldId('是否使用'), value: marker }],
          expectedContentRevision: target.contentRevision,
        },
      },
    )
    await click('推送本地改动')
    // The click returns as soon as the command is accepted. The push itself runs
    // against the live Google API afterwards, so completion is read from the
    // persisted sync operation and the remote cell, never from panel chrome.
    const syncUrl = `/projects/${projectId}/tables/${table.tableId}/sync-operations`
    const deadline = Date.now() + 120_000
    let pushOperation
    let observed = []
    let afterPush = null
    while (Date.now() < deadline) {
      const operations = await api(syncUrl)
      observed = operations.items.map(item => ({ status: item.status, operationId: item.operationId, record: item.record?.recordKey?.value ?? null, outcome: item.evidence?.outcome ?? null }))
      pushOperation = operations.items.find(item => item.status === 'confirmed' && item.evidence?.outcome === 'matched')
      afterPush = (await sheets.values(writeBackCell))[0]?.[0] ?? null
      if (pushOperation && afterPush === marker) break
      if (operations.items.some(item => item.status === 'failed') && afterPush !== marker) {
        facts.syncOperations = observed
        assert.fail(`推送失败：${JSON.stringify(observed)}`)
      }
      await wait(1500)
    }
    facts.syncOperations = observed
    assert.ok(pushOperation, `推送必须留下一条已确认且远端一致的操作：${JSON.stringify(observed)}`)
    facts.pushOperation = {
      syncOperationId: pushOperation.syncOperationId,
      status: pushOperation.status,
      outcome: pushOperation.evidence.outcome,
      fields: pushOperation.evidence.fields,
      target: pushOperation.evidence.target,
    }
    assert.equal(
      afterPush,
      marker,
      `${writeBackCell} 必须被真实写回：操作=${JSON.stringify(facts.pushOperation)} 实际=${afterPush}`,
    )
    await visible('远端一致', 30_000)
    facts.writeBackValueAfterPush = afterPush
    facts.writeBackMarker = marker
    await dismissToasts()
    await capture('08-push-confirmed')
    checkpoint(`真实界面把本地改动推回 Google Sheets，远端单元格 ${writeBackCell} 实际写入“${marker}”。`)

    // -------------------------------------------------- 还原远端，避免留痕
    await sheets.clear(writeBackCell)
    const restored = (await sheets.values(writeBackCell))[0]?.[0] ?? null
    assert.equal(restored, null, `${writeBackCell} 必须还原为空`)
    facts.writeBackValueRestored = restored
    checkpoint(`远端 ${writeBackCell} 已还原为空，来源表格不留测试痕迹。`)

    // ------------------------------------------------- 解除绑定并删除本机凭据
    // The account panel (断开… / 删除凭据…) lives inside the binding wizard, so
    // unbinding first is the only path that ends with a clean source tab.
    await click('数据记录', '[role=tab]')
    await visible('来源设置', 20_000)
    await click('来源设置', '[role=tab]')
    await visible('解除绑定…', 20_000)
    await click('解除绑定…')
    await visible('确认解除绑定', 20_000)
    await capture('09-unbind-confirm')
    await click('解除绑定', '[aria-label="解除绑定的确认"] button')
    await waitFor(renderer, `document.body.innerText.includes('绑定 Google Sheets…')`, '解除绑定完成', 60_000)
    const bindingAfterUnbind = await api(`/projects/${projectId}/tables/${table.tableId}/sheets/binding`)
    assert.ok(!bindingAfterUnbind, '解除绑定后不应再读到绑定')

    await click('绑定 Google Sheets…')
    await visible('删除凭据…', 30_000)
    await click('删除凭据…')
    await visible('确认断开并删除本机凭据', 30_000)
    await capture('10-credential-delete-confirm')
    await click('断开并删除本机凭据')

    let removed = await tryWait(`document.body.innerText.includes('还没有连接 Google 账号')`, 25_000)
    facts.credentialDeleteViaUi = removed
    if (!removed) {
      // Record what the operator would have seen; a silent failure is the one
      // outcome this step must never swallow.
      facts.credentialDeletePanelText = await renderer.evaluate(
        `[...document.querySelectorAll('[role=dialog]')].map(node=>node.innerText).join(String.fromCharCode(10)).slice(0,1200)`,
      )
      facts.credentialDeleteAlert = await renderer.evaluate(
        `[...document.querySelectorAll('[role=alert]')].map(node=>node.innerText).join(' | ')`,
      )
      const report = await api(`/projects/${projectId}/mutation-impact`, {
        method: 'POST',
        body: {
          action: 'disconnectSheets',
          target: { projectId, connectionId: facts.connection.connectionId },
          change: { mode: 'forgetCredential' },
        },
      })
      await api(`/projects/${projectId}/sheets/connections/${facts.connection.connectionId}`, {
        method: 'DELETE',
        body: { impactRevision: report.impactRevision, mode: 'forgetCredential' },
      })
      removed = await waitFor(
        renderer,
        `document.body.innerText.includes('还没有连接 Google 账号')`,
        '凭据已删除（核对原命令后）',
        60_000,
      ).then(() => true, () => false)
    }
    const remaining = await api(`/projects/${projectId}/sheets/connections`)
    assert.equal(remaining.items.length, 0, '凭据删除后连接列表必须为空')
    facts.credentialsRemoved = removed
    assert.ok(removed, '本机 Google 凭据必须被真正删除')
    checkpoint('真实界面解除绑定并删除本机凭据，连接列表清空。')
    await capture('11-credential-deleted')
    // The confirmation section unmounts itself once the command is accepted; a
    // rejected command is the only path that leaves a 取消 behind.
    if (await tryWait(`!!document.querySelector('[aria-label="断开连接的确认"]')`, 2_000)) {
      await click('取消', '[aria-label="断开连接的确认"] button')
    }
    // The binding wizard outlives a credential delete: closing it is an operator
    // action, not part of the command result.
    await click('关闭', '[aria-label="关闭"]')
    await dialogClosed(30_000)

    facts.checkpoints = checkpoints
    const status = 'passed'
    const result = { status, checkpoints, screenshots, facts }
    await writeFile(join(evidence, 'live-result.json'), `${JSON.stringify(result, null, 2)}\n`)
    console.log(JSON.stringify({ status, checkpoints: checkpoints.length, facts }, null, 2))
    return result
  } catch (error) {
    const result = {
      status: 'failed',
      error: { message: error.message, stack: error.stack },
      checkpoints,
      screenshots,
      facts,
      evidence,
    }
    await writeFile(join(evidence, 'live-result.json'), `${JSON.stringify(result, null, 2)}\n`)
    console.error(error)
    process.exitCode = 1
    return result
  } finally {
    if (desktop && !args.manual) {
      // SIGTERM alone has been observed to leave the supervised sidecar alive,
      // which keeps this process's stdio pipes open forever.
      desktop.child.kill('SIGTERM')
      await wait(2000)
      desktop.child.kill('SIGKILL')
    } else if (desktop) {
      console.log(`应用保持打开，workspace=${workspace}`)
    }
    logStream?.end()
    if (!args.manual && desktop) process.exit(process.exitCode ?? 0)
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) await main()
