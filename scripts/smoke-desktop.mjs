import { spawn } from 'node:child_process'
import { mkdtemp, rm, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'
import { createRequire } from 'node:module'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const executableIndex = process.argv.indexOf('--executable')
const packaged = executableIndex !== -1
const executable = packaged ? process.argv[executableIndex + 1] : createRequire(import.meta.url)('electron')
if (!executable || !(await stat(executable)).isFile()) throw new Error('desktop executable not found')
const dataDir = await mkdtemp(join(tmpdir(), 'autoflow-desktop-smoke-'))
const child = spawn(executable, [
  ...(!packaged ? [join(root, 'apps/desktop')] : []),
  '--remote-debugging-port=0', `--user-data-dir=${dataDir}`,
], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] })
let socket
try {
  const debugUrl = await new Promise((resolveUrl, reject) => {
    const timer = setTimeout(() => reject(new Error('desktop debugger startup timeout')), 15_000)
    let output = ''
    child.stderr.on('data', chunk => {
      output += chunk.toString()
      const match = output.match(/DevTools listening on (ws:\/\/[^\s]+)/)
      if (match) { clearTimeout(timer); resolveUrl(match[1]) }
    })
    child.once('error', error => { clearTimeout(timer); reject(error) })
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`desktop exited early: ${code}`)) })
  })
  const origin = new URL(debugUrl).origin.replace('ws:', 'http:')
  let page
  for (let attempt = 0; attempt < 100; attempt++) {
    const pages = await (await fetch(`${origin}/json/list`, { signal: AbortSignal.timeout(3000) })).json()
    page = pages.find(target => target.type === 'page')
    if (page) break
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  if (!page) throw new Error('desktop renderer not created')
  socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolveOpen, reject) => {
    const timer = setTimeout(() => reject(new Error('desktop debugger connection timeout')), 5000)
    socket.addEventListener('open', () => { clearTimeout(timer); resolveOpen() }, { once: true })
    socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('debugger connection failed')) }, { once: true })
  })
  let id = 0
  async function evaluate(expression) {
    const requestId = ++id
    return new Promise((resolveResult, reject) => {
      const timer = setTimeout(() => { socket.removeEventListener('message', receive); reject(new Error('renderer evaluation timeout')) }, 5000)
      function receive(event) {
        const message = JSON.parse(event.data)
        if (message.id !== requestId) return
        clearTimeout(timer)
        socket.removeEventListener('message', receive)
        if (message.error || message.result.exceptionDetails) reject(new Error('renderer evaluation failed'))
        else resolveResult(message.result.result.value)
      }
      socket.addEventListener('message', receive)
      socket.send(JSON.stringify({ id: requestId, method: 'Runtime.evaluate', params: { expression, awaitPromise: true, returnByValue: true } }))
    })
  }
  let body = ''
  for (let attempt = 0; attempt < 100; attempt++) {
    body = await evaluate('document.body?.innerText ?? ""')
    if (body.includes('服务已连接')) break
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  if (!body.includes('服务已连接')) throw new Error(`desktop did not connect: ${body}`)
  const status = await evaluate('window.autoflow.getSidecarStatus()')
  socket.close()
  console.log(`desktop connected (${packaged ? 'packaged' : 'development'}, ${process.platform}/${process.arch})`)
  // Kill the desktop host to exercise backend parent-exit monitoring, not only normal quit.
  await stop(child)
  let backendExited = false
  for (let attempt = 0; attempt < 50; attempt++) {
    try { await fetch(`${status.baseUrl}/health`, { signal: AbortSignal.timeout(500) }) }
    catch { backendExited = true; break }
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  if (!backendExited) throw new Error('sidecar survived desktop termination')
  console.log('sidecar exited after desktop termination')
} finally {
  socket?.close()
  await stop(child)
  await rm(dataDir, { recursive: true, force: true })
}
