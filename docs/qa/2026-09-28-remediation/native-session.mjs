// Interactive QA session: native UI actions are performed with the computer-use tool.
import { mkdtemp, realpath, stat, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { launchElectron, waitFor } from '../../../scripts/electron-cdp.mjs'
import { stop } from '../../../scripts/smoke-sidecar.mjs'
const root = resolve(import.meta.dirname, '../../..')
const workspaceArgument = process.argv[2]
if (!workspaceArgument) throw new Error('Usage: node native-session.mjs <existing dedicated QA workspace>')
const workspace = await realpath(workspaceArgument)
if (!(await stat(workspace)).isDirectory()) throw new Error('QA workspace must be an existing directory')
const output = await mkdtemp(join(import.meta.dirname, 'native-session-'))
const appPath = join(root, 'apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow')
const desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`], cliArgs: ['--executable', appPath] })
try {
  await waitFor(desktop.cdp, "document.body.innerText.includes('本地服务正常')", 'packaged service', 60_000)
  await writeFile(join(output, 'session.json'), JSON.stringify({ pid: desktop.child.pid, workspace, appPath, debugOrigin: desktop.debugOrigin, startedAt: new Date().toISOString() }, null, 2))
  console.log(`Packaged native QA session ready; evidence: ${output}`)
  await new Promise(resolveDone => { desktop.child.once('exit', resolveDone); process.once('SIGTERM', resolveDone); process.once('SIGINT', resolveDone) })
} finally { desktop.cdp.close(); await stop(desktop.child) }
