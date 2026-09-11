import { spawn } from 'node:child_process'
import { mkdtemp, rm, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const root = resolve(import.meta.dirname, '..')
export function smokeMode(args, env) {
  const index = args.indexOf('--executable')
  const executable = index === -1 ? undefined : args[index + 1]
  if (index !== -1 && (!executable || executable.startsWith('--'))) {
    throw new Error('--executable requires a path')
  }
  const baseUrl = env.AUTOFLOW_BASE_URL
  const token = env.AUTOFLOW_INSTANCE_TOKEN
  if (executable && (baseUrl || token)) {
    throw new Error('--executable cannot be combined with external readiness environment')
  }
  if (Boolean(baseUrl) !== Boolean(token)) throw new Error('sidecar readiness environment is missing')
  return { executable, baseUrl, token }
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

export async function stop(child, { graceMs = 3_000, killMs = 2_000 } = {}) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  await new Promise((resolveDone, reject) => {
    let forceTimer
    let deadlineTimer
    const finish = error => {
      clearTimeout(forceTimer)
      clearTimeout(deadlineTimer)
      child.off('exit', onExit)
      child.off('close', onExit)
      child.off('error', onError)
      if (error) reject(error)
      else resolveDone()
    }
    const onExit = () => finish()
    const onError = error => finish(error)
    child.once('exit', onExit)
    child.once('close', onExit)
    child.once('error', onError)
    forceTimer = setTimeout(() => child.kill('SIGKILL'), graceMs)
    deadlineTimer = setTimeout(() => {
      child.stdout?.destroy()
      child.stderr?.destroy()
      child.unref()
      finish(new Error('sidecar did not exit before cleanup deadline'))
    }, graceMs + killMs)
    child.kill('SIGTERM')
  })
}

async function main() {
  const { executable: suppliedExecutable, baseUrl: suppliedBaseUrl, token: suppliedToken } = smokeMode(process.argv.slice(2), process.env)
  if (suppliedBaseUrl) {
    await checkHealth(suppliedBaseUrl, suppliedToken)
    return
  }
  if (suppliedExecutable) {
    const executable = resolve(root, suppliedExecutable)
    const details = await stat(executable).catch(() => undefined)
    if (!details?.isFile()) throw new Error(`sidecar executable not found: ${executable}`)
    await smokeExecutable(executable)
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

async function smokeExecutable(executable) {
  const dataDir = await mkdtemp(resolve(tmpdir(), 'autoflow-smoke-'))
  const token = `smoke-${process.pid}-${Date.now()}`
  const child = spawn(executable, ['--instance-id', 'smoke-sidecar', '--data-dir', dataDir, '--port', '0'], {
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

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1 })
}
