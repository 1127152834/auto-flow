// Read-only evidence capture; all interactive actions are performed through native CUA.
import { connectCdp } from '../../../scripts/electron-cdp.mjs'
import { readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
const dir = join(import.meta.dirname, 'ui-current')
const session = JSON.parse(await readFile(join(dir, 'native-session.json'), 'utf8'))
const targets = await (await fetch(`${session.debugOrigin}/json/list`)).json()
const prefix = process.argv[2]
if (!prefix || !/^[a-z0-9-]+$/.test(prefix)) throw new Error('unique evidence prefix required')
for (const target of targets.filter(t => /\/(index|studio)\.html/.test(t.url))) {
  const cdp = await connectCdp(target.webSocketDebuggerUrl)
  try {
    const label = target.url.includes('studio.html') ? 'studio' : 'main'
    const snapshot = await cdp.evaluate('({url:location.href,text:document.body.innerText})')
    await writeFile(join(dir, `${prefix}-${label}.json`), JSON.stringify(snapshot, null, 2), { flag: 'wx' })
    const { data } = await cdp.command('Page.captureScreenshot', { format: 'png' })
    await writeFile(join(dir, `${prefix}-${label}.png`), Buffer.from(data, 'base64'), { flag: 'wx' })
  } finally { cdp.close() }
}
