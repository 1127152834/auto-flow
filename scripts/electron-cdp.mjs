import { spawn } from 'node:child_process'
import { stat } from 'node:fs/promises'
import { join } from 'node:path'
import { createRequire } from 'node:module'
import { stop } from './smoke-sidecar.mjs'

export async function launchElectron(root, { launchArgs = [], cliArgs = process.argv.slice(2) } = {}) {
  const executableIndex = cliArgs.indexOf('--executable')
  const packaged = executableIndex !== -1
  const executable = packaged ? cliArgs[executableIndex + 1] : createRequire(import.meta.url)('electron')
  if (!executable || !(await stat(executable)).isFile()) throw new Error('desktop executable not found')
  const extra = packaged ? [] : [join(root, 'apps/desktop')]
  const child = spawn(executable, [...extra, '--remote-debugging-port=0', ...launchArgs], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] })
  child.stdout.resume()
  try {
  let output = ''
  const debugUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`desktop debugger startup timeout: ${output}`)), 20_000)
    child.stderr.on('data', chunk => {
      output += chunk.toString()
      const match = output.match(/DevTools listening on (ws:\/\/[^\s]+)/)
      if (match) { clearTimeout(timer); resolve(match[1]) }
    })
    child.once('error', error => { clearTimeout(timer); reject(error) })
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`desktop exited early: ${code}`)) })
  })
  const origin = new URL(debugUrl).origin.replace('ws:', 'http:')
  let page
  for (let attempt = 0; attempt < 150; attempt++) {
    const targets = await (await fetch(`${origin}/json/list`, { signal: AbortSignal.timeout(3000) })).json()
    page = targets.find(target => target.type === 'page')
    if (page) break
    await wait(100)
  }
  if (!page) throw new Error('desktop renderer not created')
  return { child, cdp: await connectCdp(page.webSocketDebuggerUrl), packaged }
  } catch (error) {
    await stop(child)
    throw error
  }
}

async function connectCdp(url) {
  const socket = new WebSocket(url)
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('desktop debugger connection timeout')), 5000)
    socket.addEventListener('open', () => { clearTimeout(timer); resolve() }, { once: true })
    socket.addEventListener('error', () => { clearTimeout(timer); socket.close(); reject(new Error('desktop debugger connection failed')) }, { once: true })
  })
  let nextId = 0
  async function command(method, params = {}, timeoutMs = 10_000) {
    const id = ++nextId
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { socket.removeEventListener('message', receive); reject(new Error(`CDP ${method} timeout`)) }, timeoutMs)
      function receive(event) {
        const message = JSON.parse(event.data)
        if (message.id !== id) return
        clearTimeout(timer); socket.removeEventListener('message', receive)
        if (message.error) reject(new Error(`CDP ${method} failed: ${message.error.message}`))
        else resolve(message.result)
      }
      socket.addEventListener('message', receive)
      socket.send(JSON.stringify({ id, method, params }))
    })
  }
  async function evaluate(expression, timeoutMs) {
    const result = await command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, timeoutMs)
    if (result.exceptionDetails) throw new Error(`renderer evaluation failed: ${result.exceptionDetails.text}`)
    return result.result.value
  }
  return { socket, command, evaluate, close: () => socket.close() }
}

export async function waitFor(cdp, expression, description, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  let value
  while (Date.now() < deadline) {
    value = await cdp.evaluate(expression)
    if (value) return value
    await wait(100)
  }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(value)}`)
}

export function wait(ms) { return new Promise(resolve => setTimeout(resolve, ms)) }
