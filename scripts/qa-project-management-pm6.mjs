// PM6 Google Sheets chain through real Electron clicks on an isolated workspace.
//
// Real here: the Electron renderer, the FastAPI sidecar the desktop starts, SQLite,
// operation envelopes, idempotency replay, transactions, the binding wizard, the
// sync panel, the desktop Google handover in the main process, and the desktop
// credential-store protocol.
//
// Stand-ins, both named in the report and both sitting exactly on a port the
// production code already declares (see apps/backend/tests/qa/pm6_sidecar.py):
//   * the Google Sheets REST surface, because this machine has no authorized
//     Google account;
//   * the operating-system credential store, so an automated run never writes a
//     Google secret into the developer's keychain.
//
// Not covered here: real Google OAuth/Spreadsheet access, the Studio demo,
// packaging, Windows and other architectures.
import assert from 'node:assert/strict'
import { generateKeyPairSync, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { createWriteStream } from 'node:fs'
import { mkdir, mkdtemp, readFile, realpath, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve, sep, isAbsolute, relative } from 'node:path'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const exec = promisify(execFile)
const root = resolve(import.meta.dirname, '..')

const SPREADSHEET_ID = 'pm6-source-1'
const SPREADSHEET_TITLE = 'PM6 来源表'
const SHEET_NAME = '记录'
const IDENTITY_KEY = '001'
const MAIL_VALUE = 'remote@example.com'
const CHECK_FORMULA = '=LOWER("A@B.COM")'

export const PM6_UI_STEPS = Object.freeze([
  '真实界面新建项目与本地数据表、字段、记录',
  '真实界面连接 Google 账号（服务账号配置经主进程交接，无浏览器弹窗）',
  '真实界面绑定向导：读取工作表并检查、身份列选择、确认绑定',
  '拉取来源把远端行引入新数据代次',
  '本地编辑并推送，核验证据显示远端一致，替身远端单元格真的被写入',
  '远端改动公式列后拉取，只刷新公式列',
  '提交后响应丢失进入结果未知，核对结果得到确定结论且不重复写入',
  '解除绑定确认后取消不生效、确认后生效',
])

export function parsePm6QaArgs(args) {
  const result = { manual: false, selfTest: false }
  for (const value of args) {
    if (value === '--manual') result.manual = true
    else if (value === '--self-test') result.selfTest = true
    else throw new Error(`unknown argument: ${value}`)
  }
  return result
}

export function isOwnedPm6Workspace(path, ownerPath, marker) {
  const offset = relative(resolve(ownerPath), resolve(path))
  return (
    marker?.kind === 'pm6-project-management-qa' &&
    marker?.version === 1 &&
    offset !== '..' &&
    !offset.startsWith(`..${sep}`) &&
    !isAbsolute(offset)
  )
}

/** The exact shape `parseGoogleConfig` accepts for a service account. */
export function serviceAccountFixture() {
  const { privateKey } = generateKeyPairSync('rsa', {
    modulusLength: 2048,
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    publicKeyEncoding: { type: 'spki', format: 'pem' },
  })
  return `${JSON.stringify(
    {
      type: 'service_account',
      project_id: 'autoflow-qa',
      client_email: 'autoflow-pm6-qa@example.iam.gserviceaccount.com',
      private_key: privateKey,
      token_uri: 'https://oauth2.googleapis.com/token',
    },
    null,
    2,
  )}\n`
}

async function desktopLogTail(path, lines = 50) {
  try {
    const text = await readFile(path, 'utf8')
    return text.split('\n').filter(Boolean).slice(-lines).join('\n')
  } catch {
    return ''
  }
}

export async function main(cliArgs = process.argv.slice(2)) {
  const options = parsePm6QaArgs(cliArgs)
  if (options.selfTest) {
    assert.equal(
      isOwnedPm6Workspace('/tmp/pm6-owner/workspace', '/tmp/pm6-owner', {
        kind: 'pm6-project-management-qa',
        version: 1,
      }),
      true,
    )
    assert.equal(
      isOwnedPm6Workspace('/tmp/pm6-owner-other/workspace', '/tmp/pm6-owner', {
        kind: 'pm6-project-management-qa',
        version: 1,
      }),
      false,
    )
    assert.equal(PM6_UI_STEPS.length, 8)
    const fixture = JSON.parse(serviceAccountFixture())
    assert.equal(fixture.type, 'service_account')
    assert.equal(fixture.token_uri, 'https://oauth2.googleapis.com/token')
    assert.ok(fixture.private_key.includes('BEGIN PRIVATE KEY'))
    assert.throws(() => parsePm6QaArgs(['--unknown']))
    console.log('PM6 QA helper self-test passed')
    return
  }

  const owner = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm6-ui-qa-')))
  const workspace = join(owner, 'workspace')
  const marker = {
    kind: 'pm6-project-management-qa',
    version: 1,
    createdAt: new Date().toISOString(),
  }
  await mkdir(workspace)
  await writeFile(join(owner, '.pm6-qa.json'), `${JSON.stringify(marker, null, 2)}\n`)
  await writeFile(
    join(workspace, '.autoflow-workspace.json'),
    JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }),
  )
  await writeFile(
    join(workspace, 'desktop-settings.json'),
    JSON.stringify({
      schemaVersion: 1,
      currentPath: workspace,
      previousPath: null,
      preferences: { zoom: 100, motion: 'system' },
    }),
  )
  // A throw-away service-account key. It is generated here, lives only in the
  // disposable QA directory, and authorizes nothing anywhere.
  const configPath = join(owner, 'qa-google-service-account.json')
  await writeFile(configPath, serviceAccountFixture(), { mode: 0o600 })

  const evidence = join(
    root,
    'docs/project-management/implementation/pm6/qa-runs/2026-09-18',
  )
  await mkdir(evidence, { recursive: true })
  const screenshots = []
  const checkpoints = []
  const facts = { standIns: {} }
  let desktop
  let renderer
  let native
  let desktopLogStream

  const checkpoint = (message) => {
    checkpoints.push(message)
    console.log(message)
  }

  const report = async (status, error) => {
    const { stdout: head } = await exec('git', ['rev-parse', 'HEAD'], { cwd: root })
    const { stdout: dirty } = await exec('git', ['status', '--short'], { cwd: root })
    const result = {
      status,
      scenario: 'PM6 Google Sheets 来源与同步闭环（管理侧）',
      scope:
        status === 'passed'
          ? '管理侧与本地契约已验证；真实 Google 端到端未执行'
          : 'PM6 管理侧验收未通过',
      evidenceType:
        '真实 Electron 渲染层点击 + 应用自启 FastAPI + SQLite + 受控 Sheets REST 替身',
      standIns: {
        sheetsRest: `tests/fixtures/sheets.FakeSheetsTransport（spreadsheetId=${SPREADSHEET_ID}）`,
        credentialStore: 'QA 侧车内的文件凭据库，替代系统钥匙串',
        googleConfigPicker:
          'AUTOFLOW_QA_GOOGLE_CONFIG 仅在未打包时生效，替代原生文件选择框',
      },
      notEvidence: [
        '真实 Google OAuth / 真实 Spreadsheet 读写',
        'Studio demo',
        'Windows、其他架构与打包应用',
        '用户手动执行结果',
      ],
      gitHead: head.trim(),
      dirtyFiles: dirty.trim().split('\n').filter(Boolean),
      platform: process.platform,
      arch: process.arch,
      owner,
      workspace,
      checkpoints,
      screenshots,
      facts,
      error,
      createdAt: new Date().toISOString(),
    }
    await writeFile(
      join(evidence, 'ui-result.json'),
      `${JSON.stringify(result, null, 2)}\n`,
    )
    console.log(JSON.stringify({ status, checkpoints, facts }, null, 2))
    return result
  }

  async function visible(text, timeout = 15_000) {
    // The breadcrumb goes back through an icon-only control, exactly like the
    // PM2 smoke walks it.
    if (text === '返回数据表') {
      return waitFor(
        renderer,
        "!!document.querySelector('[aria-label=返回数据表]')",
        text,
        timeout,
      )
    }
    return waitFor(
      renderer,
      `document.body?.innerText?.includes(${JSON.stringify(text)})`,
      text,
      timeout,
    )
  }

  /** Same polling as `visible`, but a missing element is an answer instead of a failure. */
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
      await renderer.command('Input.dispatchMouseEvent', {
        type,
        ...point,
        button: 'left',
        clickCount: 1,
      })
    }
    await wait(160)
  }

  async function doubleClick(selector) {
    const point = await waitFor(
      renderer,
      `(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||!e.getClientRects().length)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`,
      `double click: ${selector}`,
      7_000,
    )
    await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
    await renderer.command('Input.dispatchMouseEvent', {
      type: 'mousePressed',
      ...point,
      button: 'left',
      clickCount: 2,
    })
    await renderer.command('Input.dispatchMouseEvent', {
      type: 'mouseReleased',
      ...point,
      button: 'left',
      clickCount: 2,
    })
    await wait(140)
  }

  async function input(selector, value) {
    await waitFor(
      renderer,
      `document.querySelector(${JSON.stringify(selector)})?.getClientRects().length > 0`,
      selector,
    )
    await renderer.evaluate(
      `(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});e.focus();e.select();return true})()`,
    )
    await renderer.command('Input.insertText', { text: value })
    await wait(90)
  }

  async function selectValue(selector, value) {
    // A plain <select> is driven through its own change event so React sees it.
    await renderer.evaluate(
      `(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('select missing');e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`,
    )
    await wait(120)
  }

  async function dialogClosed(timeout = 15_000) {
    return waitFor(
      renderer,
      `(()=>{const open=[...document.querySelectorAll('[role=dialog]')].some(e=>e.getClientRects().length);return open?null:true})()`,
      '弹层已关闭',
      timeout,
    )
  }

  // Toasts clear themselves after 2600ms. Clicking their close button would be a
  // real pointerdown outside any open dialog, and a dialog reads that as "the
  // user dismissed me" -- which is how an earlier run lost the binding wizard.
  async function dismissToasts() {
    await tryWait(
      `[...document.querySelectorAll('[aria-label="关闭通知"]')].every(e=>!e.getClientRects().length)`,
      15_000,
    )
  }

  async function capture(name) {
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const geometry = await renderer.evaluate(
      '({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,scrollWidth:document.documentElement.scrollWidth})',
    )
    assert.ok(
      geometry.scrollWidth <= geometry.viewport.width + 1,
      `${name} 不能撑宽应用：${JSON.stringify(geometry)}`,
    )
    const { data } = await renderer.command('Page.captureScreenshot', { format: 'png' })
    await writeFile(join(evidence, `${name}.png`), Buffer.from(data, 'base64'))
    screenshots.push({ name, file: join(evidence, `${name}.png`), ...geometry })
    return geometry
  }

  async function api(path, init) {
    assert.ok(
      isOwnedPm6Workspace(runtime.workspaceKey, owner, marker),
      'QA 只能操作 marker 所有的隔离工作区',
    )
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/v1${path}`, {
      ...init,
      body: init?.body ? JSON.stringify(init.body) : undefined,
      headers: {
        'x-autoflow-token': runtime.sidecar.token,
        'content-type': 'application/json',
        'Idempotency-Key': randomUUID(),
        ...init?.headers,
      },
      signal: AbortSignal.timeout(30_000),
    })
    const text = await response.text()
    assert.ok(
      response.ok,
      `${init?.method ?? 'GET'} ${path}: ${response.status} ${text}`,
    )
    return text ? JSON.parse(text) : undefined
  }

  const remote = () => api(`/qa/pm6/sheets?sheet=${encodeURIComponent(SHEET_NAME)}`)

  async function tableFacts(projectId, tableId) {
    const table = await api(`/projects/${projectId}/tables/${tableId}`)
    const fields = await api(`/projects/${projectId}/tables/${tableId}/fields`)
    return { table, fields }
  }

  let runtime

  try {
    process.env.AUTOFLOW_QA_SIDECAR_MODULE = 'tests.qa.pm6_sidecar'
    process.env.AUTOFLOW_QA_GOOGLE_CONFIG = configPath
    facts.sidecarModule = process.env.AUTOFLOW_QA_SIDECAR_MODULE
    desktop = await launchElectron(root, {
      launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'],
      cliArgs: [],
    })
    const desktopLog = join(owner, 'desktop.log')
    facts.desktopLog = desktopLog
    desktopLogStream = createWriteStream(desktopLog, { flags: 'a' })
    desktop.child.stdout.pipe(desktopLogStream)
    desktop.child.stderr.pipe(desktopLogStream)
    renderer = desktop.cdp
    native = await connectCdp(desktop.inspectorUrl)
    await native.evaluate(
      "globalThis.pm6Electron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');pm6Electron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true",
    )
    await renderer.command('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1024,
      deviceScaleFactor: 1,
      mobile: false,
    })
    await visible('本地服务正常', 30_000)
    runtime = await renderer.evaluate('window.autoflow.getRuntimeContext()')
    assert.ok(
      isOwnedPm6Workspace(runtime.workspaceKey, owner, marker),
      'QA 只能操作 marker 所有的隔离工作区',
    )
    facts.workspaceKey = runtime.workspaceKey
    facts.debugPort = new URL(desktop.debugOrigin).port

    // ---------------------------------------------------------------- local data
    await click('项目', 'a, button')
    await visible('新建项目', 20_000)
    await click('新建项目')
    await input('#project-name', 'PM6 来源同步验证')
    await input('#project-description', '隔离的 Google Sheets 绑定与同步验收')
    await click('创建项目')
    await visible('项目资料', 20_000)
    const projectId = (await api('/projects')).items.find(
      (item) => item.name === 'PM6 来源同步验证',
    ).projectId
    facts.projectId = projectId
    checkpoint('真实界面创建项目。')

    await click('数据', 'a, button')
    await visible('新建数据表', 20_000)
    await click('新建数据表')
    await input('#data-table-name', '邮箱表')
    await input('#data-table-description', '绑定来源工作表并同步')
    await click('创建数据表')
    await visible('返回数据表', 30_000)
    const tables = await api(`/projects/${projectId}/tables`)
    const table = tables.items.find((item) => item.name === '邮箱表')
    assert.ok(table, '真实界面必须建出邮箱表')
    facts.tableId = table.tableId
    facts.tableSourceBeforeBinding = table.sourceKind

    await click('字段与校验', '[role=tab]')
    await visible('新增字段', 20_000)
    for (const [name, key] of [
      ['编号', 'code'],
      ['邮箱', 'mail'],
      ['校验', 'check'],
    ]) {
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
    let current = await tableFacts(projectId, table.tableId)
    assert.equal(current.fields.items.length, 3, '三个字段必须一次性落库')
    const fieldId = (name) =>
      current.fields.items.find((item) => item.name === name).ref.fieldId
    checkpoint('真实界面在字段抽屉里建立三个字段并整体保存。')

    await click('数据记录', '[role=tab]')
    await visible('本地记录', 20_000)
    await click('', '[data-record-action="create"]')
    await waitFor(renderer, "!!document.querySelector('[data-record-draft]')", '记录草稿')
    await doubleClick(
      `[data-record-draft] [data-grid-cell="0:${fieldId('编号')}"]`,
    )
    await input(
      `[data-record-draft] textarea[aria-label=${JSON.stringify('第 1 行 · 编号')}]`,
      IDENTITY_KEY,
    )
    await doubleClick(`[data-record-draft] [data-grid-cell="0:${fieldId('邮箱')}"]`)
    await input(
      `[data-record-draft] textarea[aria-label=${JSON.stringify('第 1 行 · 邮箱')}]`,
      'local@example.com',
    )
    await click('保存 1 行')
    await dialogClosed(30_000)
    await visible(IDENTITY_KEY, 20_000)
    const localRecords = await api(
      `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`,
    )
    assert.equal(localRecords.total, 1, '绑定前本地必须有一条真实记录')
    facts.localRecordBeforeBinding = localRecords.items[0].values.map(
      (value) => value.value,
    )
    checkpoint('真实界面录入本地记录（绑定前），本地数据代次已存在。')

    // -------------------------------------------- connection, inside the wizard
    // The account handshake is the wizard's first step, exactly like the
    // prototype's 编辑来源 dialog: the source tab never connects on its own.
    await click('来源设置', '[role=tab]')
    await visible('绑定 Google Sheets…', 20_000)
    await capture('01-source-tab-unbound')
    await click('绑定 Google Sheets…')
    await visible('选择工作表', 20_000)
    await input('[aria-label="Google 账号名称"]', 'QA 服务账号')
    await click('连接 Google 账号')
    await waitFor(
      renderer,
      `document.body.innerText.includes('QA 服务账号') && document.body.innerText.includes('可用')`,
      'Google 连接出现在账号列表',
      30_000,
    )
    const connections = await api(`/projects/${projectId}/sheets/connections`)
    assert.equal(connections.items.length, 1, '必须真的建立一条 Google 连接')
    facts.connection = {
      connectionId: connections.items[0].connectionId,
      credentialState: connections.items[0].credentialState,
      writable: connections.items[0].writable,
    }
    // A connection is not usable until the wizard selects it for this table.
    await click('选择')
    await visible('已选择', 20_000)
    await dismissToasts()
    await capture('02-google-connection')
    checkpoint('真实界面经桌面主进程交接建立 Google 连接，凭据状态可用且可写。')

    // --------------------------------------------------------------------- binding
    await input(
      '[aria-label="Spreadsheet 链接"]',
      `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit#gid=1000`,
    )
    await visible('将检查 Spreadsheet', 20_000)
    await click('读取工作表并检查')
    await visible('来源检查', 30_000)
    const inspectionText = await renderer.evaluate(
      "document.querySelector('[aria-label=\"来源检查结果\"]')?.innerText ?? ''",
    )
    facts.inspection = inspectionText.trim()
    assert.ok(inspectionText.includes('表头 3 列'), `检查结果必须报告真实表头列数：${inspectionText}`)
    await capture('03-binding-wizard-inspection')
    await selectValue('[aria-label="身份列"]', 'A')
    await click('确认绑定')
    // A binding that moves the table to a new data generation reports its
    // impacts first; confirming them is a second, separate act.
    if (
      await tryWait(
        "[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.trim()==='确认并绑定')",
        20_000,
      )
    ) {
      await capture('03b-binding-impacts')
      await click('确认并绑定')
    }
    await dialogClosed(30_000)
    // The source tab names the worksheet the way a person reads it: the
    // spreadsheet title and the worksheet name, not the internal grid id.
    await waitFor(
      renderer,
      `document.body.innerText.includes('${SPREADSHEET_TITLE}') && document.body.innerText.includes('来源工作表已建立映射')`,
      '绑定事实出现在来源页',
      30_000,
    )
    const binding = await api(
      `/projects/${projectId}/tables/${table.tableId}/sheets/binding`,
    )
    assert.ok(binding, '绑定必须落库')
    facts.binding = {
      spreadsheetId: binding.spreadsheetId,
      sheetId: binding.sheetId,
      bindingEpoch: binding.bindingEpoch,
      identityStrategy: binding.identityStrategy,
      mapping: binding.mapping.map((entry) => ({
        columnId: entry.columnId,
        direction: entry.direction,
        formula: entry.formula,
      })),
    }
    assert.equal(
      binding.bindingEpoch,
      1,
      '首次绑定必须从 epoch 1 开始',
    )
    assert.ok(
      binding.mapping.some((entry) => entry.columnId === 'C' && entry.formula === true),
      '远端公式列必须在绑定里标记为只读公式列',
    )
    current = await tableFacts(projectId, table.tableId)
    assert.notEqual(
      current.table.datasetGeneration,
      table.datasetGeneration,
      '绑定必须建立新的数据代次',
    )
    assert.equal(current.table.sourceKind, 'sheets')
    const afterBinding = await api(
      `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${current.table.datasetGeneration}`,
    )
    assert.equal(
      afterBinding.total,
      0,
      '新数据代次在拉取前必须是空的，本地旧记录不自动搬过去',
    )
    facts.generationAfterBinding = current.table.datasetGeneration
    // The source tab has to name the real spreadsheet and worksheet, not an
    // internal grid id and not "未记录" next to a live binding.
    const sourceFacts = await waitFor(
      renderer,
      `(()=>{const table=[...document.querySelectorAll('table')].find(node=>node.getAttribute('aria-label')==='来源事实');return table?table.innerText:null})()`,
      '来源事实',
      20_000,
    )
    assert.ok(sourceFacts.includes(SPREADSHEET_TITLE), `来源表格必须显示真实名称：${sourceFacts}`)
    assert.ok(sourceFacts.includes(SHEET_NAME), `工作表必须显示真实名称：${sourceFacts}`)
    assert.ok(!sourceFacts.includes('未记录'), `已绑定来源不得显示未记录：${sourceFacts}`)
    assert.ok(!sourceFacts.includes('gid'), `已绑定来源不得显示内部 gid：${sourceFacts}`)
    facts.sourceFacts = sourceFacts.split('\n').map(line => line.trim()).filter(Boolean)
    await dismissToasts()
    await capture('04-binding-bound')
    checkpoint('真实界面完成检查与绑定：新数据代次、身份列 A、公式列 C 只读，旧本地记录不继承。')

    // ------------------------------------------------------------------------ pull
    // 拉取/推送 stay in the source tab's 同步状态 panel, the same place the
    // prototype puts 拉取新增 and 推送变化.
    await visible('拉取来源（含公式）', 20_000)
    await click('拉取来源（含公式）')
    await visible('拉取已提交', 30_000)
    const pulled = await api(
      `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${current.table.datasetGeneration}`,
    )
    const pulledRecord = pulled.items.find((item) =>
      item.values.some((value) => value.value === IDENTITY_KEY),
    )
    assert.ok(pulledRecord, '拉取必须引入身份 001 的记录')
    const valueOf = (record, name) =>
      record.values.find((value) => value.fieldId === fieldId(name))?.value
    assert.equal(valueOf(pulledRecord, '邮箱'), MAIL_VALUE)
    assert.equal(
      valueOf(pulledRecord, '校验'),
      CHECK_FORMULA,
      '公式列必须保存公式本身，而不是显示值',
    )
    facts.pulledRecordKey = pulledRecord.ref.recordKey
    facts.pulledValues = {
      code: valueOf(pulledRecord, '编号'),
      mail: valueOf(pulledRecord, '邮箱'),
      check: valueOf(pulledRecord, '校验'),
    }
    await dismissToasts()
    await click('数据记录', '[role=tab]')
    // The binding moved the table to a new data generation. The grid session
    // opened before that move is deliberately held aside instead of being
    // written into the new data, so the operator has to discard it before the
    // new generation is listed. A stale draft is never silently adopted.
    if (
      await tryWait(
        "[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.trim()==='放弃新增')",
        15_000,
      )
    ) {
      await click('放弃新增')
      // A dirty draft asks for confirmation first; a stale one is discarded
      // straight away, because it can never be written into the new generation.
      if (
        await tryWait(
          "[...document.querySelectorAll('[role=alertdialog]')].some(e=>e.getClientRects().length)",
          5_000,
        )
      ) {
        await click('放弃新增', '[role=alertdialog] button')
        await tryWait(`!document.querySelector('[role=alertdialog]')`, 15_000)
      }
    }
    await waitFor(
      renderer,
      `document.body.innerText.includes(${JSON.stringify(MAIL_VALUE)})`,
      '远端行出现在记录页',
      30_000,
    )
    await capture('05-pulled-record')
    checkpoint('拉取把远端行引入新代次，文本身份 “001” 保持原样，公式列保存公式。')
    await click('来源设置', '[role=tab]')
    await visible('推送本地改动', 20_000)

    // ------------------------------------------------------------------------ push
    await api(
      `/projects/${projectId}/tables/${table.tableId}/records/${Buffer.from(
        pulledRecord.ref.recordKey.value,
      ).toString('base64url')}`,
      {
        method: 'PATCH',
        body: {
          datasetGeneration: current.table.datasetGeneration,
          recordKeyType: pulledRecord.ref.recordKey.type,
          values: [{ fieldId: fieldId('邮箱'), value: 'pushed@example.com' }],
          expectedContentRevision: pulledRecord.contentRevision,
        },
      },
    )
    facts.remoteWritesBeforePush = (await remote()).writes
    await click('推送本地改动')
    await waitFor(
      renderer,
      `document.body.innerText.includes('远端一致')`,
      '推送核验显示远端一致',
      30_000,
    )
    const grid = await remote()
    const header = grid.grid[0]
    const mailColumn = header.indexOf('邮箱')
    const rowIndex = grid.grid.findIndex(
      (row, index) => index > 0 && row[header.indexOf('编号')] === IDENTITY_KEY,
    )
    assert.ok(rowIndex > 0, '替身远端必须能找到身份行')
    assert.equal(
      grid.grid[rowIndex][mailColumn],
      'pushed@example.com',
      '推送必须真的写入替身远端单元格',
    )
    assert.ok(grid.writes > facts.remoteWritesBeforePush, '推送必须真的发出写请求')
    const syncOperations = await api(
      `/projects/${projectId}/tables/${table.tableId}/sync-operations`,
    )
    const confirmed = syncOperations.items.find(
      (item) => item.status === 'confirmed' && item.evidence?.outcome === 'matched',
    )
    assert.ok(confirmed, '必须有一条已确认且远端一致的同步操作')
    facts.pushOperation = {
      syncOperationId: confirmed.syncOperationId,
      status: confirmed.status,
      outcome: confirmed.evidence.outcome,
      fields: confirmed.evidence.fields,
    }
    facts.remoteMailAfterPush = grid.grid[rowIndex][mailColumn]
    await dismissToasts()
    await capture('06-push-confirmed')
    checkpoint('推送写入替身远端并被核验：同步操作已确认，远端证据为远端一致。')

    // -------------------------------------------------------------- formula refresh
    // A real formula cell has two render views of one fact: the formula that is
    // stored and what it computed to. The co-editor states both, so the pull is
    // compared against a remote state Google can actually produce.
    await api('/qa/pm6/sheets/cell', {
      method: 'POST',
      body: {
        sheet: SHEET_NAME,
        row: rowIndex,
        column: header.indexOf('校验'),
        formula: '=UPPER("a@b.com")',
        value: 'A@B.COM',
      },
    })
    await click('拉取来源（含公式）')
    await visible('拉取已提交', 30_000)
    const refreshed = await api(
      `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${current.table.datasetGeneration}`,
    )
    const refreshedRecord = refreshed.items.find(
      (item) => item.ref.recordKey.value === IDENTITY_KEY,
    )
    assert.equal(
      valueOf(refreshedRecord, '校验'),
      '=UPPER("a@b.com")',
      '公式列必须刷新成新的公式',
    )
    assert.equal(
      valueOf(refreshedRecord, '邮箱'),
      'pushed@example.com',
      '公式刷新不得改动同行的普通值',
    )
    facts.formulaRefresh = {
      check: valueOf(refreshedRecord, '校验'),
      mail: valueOf(refreshedRecord, '邮箱'),
    }
    await dismissToasts()
    await click('数据记录', '[role=tab]')
    await waitFor(
      renderer,
      `document.body.innerText.includes(${JSON.stringify('pushed@example.com')})`,
      '普通值保持不变',
      30_000,
    )
    await capture('07-formula-refreshed')
    checkpoint('远端改动公式列后拉取：只有公式列刷新，普通值保持原样。')
    await click('来源设置', '[role=tab]')
    await visible('推送本地改动', 20_000)

    // -------------------------------------------------------------- pause/resume
    // 暂停调度 must refuse new sends while keeping the local change as a fact.
    const beforePause = (
      await api(
        `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${current.table.datasetGeneration}`,
      )
    ).items.find(item => item.ref.recordKey.value === IDENTITY_KEY)
    await api(
      `/projects/${projectId}/tables/${table.tableId}/records/${Buffer.from(
        IDENTITY_KEY,
      ).toString('base64url')}`,
      {
        method: 'PATCH',
        body: {
          datasetGeneration: current.table.datasetGeneration,
          recordKeyType: beforePause.ref.recordKey.type,
          values: [{ fieldId: fieldId('邮箱'), value: 'paused@example.com' }],
          expectedContentRevision: beforePause.contentRevision,
        },
      },
    )
    const writesBeforePause = (await remote()).writes
    await click('暂停调度')
    await visible('恢复调度', 20_000)
    await click('推送本地改动')
    await waitFor(
      renderer,
      `document.body.innerText.includes('同步已暂停')`,
      '暂停期间推送被拒绝',
      30_000,
    )
    const pausedRemote = await remote()
    assert.equal(
      pausedRemote.writes,
      writesBeforePause,
      '暂停调度期间不得发出任何写入',
    )
    assert.notEqual(
      pausedRemote.grid[rowIndex][mailColumn],
      'paused@example.com',
      '暂停调度期间远端不得被改写',
    )
    await dismissToasts()
    await click('恢复调度')
    await visible('暂停调度', 20_000)
    await click('推送本地改动')
    await waitFor(
      renderer,
      `document.body.innerText.includes('远端一致')`,
      '恢复调度后推送核验',
      30_000,
    )
    assert.equal(
      (await remote()).grid[rowIndex][mailColumn],
      'paused@example.com',
      '恢复调度后待发送的本地改动必须写入远端',
    )
    await dismissToasts()
    await capture('07b-paused-and-resumed')
    checkpoint('暂停调度期间推送被拒绝且不改远端；恢复后同一条本地改动推送并核验。')

    // ------------------------------------------------------------- lost response
    const beforeLoss = (
      await api(
        `/projects/${projectId}/tables/${table.tableId}/records?datasetGeneration=${current.table.datasetGeneration}`,
      )
    ).items.find(item => item.ref.recordKey.value === IDENTITY_KEY)
    await api(
      `/projects/${projectId}/tables/${table.tableId}/records/${Buffer.from(
        IDENTITY_KEY,
      ).toString('base64url')}`,
      {
        method: 'PATCH',
        body: {
          datasetGeneration: current.table.datasetGeneration,
          recordKeyType: beforeLoss.ref.recordKey.type,
          values: [{ fieldId: fieldId('邮箱'), value: 'unknown@example.com' }],
          expectedContentRevision: beforeLoss.contentRevision,
        },
      },
    )
    const writesBeforeLoss = (await remote()).writes
    await api('/qa/pm6/sheets/lost-response', { method: 'POST', body: { enabled: true } })
    await click('推送本地改动')
    await waitFor(
      renderer,
      `document.body.innerText.includes('结果未知') || document.body.innerText.includes('推送未完成')`,
      '推送进入结果未知',
      30_000,
    )
    // The provider really wrote the cell before the response was lost, so the
    // reconcile must decide from the remote, not from a blind resend.
    const afterLoss = await remote()
    facts.lostResponse = {
      remoteMail: afterLoss.grid[rowIndex][mailColumn],
      writesDelta: afterLoss.writes - writesBeforeLoss,
    }
    assert.equal(
      afterLoss.grid[rowIndex][mailColumn],
      'unknown@example.com',
      '响应丢失前写入必须已经发生',
    )
    await dismissToasts()
    // The prototype's `100-sheets-directions` unknown card is a distinct state; capture it
    // before the confirm step resolves it.
    await capture('08a-push-result-unknown')
    await click('核对结果')
    await waitFor(
      renderer,
      `document.body.innerText.includes('已确认')`,
      '核对结果得到确定结论',
      30_000,
    )
    const afterReconcile = await remote()
    assert.equal(
      afterReconcile.writes,
      afterLoss.writes,
      '核对结果必须只读远端，不得重发写入',
    )
    const reconcileOperations = await api(
      `/projects/${projectId}/tables/${table.tableId}/sync-operations?status=confirmed`,
    )
    facts.reconcile = {
      confirmedCount: reconcileOperations.total,
      writesUnchanged: afterReconcile.writes,
    }
    await dismissToasts()
    await capture('08-lost-response-reconciled')
    checkpoint('提交后响应丢失进入结果未知；核对结果依据远端证据判定已确认，且没有重复写入。')

    // ----------------------------------------------------------------- unbind
    await click('解除绑定…')
    await visible('确认解除绑定', 20_000)
    const unbindText = await renderer.evaluate(
      "document.querySelector('[aria-label=\"解除绑定的确认\"]')?.innerText ?? ''",
    )
    facts.unbindImpacts = unbindText.trim()
    await capture('09-unbind-confirm')
    await click('取消')
    await waitFor(
      renderer,
      `!document.querySelector('[aria-label="解除绑定的确认"]')`,
      '取消解除绑定',
      15_000,
    )
    assert.ok(
      await api(`/projects/${projectId}/tables/${table.tableId}/sheets/binding`),
      '取消解除绑定不得改动已保存的绑定',
    )
    checkpoint('解除绑定先给出影响确认；取消不改变已保存绑定。')

    await click('解除绑定…')
    await visible('确认解除绑定', 20_000)
    await click('解除绑定', '[aria-label="解除绑定的确认"] button')
    await waitFor(
      renderer,
      `document.body.innerText.includes('把这张表绑定到一张工作表')`,
      '解除绑定后回到未绑定状态',
      30_000,
    )
    const unboundTable = await api(`/projects/${projectId}/tables/${table.tableId}`)
    assert.equal(unboundTable.sourceKind, 'unconfigured')
    assert.equal(
      await api(`/projects/${projectId}/tables/${table.tableId}/sheets/binding`),
      null,
    )
    facts.afterUnbind = {
      sourceKind: unboundTable.sourceKind,
      binding: null,
    }
    await dismissToasts()
    await capture('10-unbound')
    checkpoint('解除绑定后表进入待配置，本地数据与证据保留，绑定记录为空。')

    // ------------------------------------------------------ existing entries kept
    await renderer.evaluate(`location.hash = '#/projects/${projectId}/data'`)
    await visible('邮箱表', 20_000)
    assert.ok(
      await tryWait("document.body.innerText.includes('从 Excel 导入')", 15_000),
      'PM2 的数据表入口（从 Excel 导入）必须仍在',
    )
    // The catalog is a list of tables; the record entries live one level down, so
    // the walk keeps going through the same control a person uses.
    await click('打开数据表：邮箱表')
    await visible('数据记录', 20_000)
    await click('数据记录', '[role=tab]')
    await visible('新增行', 20_000)
    const toolbarLabels = await renderer.evaluate(
      `(()=>{const text=document.body.innerText;return ['筛选','排序','显示列'].filter(label=>text.includes(label))})()`,
    )
    // Export and re-import moved into the record toolbar's overflow menu in R1,
    // so the check opens it instead of reading the page text.
    await click('更多操作')
    const menuText = await waitFor(
      renderer,
      `(()=>{const menu=document.querySelector('[role=menu]');return menu&&menu.getClientRects().length?menu.innerText:null})()`,
      '记录工具栏的更多操作',
      15_000,
    )
    for (const label of ['导出 Excel', '重新导入 Excel']) {
      assert.ok(menuText.includes(label), `PM2 的记录入口必须仍在：${label}`)
    }
    facts.existingEntries = [...toolbarLabels, ...menuText.split('\n').map(part => part.trim()).filter(Boolean)]
    await renderer.command('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'Escape',
      code: 'Escape',
      windowsVirtualKeyCode: 27,
    })
    await renderer.command('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'Escape',
      code: 'Escape',
      windowsVirtualKeyCode: 27,
    })
    await wait(200)
    await capture('11-records-entry-after-unbind')
    checkpoint('解除绑定没有移除 PM2 的记录入口。')

    return await report('passed', null)
  } catch (error) {
    try {
      await capture('99-failure')
    } catch {
      /* evidence capture is best effort */
    }
    const diagnosis = await desktopLogTail(join(owner, 'desktop.log'))
    if (diagnosis) {
      facts.desktopLogTail = diagnosis
      console.error(`桌面日志尾部（${join(owner, 'desktop.log')}）：\n${diagnosis}`)
    }
    const sidecarTail = await desktopLogTail(join(workspace, 'logs', 'sidecar.log'), 60)
    if (sidecarTail) {
      facts.sidecarLogTail = sidecarTail
      console.error(`本地服务日志尾部：\n${sidecarTail}`)
    }
    return await report('failed', `${error?.stack ?? error}`)
  } finally {
    desktopLogStream?.end()
    if (!options.manual) {
      renderer?.close()
      native?.close()
      await stop(desktop?.child).catch(() => undefined)
    } else {
      console.log(
        `手动模式：应用保持运行，隔离工作区 ${workspace}，调试端口 ${facts.debugPort}`,
      )
    }
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(import.meta.filename)) {
  const result = await main()
  process.exitCode = !result || result.status === 'passed' ? 0 : 1
}
