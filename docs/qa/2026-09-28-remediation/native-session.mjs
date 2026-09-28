// Interactive QA session: native UI actions are performed with the computer-use tool.
import { readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { launchElectron, waitFor } from '../../../scripts/electron-cdp.mjs'
import { stop } from '../../../scripts/smoke-sidecar.mjs'
const root = resolve(import.meta.dirname, '../../..')
const prior = JSON.parse(await readFile(join(import.meta.dirname, 'ui-current/result.json'), 'utf8'))
const appPath = join(root, 'apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow')
const desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${prior.workspace}`], cliArgs: ['--executable', appPath] })
try {
  await waitFor(desktop.cdp, "document.body.innerText.includes('本地服务正常')", 'packaged service', 60_000)
  await writeFile(join(import.meta.dirname, 'ui-current/native-session.json'), JSON.stringify({ pid: desktop.child.pid, workspace: prior.workspace, appPath, debugOrigin: desktop.debugOrigin, startedAt: new Date().toISOString() }, null, 2))
  console.log('Packaged native QA session ready')
  await new Promise(resolveDone => { desktop.child.once('exit', resolveDone); process.once('SIGTERM', resolveDone); process.once('SIGINT', resolveDone) })
} finally { desktop.cdp.close(); await stop(desktop.child) }
