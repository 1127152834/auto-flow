import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, mkdtemp, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const fixtureVersion = '146.0.7680.80'

export function smokeMode(args) {
  const index = args.indexOf('--executable')
  const executable = index === -1 ? undefined : args[index + 1]
  if (index !== -1 && (!executable || executable.startsWith('--'))) {
    throw new Error('--executable requires a path')
  }
  return { executable }
}

export function kernelExecutablePath(directory, platform = process.platform) {
  if (platform === 'darwin') return join(directory, 'Chromium.app', 'Contents', 'MacOS', 'Chromium')
  if (platform === 'win32') return join(directory, 'chrome.exe')
  throw new Error(`browser management smoke does not support ${platform}`)
}

async function createKernelFixture(rootDirectory) {
  const directory = join(rootDirectory, `chromium-${fixtureVersion}`)
  const executable = kernelExecutablePath(directory)
  await mkdir(resolve(executable, '..'), { recursive: true })
  await writeFile(executable, 'autoflow browser-management smoke fixture\n', { mode: 0o755 })
  return executable
}

function waitForReady(child, timeoutMs = 20_000) {
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
          if (!Number.isInteger(ready.port) || ready.port < 1 || ready.port > 65535) {
            throw new Error('invalid sidecar readiness')
          }
          clearTimeout(timer)
          resolveReady(ready)
        } catch (error) { fail(error) }
      }
    })
    child.once('error', fail)
    child.once('exit', code => fail(new Error(`sidecar exited before readiness (${code ?? 'unknown'})`)))
  })
}

async function smokeWorker(command, cacheDirectory) {
  const executable = await createKernelFixture(cacheDirectory)
  const child = spawn(command[0], [...command.slice(1), '--kernel-worker'], {
    cwd: root,
    env: { ...process.env, CLOAKBROWSER_BINARY_PATH: executable },
    stdio: ['pipe', 'pipe', 'pipe'],
  })
  const stdout = []
  const stderr = []
  child.stdout.on('data', chunk => stdout.push(chunk))
  child.stderr.on('data', chunk => stderr.push(chunk))
  child.stdin.end(`${JSON.stringify({
    command: 'download',
    cacheDir: cacheDirectory,
    edition: 'public',
    requestedVersion: fixtureVersion,
    releaseChannel: 'stable',
    licenseKey: null,
  })}\n`)
  const code = await new Promise((resolveExit, reject) => {
    const timer = setTimeout(() => {
      child.kill('SIGKILL')
      reject(new Error('kernel worker smoke timeout'))
    }, 20_000)
    child.once('error', error => { clearTimeout(timer); reject(error) })
    child.once('close', value => { clearTimeout(timer); resolveExit(value) })
  })
  if (code !== 0) throw new Error(`kernel worker smoke failed (${code}): ${Buffer.concat(stderr).toString().trim()}`)
  const messages = Buffer.concat(stdout).toString().trim().split(/\r?\n/).map(line => JSON.parse(line))
  const completed = messages.at(-1)
  assert.equal(completed?.type, 'completed')
  assert.equal(completed?.resolvedVersion, fixtureVersion)
  assert.equal(completed?.executableRelativePath, executable.slice(cacheDirectory.length + 1).split('\\').join('/'))
}

async function api(baseUrl, token, path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers: {
      'x-autoflow-token': token,
      ...(options.body ? { 'content-type': 'application/json' } : {}),
      ...options.headers,
    },
    signal: AbortSignal.timeout(20_000),
  })
  if (!response.ok) {
    throw new Error(`${options.method ?? 'GET'} ${path} failed: ${response.status} ${await response.text()}`)
  }
  return response.status === 204 ? undefined : response.json()
}

