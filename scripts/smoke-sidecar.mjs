import { spawn } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const suppliedBaseUrl = process.env.AUTOFLOW_BASE_URL
const suppliedToken = process.env.AUTOFLOW_INSTANCE_TOKEN
if ((suppliedBaseUrl && !suppliedToken) || (!suppliedBaseUrl && suppliedToken)) {
  throw new Error('sidecar readiness environment is missing')
}

function waitForReady(child, timeoutMs = 15_000) {
  return new Promise((resolveReady, reject) => {
    let buffer = ''
    const timer = setTimeout(() => reject(new Error('sidecar readiness timeout')), timeoutMs)
    const fail = error => { clearTimeout(timer); reject(error) }
    child.stdout.on('data', chunk => {
      buffer += chunk.toString()
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('AUTOFLOW_READY ')) continue
        try {
          const ready = JSON.parse(line.slice('AUTOFLOW_READY '.length))
          if (!Number.isInteger(ready.port) || ready.port < 1 || ready.port > 65535) throw new Error('invalid sidecar readiness')
          clearTimeout(timer)
          resolveReady(ready)
        } catch (error) { fail(error) }
      }
    })
    child.once('error', fail)
    child.once('exit', code => fail(new Error(`sidecar exited before readiness (${code ?? 'unknown'})`)))
  })
}

async function stop(child) {
  if (!child || child.exitCode !== null) return
  child.kill('SIGTERM')
  await new Promise(resolveDone => {
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolveDone() }, 3_000)
    child.once('exit', () => { clearTimeout(timer); resolveDone() })
  })
}

async function main() {
  if (suppliedBaseUrl) {
    await checkHealth(suppliedBaseUrl, suppliedToken)
    return
  }
  const dataDir = await mkdtemp(resolve(tmpdir(), 'autoflow-smoke-'))
  const token = `smoke-${process.pid}-${Date.now()}`
  const child = spawn('uv', ['run', '--directory', 'apps/backend', 'python', '-m', 'autoflow', '--instance-id', 'smoke-sidecar', '--data-dir', dataDir, '--port', '0'], {
    cwd: root,
    env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token },
    stdio: ['ignore', 'pipe', 'inherit'],
  })
  try {
    const ready = await waitForReady(child)
    await checkHealth(`http://127.0.0.1:${ready.port}`, token, ready)
  } finally {
    await stop(child)
    await rm(dataDir, { recursive: true, force: true })
  }
}

async function checkHealth(baseUrl, token, ready) {
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/health`, { headers: { 'x-autoflow-token': token } })
  if (!response.ok) throw new Error(`health check failed: ${response.status}`)
  const body = await response.json()
  if (body.status !== 'ok' || body.apiVersion !== 'v1' || (ready && body.instanceId !== ready.instanceId)) {
    throw new Error('unexpected health response')
  }
}

main().catch(error => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1 })
