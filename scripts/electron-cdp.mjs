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
  const rendererDeadline = Date.now() + 30_000
  while (Date.now() < rendererDeadline) {
    if (child.exitCode !== null || child.signalCode !== null) throw new Error('desktop exited before renderer creation')
    try {
      const targets = await (await fetch(`${origin}/json/list`, { signal: AbortSignal.timeout(Math.min(3000, Math.max(1, rendererDeadline - Date.now()))) })).json()
      page = targets.find(target => target.type === 'page')
    } catch (error) {
      if (!(error instanceof TypeError) && error.name !== 'TimeoutError') throw error
    }
    if (page) break
    await wait(100)
  }
  if (!page) throw new Error('desktop renderer not created')
  return { child, cdp: await connectCdp(page.webSocketDebuggerUrl), packaged, debugOrigin: origin, inspectorUrl: output.match(/Debugger listening on (ws:\/\/[^\s]+)/)?.[1] }
  } catch (error) {
    await stop(child)
    throw error
  }
}

export async function connectCdp(url) {
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
  let failure
  while (Date.now() < deadline) {
    // A page that is mid-navigation has no document body yet; that is a normal
    // transient, so it retries like any other unmet condition instead of
    // aborting the wait.
    try {
      value = await cdp.evaluate(expression)
      failure = undefined
    } catch (error) {
      failure = error
      value = undefined
    }
    if (value) return value
    await wait(100)
  }
  const detail = failure ? String(failure.message ?? failure) : JSON.stringify(value)
  throw new Error(`timed out waiting for ${description}: ${detail}`)
}

// The project page is identified structurally (its tab bar), never by copy that
// may change with the page content. Text anchors such as 项目资料 only render as
// a transient loading fallback and are not usable as a navigation signal.
export const PROJECT_PAGE_SELECTOR = '[aria-label="项目功能"]'

export async function waitForSelector(cdp, selector, description, timeoutMs = 15_000) {
  return waitFor(cdp, `Boolean(document.querySelector(${JSON.stringify(selector)}))`, description ?? `selector ${selector}`, timeoutMs)
}

export async function waitForProjectPage(cdp, timeoutMs = 30_000) {
  return waitForSelector(cdp, PROJECT_PAGE_SELECTOR, 'project page', timeoutMs)
}

export function wait(ms) { return new Promise(resolve => setTimeout(resolve, ms)) }