async function smokeBrowserManagement(baseUrl, token) {
  const environment = await api(baseUrl, token, '/api/v1/profiles/environment-options')
  assert.ok(environment.locales.some(option => option.value === 'ja-JP'))
  assert.ok(environment.timezones.some(option => option.value === 'Asia/Tokyo'))
  for (const options of [environment.locales, environment.timezones, environment.userAgentTemplates]) {
    assert.ok(options.length > 1)
    assert.equal(new Set(options.map(option => option.value)).size, options.length)
  }
  assert.ok(environment.userAgentTemplates.every(option => option.value.includes('Chrome/{major}.0.0.0')))
  const installed = await api(baseUrl, token, '/api/v1/kernels/installed')
  assert.equal(installed.items.length, 1)
  assert.equal(installed.items[0].edition, 'public')
  assert.equal(installed.items[0].version, fixtureVersion)

  const initialDefault = await api(baseUrl, token, '/api/v1/kernels/default')
  assert.deepEqual(initialDefault, { revision: 0, kernel: null })
  const kernel = { edition: 'public', version: fixtureVersion }
  const selectedDefault = await api(baseUrl, token, '/api/v1/kernels/default', {
    method: 'PUT', body: JSON.stringify({ expectedRevision: 0, kernel }),
  })
  assert.deepEqual(selectedDefault, { revision: 1, kernel })

  const profile = {
    name: 'Browser smoke profile',
    description: 'Temporary packaged-sidecar verification',
    startUrl: 'about:blank',
    locale: 'zh-CN',
    timezone: 'Asia/Shanghai',
    geoip: false,
    headless: true,
    humanize: true,
    humanPreset: 'careful',
    userAgent: null,
    viewportJson: { width: 1440, height: 900 },
    colorScheme: 'dark',
    extensionPathsJson: [],
    expertArgsJson: ['--lang=zh-CN'],
    browserVersion: fixtureVersion,
    browserEdition: 'public',
    releaseChannel: 'stable',
    proxyMode: 'none',
    proxyId: null,
    proxyPoolId: null,
  }
  const created = await api(baseUrl, token, '/api/v1/profiles', {
    method: 'POST', body: JSON.stringify(profile),
  })
  assert.equal(created.browserEdition, 'public')
  assert.equal(created.timezone, 'Asia/Shanghai')

  const duplicated = await api(baseUrl, token, `/api/v1/profiles/${created.id}/duplicate`, {
    method: 'POST', body: JSON.stringify({ name: 'Browser smoke copy' }),
  })
  assert.notEqual(duplicated.fingerprintSeed, created.fingerprintSeed)

  const updatedName = 'Browser smoke profile updated'
  await api(baseUrl, token, `/api/v1/profiles/${created.id}`, {
    method: 'PUT', body: JSON.stringify({ ...profile, name: updatedName }),
  })
  const reloadProfile = id => api(baseUrl, token, `/api/v1/profiles/${id}`)
  assert.equal((await reloadProfile(created.id)).name, updatedName)

  await api(baseUrl, token, `/api/v1/profiles/${duplicated.id}`, { method: 'DELETE' })
  await api(baseUrl, token, `/api/v1/profiles/${created.id}`, { method: 'DELETE' })
  assert.deepEqual(await api(baseUrl, token, '/api/v1/profiles'), { items: [], total: 0 })
  assert.deepEqual(await api(baseUrl, token, '/api/v1/kernels/default', {
    method: 'PUT', body: JSON.stringify({ expectedRevision: 1, kernel: null }),
  }), { revision: 2, kernel: null })
}

export async function smokeCooperativeShutdown(child, baseUrl, token, requestShutdown) {
  const stream = await fetch(`${baseUrl}/api/v1/kernels/events`, { headers: { 'x-autoflow-token': token } })
  assert.equal(stream.status, 200)
  const reader = stream.body.getReader()
  try {
    assert.match(new TextDecoder().decode((await reader.read()).value), /event: snapshot/)
    const exited = new Promise((resolveExit, reject) => {
      const timer = setTimeout(() => reject(new Error('cooperative shutdown exceeded 8s with SSE open')), 8000)
      child.once('exit', (code, signal) => {
        clearTimeout(timer)
        if (code === 0 && signal === null) resolveExit()
        else reject(new Error(`shutdown was not a clean exit: ${code}/${signal}`))
      })
    })
    await Promise.all([exited, requestShutdown()])
    const stillListening = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(1000) }).then(() => true, () => false)
    assert.equal(stillListening, false, 'sidecar must exit before its host completes shutdown')
  } finally {
    await reader.cancel().catch(() => undefined)
  }
}

async function main() {
  const { executable: suppliedExecutable } = smokeMode(process.argv.slice(2))
  const executable = suppliedExecutable ? resolve(root, suppliedExecutable) : undefined
  if (executable && !(await stat(executable).catch(() => undefined))?.isFile()) {
    throw new Error(`sidecar executable not found: ${executable}`)
  }
  const dataDirectory = await mkdtemp(join(tmpdir(), 'autoflow-browser-smoke-'))
  const token = `browser-smoke-${process.pid}-${Date.now()}`
  const hostToken = `browser-smoke-host-${process.pid}-${Date.now()}`
  const sourceCommand = ['uv', 'run', '--directory', 'apps/backend', 'python', '-m', 'autoflow']
  const command = executable ? [executable] : sourceCommand
  await createKernelFixture(join(dataDirectory, 'data', 'kernels'))

  let child
  try {
    await smokeWorker(command, join(dataDirectory, 'worker-cache'))
    const env = { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token, AUTOFLOW_HOST_TOKEN: hostToken, PYTHONTZPATH: '' }
    delete env.CLOAKBROWSER_BINARY_PATH
    delete env.CLOAKBROWSER_LICENSE_KEY
    child = spawn(command[0], [...command.slice(1), '--instance-id', 'smoke-browser-management', '--data-dir', dataDirectory, '--port', '0'], {
      cwd: root, env, stdio: ['ignore', 'pipe', 'inherit'],
    })
    const ready = await waitForReady(child)
    assert.equal(ready.instanceId, 'smoke-browser-management')
    const baseUrl = `http://127.0.0.1:${ready.port}`
    await smokeBrowserManagement(baseUrl, token)
    await smokeCooperativeShutdown(child, baseUrl, token, () => api(baseUrl, token, '/internal/lifecycle/shutdown', {
      method: 'POST', headers: { 'x-autoflow-host-token': hostToken },
    }))
    console.log(`browser management smoke passed (${executable ? 'packaged' : 'source'}, ${process.platform}/${process.arch})`)
  } finally {
    await stop(child)
    await rm(dataDirectory, { recursive: true, force: true })
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1 })
}
