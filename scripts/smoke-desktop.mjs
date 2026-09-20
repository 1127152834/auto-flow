import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'
import { launchElectron, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const dataDir = await mkdtemp(join(tmpdir(), 'autoflow-desktop-smoke-'))
let desktop
try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${dataDir}`] })
  const { packaged } = desktop
  const readiness = await waitFor(desktop.cdp, `(async () => {
    if (!window.autoflow) return null
    const status = await window.autoflow.getSidecarStatus()
    if (status.state !== 'ready') return null
    const response = await fetch(status.baseUrl + '/health', { headers: { 'x-autoflow-token': status.token }, signal: AbortSignal.timeout(3000) })
    const health = response.ok ? await response.json() : null
    return response.ok && health?.status === 'ok' && health?.instanceId === status.instanceId ? { status } : null
  })()`, 'authenticated sidecar health', 60_000)
  const status = readiness.status
  desktop.cdp.close()
  console.log(`desktop connected (${packaged ? 'packaged' : 'development'}, ${process.platform}/${process.arch})`)
  // Kill the desktop host to exercise backend parent-exit monitoring, not only normal quit.
  await stop(desktop.child)
  let backendExited = false
  for (let attempt = 0; attempt < 50; attempt++) {
    try { await fetch(`${status.baseUrl}/health`, { signal: AbortSignal.timeout(500) }) }
    catch { backendExited = true; break }
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  if (!backendExited) throw new Error('sidecar survived desktop termination')
  console.log('sidecar exited after desktop termination')
} finally {
  desktop?.cdp.close()
  await stop(desktop?.child)
  await rm(dataDir, { recursive: true, force: true, maxRetries: 20, retryDelay: 250 })
}
