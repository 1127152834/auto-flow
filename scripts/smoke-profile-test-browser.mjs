import assert from 'node:assert/strict'
import { execFile, spawn } from 'node:child_process'
import { constants } from 'node:fs'
import { cp, lstat, mkdir, mkdtemp, readdir, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { createConnection, createServer as createNetServer } from 'node:net'
import { homedir, tmpdir } from 'node:os'
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { promisify } from 'node:util'
import { pathToFileURL } from 'node:url'

import { kernelExecutablePath } from './smoke-browser-management.mjs'
import { stop } from './smoke-sidecar.mjs'

const run = promisify(execFile)
const root = resolve(import.meta.dirname, '..')
const reportPath = '/tmp/autoflow-profile-test-browser-smoke.md'
const kernelPattern = /^chromium-(\d+(?:\.\d+){3,4})$/

export function smokeOptions(args) {
  const values = {}
  const consumed = new Set()
  for (const [flag, key] of [['--kernel-directory', 'kernelDirectory'], ['--executable', 'executable']]) {
    const index = args.indexOf(flag)
    if (index === -1) continue
    const value = args[index + 1]
    if (!value || value.startsWith('--')) throw new Error(`${flag} requires a path`)
    values[key] = value
    consumed.add(index)
    consumed.add(index + 1)
  }
  const unknown = args.filter((value, position) => !consumed.has(position))
  if (unknown.length) throw new Error(`unknown argument: ${unknown[0]}`)
  return { kernelDirectory: values.kernelDirectory, executable: values.executable }
}

export async function inspectPublicKernel(directory, platform = process.platform) {
  const source = resolve(directory)
  const match = kernelPattern.exec(basename(source))
  if (!match) throw new Error('kernel directory must be named chromium-<four-or-five-part-version> (public edition)')
  const directoryInfo = await lstat(source).catch(() => undefined)
  if (!directoryInfo?.isDirectory() || directoryInfo.isSymbolicLink()) {
    throw new Error(`kernel directory is not a real directory: ${source}`)
  }
  const executable = kernelExecutablePath(source, platform)
  const executableInfo = await stat(executable).catch(() => undefined)
  if (!executableInfo?.isFile() || !(executableInfo.mode & 0o111)) {
    throw new Error(`kernel executable is missing or not executable: ${executable}`)
  }
  const resolvedExecutable = await realpath(executable)
  const resolvedSource = await realpath(source)
  if (!isWithin(resolvedExecutable, resolvedSource)) throw new Error('kernel executable resolves outside its installation directory')
  return { directory: resolvedSource, executable: resolvedExecutable, version: match[1] }
}

async function discoverPublicKernel() {
  const kernels = join(homedir(), 'Library', 'Application Support', '@autoflow', 'desktop', 'data', 'kernels')
  const entries = await readdir(kernels, { withFileTypes: true }).catch(() => [])
  const candidates = entries
    .filter(entry => entry.isDirectory() && kernelPattern.test(entry.name))
    .map(entry => join(kernels, entry.name))
    .sort((a, b) => versionKey(basename(b)).localeCompare(versionKey(basename(a)), undefined, { numeric: true }))
  for (const candidate of candidates) {
    try { return await inspectPublicKernel(candidate) } catch {}
  }
  return undefined
}

function versionKey(directoryName) {
  return directoryName.slice('chromium-'.length).split('.').map(part => part.padStart(10, '0')).join('.')
}

function isWithin(path, parent) {
  const offset = relative(parent, path)
  return offset !== '..' && !offset.startsWith(`..${sep}`) && !isAbsolute(offset)
}

async function verifyKernel(kernel) {
  if (process.platform !== 'darwin') throw new Error(`real profile test browser smoke supports macOS only, got ${process.platform}`)
  const [{ stdout: version }, { stdout: kind }] = await Promise.all([
    run(kernel.executable, ['--version'], { timeout: 10_000 }),
    run('file', [kernel.executable], { timeout: 10_000 }),
  ])
  assert.match(version, new RegExp(`^Chromium ${kernel.version.split('.')[0]}\\.`))
  if (process.arch === 'arm64') assert.match(kind, /arm64/)
  return { version: version.trim(), architecture: kind.trim().split(': ').at(-1) }
}

async function copyKernel(kernel, dataDirectory) {
  const destination = join(dataDirectory, 'data', 'kernels', basename(kernel.directory))
  assert.ok(isWithin(destination, dataDirectory))
  await cp(kernel.directory, destination, {
    recursive: true,
    dereference: false,
    verbatimSymlinks: true,
    mode: constants.COPYFILE_FICLONE,
  })
  await assertInternalSymlinks(destination)
  return inspectPublicKernel(destination)
}

async function assertInternalSymlinks(directory) {
  const pending = [directory]
  const rootPath = await realpath(directory)
  while (pending.length) {
    const current = pending.pop()
    for (const entry of await readdir(current, { withFileTypes: true })) {
      const path = join(current, entry.name)
      if (entry.isDirectory()) pending.push(path)
      if (entry.isSymbolicLink()) {
        const target = await realpath(path)
        if (!isWithin(target, rootPath)) throw new Error(`kernel contains an external symlink: ${path}`)
      }
    }
  }
}

function waitForReady(child, timeoutMs = 30_000) {
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

async function apiResponse(baseUrl, token, path, options = {}) {
  return fetch(`${baseUrl}${path}`, {
    ...options,
    headers: {
      'x-autoflow-token': token,
      ...(options.body ? { 'content-type': 'application/json' } : {}),
      ...options.headers,
    },
    signal: AbortSignal.timeout(100_000),
  })
}

async function api(baseUrl, token, path, options = {}) {
  const response = await apiResponse(baseUrl, token, path, options)
  const text = await response.text()
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} ${path} failed: ${response.status} ${text}`)
  return text ? JSON.parse(text) : undefined
}

async function fixtureServer() {
  const visits = []
  const reports = []
  let releaseFirst
  const firstReleased = new Promise(resolveReleased => { releaseFirst = resolveReleased })
  const server = createServer(async (request, response) => {
    if (request.url === '/') {
      const visitId = `visit-${visits.length + 1}`
      visits.push({ visitId, requestCookie: request.headers.cookie ?? '' })
      if (visits.length === 1) await Promise.race([firstReleased, new Promise(resolveWait => setTimeout(resolveWait, 2_000))])
      const html = `<!doctype html><meta charset="utf-8"><title>AutoFlow smoke</title><script>
        (async () => {
          const before = localStorage.getItem('autoflow-smoke');
          const canvas = document.createElement('canvas');
          canvas.width = 320; canvas.height = 80;
          const context = canvas.getContext('2d');
          context.fillStyle = '#d7c8b6'; context.fillRect(0, 0, 320, 80);
          context.fillStyle = '#3d3027'; context.font = '17px Arial';
          context.fillText('AutoFlow fingerprint 0123456789', 8, 32);
          context.beginPath(); context.arc(260, 42, 23, 0, Math.PI * 2); context.stroke();
          const bytes = new TextEncoder().encode(canvas.toDataURL());
          const canvasHash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
            .map(value => value.toString(16).padStart(2, '0')).join('');
          const webgl = document.createElement('canvas').getContext('webgl');
          const debug = webgl?.getExtension('WEBGL_debug_renderer_info');
          const surfaces = {
            userAgent: navigator.userAgent,
            language: navigator.language,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            platform: navigator.platform,
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory ?? null,
            screen: [screen.width, screen.height, screen.colorDepth],
            webglVendor: debug ? webgl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : null,
            webglRenderer: debug ? webgl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null,
          };
          await fetch('/report', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({
            visitId:${JSON.stringify(visitId)}, before, cookie:document.cookie, canvasHash, surfaces,
          })});
          localStorage.setItem('autoflow-smoke', ${JSON.stringify(visitId)});
        })();
      </script><p>${visitId}</p>`
      response.writeHead(200, {
        'content-type': 'text/html; charset=utf-8',
        'set-cookie': `autoflow-smoke-cookie=${visitId}; Path=/; SameSite=Strict`,
      })
      response.end(html)
      return
    }
    if (request.url === '/report' && request.method === 'POST') {
      let body = ''
      for await (const chunk of request) body += chunk
      reports.push(JSON.parse(body))
      response.writeHead(204).end()
      return
    }
    response.writeHead(204).end()
  })
  await new Promise((resolveListen, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolveListen)
  })
  const address = server.address()
  assert.ok(address && typeof address === 'object')
  return {
    url: `http://127.0.0.1:${address.port}/`, visits, reports,
    releaseFirst: () => releaseFirst(),
    close: () => new Promise((resolveClose, reject) => server.close(error => error ? reject(error) : resolveClose())),
  }
}

async function authenticatedSocksFixture() {
  const requests = []
  const socks = []
  const activeSockets = new Set()
  const target = createServer((request, response) => {
    requests.push({ host: request.headers.host, path: request.url })
    const body = '<!doctype html><title>proxied</title><p>authenticated SOCKS5</p>'
    response.writeHead(200, { 'content-type': 'text/html', 'content-length': Buffer.byteLength(body), connection: 'close' })
    response.end(body)
  })
  await listen(target)
  const targetAddress = target.address()
  assert.ok(targetAddress && typeof targetAddress === 'object')

  const server = createNetServer(connection => {
    activeSockets.add(connection)
    connection.on('close', () => activeSockets.delete(connection))
    handleSocksConnection(connection, targetAddress.port, socks).catch(() => connection.destroy())
  })
  await listen(server)
  const address = server.address()
  assert.ok(address && typeof address === 'object')
  return {
    port: address.port,
    targetPort: targetAddress.port,
    requests,
    socks,
    close: async () => {
      for (const connection of activeSockets) connection.destroy()
      await Promise.all([closeServer(server), closeServer(target)])
    },
  }
}

async function handleSocksConnection(connection, targetPort, observations) {
  const reader = socketReader(connection)
  assert.deepEqual(await reader.read(3), Buffer.from([5, 1, 2]))
  connection.write(Buffer.from([5, 2]))
  assert.equal((await reader.read(1))[0], 1)
  const username = await reader.read((await reader.read(1))[0])
  const password = await reader.read((await reader.read(1))[0])
  connection.write(Buffer.from([1, 0]))
  const request = await reader.read(4)
  assert.deepEqual(request.subarray(0, 3), Buffer.from([5, 1, 0]))
  const host = await readSocksHost(reader, request[3])
  const port = (await reader.read(2)).readUInt16BE()
  observations.push({ username: username.toString(), password: password.toString(), host, port })
  if (host !== 'fixture.test' || port !== targetPort) {
    connection.end(Buffer.from([5, 4, 0, 1, 0, 0, 0, 0, 0, 0]))
    return
  }
  const target = createConnection({ host: '127.0.0.1', port: targetPort })
  await new Promise((resolveConnect, reject) => {
    target.once('connect', resolveConnect)
    target.once('error', reject)
  })
  connection.write(Buffer.from([5, 0, 0, 1, 127, 0, 0, 1, 0, 0]))
  const buffered = reader.release()
  if (buffered.length) target.write(buffered)
  connection.pipe(target)
  target.pipe(connection)
  connection.resume()
}

async function readSocksHost(reader, type) {
  if (type === 1) return [...await reader.read(4)].join('.')
  if (type === 3) return (await reader.read((await reader.read(1))[0])).toString()
  if (type === 4) throw new Error('IPv6 was not expected in the fixture')
  throw new Error('invalid SOCKS address type')
}

function socketReader(socket) {
  let buffer = Buffer.alloc(0)
  let ended = false
  let wake
  const changed = () => { wake?.(); wake = undefined }
  const onData = chunk => { buffer = Buffer.concat([buffer, chunk]); changed() }
  const onEnd = () => { ended = true; changed() }
  socket.on('data', onData)
  socket.on('end', onEnd)
  socket.on('error', onEnd)
  return {
    async read(length) {
      while (buffer.length < length) {
        if (ended) throw new Error('SOCKS fixture connection ended')
        await new Promise(resolveWait => { wake = resolveWait })
      }
      const value = buffer.subarray(0, length)
      buffer = buffer.subarray(length)
      return value
    },
    release() {
      socket.pause()
      socket.off('data', onData)
      socket.off('end', onEnd)
      socket.off('error', onEnd)
      return buffer
    },
  }
}

function listen(server) {
  return new Promise((resolveListen, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolveListen)
  })
}

function closeServer(server) {
  return new Promise(resolveClose => server.close(() => resolveClose()))
}

function waitForWorkerReady(child, timeoutMs = 90_000) {
  return new Promise((resolveReady, reject) => {
    let buffer = ''
    const timer = setTimeout(() => reject(new Error('test browser worker readiness timeout')), timeoutMs)
    const fail = error => { clearTimeout(timer); reject(error) }
    child.stdout.on('data', chunk => {
      buffer += chunk.toString()
      const newline = buffer.indexOf('\n')
      if (newline === -1) return
      try {
        const message = JSON.parse(buffer.slice(0, newline))
        if (message.type !== 'ready') throw new Error(`worker did not become ready: ${JSON.stringify(message)}`)
        clearTimeout(timer)
        resolveReady(message)
      } catch (error) { fail(error) }
    })
    child.once('error', fail)
    child.once('exit', code => fail(new Error(`test browser worker exited before readiness (${code ?? 'unknown'})`)))
  })
}

function waitForCleanExit(child, timeoutMs = 20_000) {
  return new Promise((resolveExit, reject) => {
    if (child.exitCode !== null) return child.exitCode === 0 ? resolveExit() : reject(new Error(`worker exited ${child.exitCode}`))
    const timer = setTimeout(() => reject(new Error('test browser worker exit timeout')), timeoutMs)
    child.once('exit', (code, signal) => {
      clearTimeout(timer)
      if (code === 0 && signal === null) resolveExit()
      else reject(new Error(`worker exit was not clean: ${code}/${signal}`))
    })
  })
}

async function smokeAuthenticatedSocksWorker(command, copiedKernel, dataDirectory, report) {
  const fixture = await authenticatedSocksFixture()
  const cache = join(dataDirectory, 'tmp', 'direct-authenticated-socks')
  const username = 'autoflow-smoke-user'
  const password = 'autoflow-smoke-password'
  const seed = 71234
  let worker
  try {
    await mkdir(cache, { recursive: true })
    worker = spawn(command[0], [...command.slice(1), '--test-browser-worker'], {
      cwd: root,
      env: {
        ...process.env,
        CLOAKBROWSER_BINARY_PATH: copiedKernel.executable,
        CLOAKBROWSER_CACHE_DIR: cache,
        TMPDIR: cache,
        TMP: cache,
        TEMP: cache,
      },
      stdio: ['pipe', 'pipe', 'inherit'],
    })
    worker.stdin.write(`${JSON.stringify({
      sessionId: 'authenticated-socks-smoke', profileId: 'authenticated-socks-profile', fingerprintSeed: seed,
      startUrl: `http://fixture.test:${fixture.targetPort}/through-socks`, locale: 'zh-CN', timezone: 'Asia/Shanghai',
      geoip: false, humanize: false, humanPreset: 'default', userAgent: null,
      viewport: { width: 960, height: 640 }, colorScheme: 'dark', extensionPaths: [], expertArgs: [],
      browserVersion: copiedKernel.version, releaseChannel: 'stable', licenseKey: null,
      proxy: { server: `socks5://127.0.0.1:${fixture.port}`, username, password },
    })}\n`)
    const ready = await waitForWorkerReady(worker)
    assert.equal(ready.warning, null)
    await waitFor(() => fixture.requests.some(item => item.host === `fixture.test:${fixture.targetPort}` && item.path === '/through-socks'), 'fixture.test through authenticated SOCKS5')
    assert.ok(fixture.socks.some(item => item.username === username && item.password === password && item.host === 'fixture.test' && item.port === fixture.targetPort))
    const browser = await waitFor(async () => {
      const processes = await browserProcesses(copiedKernel.directory)
      return processes.find(item => !item.command.includes('--type=') && item.command.includes(`--fingerprint=${seed}`))
    }, 'proxied Chromium argv')
    assert.match(browser.command, /--proxy-server=http:\/\/127\.0\.0\.1:\d+/)
    for (const secret of [username, password, `socks5://127.0.0.1:${fixture.port}`]) assert.ok(!browser.command.includes(secret))
    worker.stdin.end()
    await waitForCleanExit(worker)
    await waitFor(async () => !(await browserProcesses(copiedKernel.directory)).some(item => item.command.includes(`--fingerprint=${seed}`)), 'proxied Chromium cleanup')
    assert.equal(await stat(cache).catch(() => undefined), undefined)
    report.push('- PASS：真实 Chromium 经无凭据 loopback relay、认证 SOCKS5 假上游到达 fixture.test；认证只在 SOCKS5 握手中出现。')
    report.push('- PASS：真实 Chromium argv 仅含 loopback HTTP proxy，不含 SOCKS5 上游地址、用户名或密码；stdin EOF 后进程与会话目录均回收。')
  } finally {
    worker?.stdin?.end()
    await stop(worker).catch(() => undefined)
    await fixture.close()
  }
}

async function browserProcesses(copiedKernelDirectory) {
  const { stdout } = await run('ps', ['axww', '-o', 'pid=,ppid=,pgid=,command='])
  return stdout.split(/\r?\n/).flatMap(line => {
    const match = /^\s*(\d+)\s+(\d+)\s+(\d+)\s+(.*)$/.exec(line)
    if (!match || !match[4].includes(copiedKernelDirectory)) return []
    return [{ pid: Number(match[1]), ppid: Number(match[2]), pgid: Number(match[3]), command: match[4] }]
  })
}

async function waitFor(check, message, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  let value
  while (Date.now() < deadline) {
    value = await check()
    if (value) return value
    await new Promise(resolveWait => setTimeout(resolveWait, 100))
  }
  throw new Error(`timed out waiting for ${message}`)
}

async function listFiles(directory) {
  const info = await stat(directory).catch(() => undefined)
  if (!info) return []
  const files = []
  const pending = [directory]
  while (pending.length) {
    const current = pending.pop()
    for (const entry of await readdir(current, { withFileTypes: true })) {
      const path = join(current, entry.name)
      if (entry.isDirectory()) pending.push(path)
      else files.push(path)
    }
  }
  return files
}

export async function findSessionDirectory(base, sessionId) {
  const roots = await readdir(base, { withFileTypes: true }).catch(error => {
    if (error.code === 'ENOENT') return []
    throw error
  })
  const matches = []
  for (const entry of roots) {
    if (!entry.isDirectory() || entry.isSymbolicLink()) continue
    const candidate = join(base, entry.name, sessionId)
    const info = await lstat(candidate).catch(error => {
      if (error.code === 'ENOENT') return undefined
      throw error
    })
    if (info?.isDirectory() && !info.isSymbolicLink()) matches.push(candidate)
  }
  if (matches.length > 1) throw new Error(`session directory is ambiguous: ${sessionId}`)
  return matches[0]
}

async function closeMacWindow(pid) {
  const script = `
    const se = Application('System Events');
    const matches = se.applicationProcesses.whose({unixId:${pid}})();
    if (matches.length !== 1 || matches[0].windows().length < 1) throw new Error('window unavailable');
    matches[0].windows()[0].buttons()[0].click();
  `
  await run('osascript', ['-l', 'JavaScript', '-e', script], { timeout: 10_000 })
}

async function smoke(kernel, kernelDetails, sidecarExecutable, report) {
  const dataDirectory = await mkdtemp(join(tmpdir(), 'autoflow-profile-test-browser-'))
  const token = `profile-test-browser-${process.pid}-${Date.now()}`
  const hostToken = `profile-test-browser-host-${process.pid}-${Date.now()}`
  const fixture = await fixtureServer()
  let sidecar
  try {
    const copiedKernel = await copyKernel(kernel, dataDirectory)
    report.push(`- 临时内核：${copiedKernel.directory}`)
    const command = sidecarExecutable
      ? [sidecarExecutable]
      : ['uv', 'run', '--directory', 'apps/backend', 'python', '-m', 'autoflow']
    await smokeAuthenticatedSocksWorker(command, copiedKernel, dataDirectory, report)
    sidecar = spawn(command[0], [...command.slice(1), '--instance-id', 'profile-test-browser-smoke', '--data-dir', dataDirectory, '--port', '0'], {
      cwd: root,
      env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token, AUTOFLOW_HOST_TOKEN: hostToken },
      stdio: ['ignore', 'pipe', 'inherit'],
    })
    const ready = await waitForReady(sidecar)
    const baseUrl = `http://127.0.0.1:${ready.port}`
    const profile = await api(baseUrl, token, '/api/v1/profiles', {
      method: 'POST',
      body: JSON.stringify({
        name: 'Profile test browser smoke', description: 'Isolated real-browser verification',
        startUrl: fixture.url, locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false,
        headless: true, humanize: false, humanPreset: 'default', userAgent: null,
        viewportJson: { width: 960, height: 640 }, colorScheme: 'dark', extensionPathsJson: [],
        expertArgsJson: ['--lang=zh-CN'], browserVersion: kernel.version, browserEdition: 'public',
        releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
      }),
    })
    assert.equal(profile.headless, true)
    assert.deepEqual(await listFiles(join(dataDirectory, 'workspace', 'profiles')), [])

    const starts = [
      apiResponse(baseUrl, token, `/api/v1/profiles/${profile.id}/test-browser`, { method: 'POST' }),
      apiResponse(baseUrl, token, `/api/v1/profiles/${profile.id}/test-browser`, { method: 'POST' }),
    ]
    await waitFor(() => fixture.visits.length === 1, 'first browser navigation')
    fixture.releaseFirst()
    const startResponses = await Promise.all(starts)
    const startedResponse = startResponses.find(response => response.status === 201)
    const busyResponse = startResponses.find(response => response.status === 409)
    assert.ok(startedResponse, `expected one 201, got ${startResponses.map(item => item.status).join('/')}`)
    assert.ok(busyResponse, `expected one 409, got ${startResponses.map(item => item.status).join('/')}`)
    assert.equal((await busyResponse.json()).error.code, 'PROFILE_TEST_BROWSER_BUSY')
    const firstSession = await startedResponse.json()
    assert.equal(firstSession.profileId, profile.id)
    assert.equal(firstSession.fingerprintSeed, profile.fingerprintSeed)
    assert.equal(firstSession.warning, null)

    const firstMain = await waitFor(async () => {
      const processes = await browserProcesses(copiedKernel.directory)
      return processes.find(item => item.command.includes(`--fingerprint=${profile.fingerprintSeed}`) && !item.command.includes('--type='))
    }, 'first Chromium seed in argv')
    assert.ok(!firstMain.command.includes('--headless'), 'test browser must override saved headless=true')
    assert.ok(!firstMain.command.includes('--proxy-server'), 'proxyMode=none must not add a proxy server')
    assert.equal((await api(baseUrl, token, `/api/v1/profiles/${profile.id}`)).headless, true)

    const sameSeedSession = await api(baseUrl, token, `/api/v1/profiles/${profile.id}/test-browser`, { method: 'POST' })
    assert.notEqual(sameSeedSession.sessionId, firstSession.sessionId)
    assert.equal(sameSeedSession.fingerprintSeed, profile.fingerprintSeed)
    assert.equal(sameSeedSession.warning, null)
    await waitFor(() => fixture.reports.length === 2, 'same-seed browser storage report')

    const regenerated = await api(baseUrl, token, `/api/v1/profiles/${profile.id}/regenerate-fingerprint`, { method: 'POST' })
    assert.notEqual(regenerated.fingerprintSeed, profile.fingerprintSeed)
    assert.equal((await api(baseUrl, token, `/api/v1/profiles/${profile.id}`)).fingerprintSeed, regenerated.fingerprintSeed)
    const resetSeedSession = await api(baseUrl, token, `/api/v1/profiles/${profile.id}/test-browser`, { method: 'POST' })
    assert.notEqual(resetSeedSession.sessionId, firstSession.sessionId)
    assert.notEqual(resetSeedSession.sessionId, sameSeedSession.sessionId)
    assert.equal(resetSeedSession.fingerprintSeed, regenerated.fingerprintSeed)
    assert.equal(resetSeedSession.warning, null)
    const processes = await waitFor(async () => {
      const current = await browserProcesses(copiedKernel.directory)
      const main = current.filter(item => !item.command.includes('--type='))
      return main.filter(item => item.command.includes(`--fingerprint=${profile.fingerprintSeed}`)).length >= 2
        && main.some(item => item.command.includes(`--fingerprint=${regenerated.fingerprintSeed}`)) ? current : undefined
    }, 'three independent Chromium windows')

    await waitFor(() => fixture.reports.length === 3, 'three browser storage reports')
    assert.deepEqual(fixture.visits.map(item => item.requestCookie), ['', '', ''])
    assert.deepEqual(fixture.reports.map(item => item.before), [null, null, null])
    for (const visit of fixture.reports) assert.match(visit.cookie, new RegExp(`autoflow-smoke-cookie=${visit.visitId}`))
    assert.deepEqual(await listFiles(join(dataDirectory, 'workspace', 'profiles')), [])

    const sessionBase = join(dataDirectory, 'tmp', 'test-browser')
    const sessionDirectories = await waitFor(async () => {
      const directories = await Promise.all([
        findSessionDirectory(sessionBase, firstSession.sessionId),
        findSessionDirectory(sessionBase, sameSeedSession.sessionId),
        findSessionDirectory(sessionBase, resetSeedSession.sessionId),
      ])
      return directories.every(Boolean) ? directories : undefined
    }, 'three live session directories')

    await closeMacWindow(firstMain.pid)
    await waitFor(async () => !(await stat(sessionDirectories[0]).catch(() => undefined)), 'closed-window session cleanup', 20_000)
    assert.ok(await stat(sessionDirectories[1]))
    assert.ok(await stat(sessionDirectories[2]))
    report.push('- PASS：首个窗口通过 macOS 辅助功能按 PID 关闭，其 worker 与会话临时目录已回收。')

    const trackedPids = processes.map(item => item.pid)
    await api(baseUrl, token, '/internal/lifecycle/shutdown', {
      method: 'POST', headers: { 'x-autoflow-host-token': hostToken },
    })
    await waitFor(() => sidecar.exitCode !== null || sidecar.signalCode !== null, 'sidecar shutdown', 15_000)
    await waitFor(async () => (await browserProcesses(copiedKernel.directory)).length === 0, 'browser process cleanup', 15_000)
    assert.equal(await stat(sessionBase).catch(() => undefined), undefined)
    for (const pid of trackedPids) assert.throws(() => process.kill(pid, 0))
    const [firstObservation, sameSeedObservation, resetSeedObservation] = fixture.reports
    report.push('- PASS：重置前后种子持久化，三个实际 Chromium argv 分别带对应 `--fingerprint`。')
    report.push('- PASS：同一配置三个并存窗口的首次 Cookie 与 localStorage 均为空。')
    report.push('- PASS：保存的 headless=true 未改变；测试窗口实际无 `--headless`；proxyMode=none 未添加代理参数。')
    report.push('- PASS：同配置启动中返回 409；启动成功后可再启动独立窗口。')
    report.push('- PASS：workspace/profiles 未产生文件；sidecar 退出后无测试浏览器进程和会话临时目录。')
    report.push(`- API 与 argv 验证的旧 seed：${profile.fingerprintSeed}；新 seed：${regenerated.fingerprintSeed}`)
    report.push(`- 观察到的测试浏览器进程数（含 helper）：${processes.length}`)
    report.push(`- 内核版本输出：${kernelDetails.version}`)
    report.push(`- 同 seed Canvas SHA-256 相同：${firstObservation.canvasHash === sameSeedObservation.canvasHash}`)
    report.push(`- 重置 seed 后 Canvas SHA-256 变化：${firstObservation.canvasHash !== resetSeedObservation.canvasHash}`)
    report.push(`- 同 seed WebGL 相同：${sameWebGl(firstObservation, sameSeedObservation)}`)
    report.push(`- 重置 seed 后 WebGL 变化：${!sameWebGl(firstObservation, resetSeedObservation)}`)
    report.push(`- 旧 seed 首次观测：${JSON.stringify({ canvasHash: firstObservation.canvasHash, ...firstObservation.surfaces })}`)
    report.push(`- 旧 seed 再次观测：${JSON.stringify({ canvasHash: sameSeedObservation.canvasHash, ...sameSeedObservation.surfaces })}`)
    report.push(`- 新 seed 观测：${JSON.stringify({ canvasHash: resetSeedObservation.canvasHash, ...resetSeedObservation.surfaces })}`)
  } finally {
    fixture.releaseFirst()
    await stop(sidecar).catch(() => undefined)
    await fixture.close().catch(() => undefined)
    await rm(dataDirectory, { recursive: true, force: true })
  }
}

function sameWebGl(left, right) {
  return left.surfaces.webglVendor === right.surfaces.webglVendor
    && left.surfaces.webglRenderer === right.surfaces.webglRenderer
}

async function main() {
  const startedAt = new Date()
  let appendReport = false
  const report = [
    '# AutoFlow 配置测试浏览器真实冒烟', '',
    `- 时间：${startedAt.toISOString()}`,
    `- 平台：${process.platform}/${process.arch}`,
  ]
  try {
    const { kernelDirectory, executable } = smokeOptions(process.argv.slice(2))
    appendReport = Boolean(executable)
    const sidecarExecutable = executable ? resolve(root, executable) : undefined
    if (sidecarExecutable && !(await stat(sidecarExecutable).catch(() => undefined))?.isFile()) {
      throw new Error(`sidecar executable not found: ${sidecarExecutable}`)
    }
    const kernel = kernelDirectory ? await inspectPublicKernel(kernelDirectory) : await discoverPublicKernel()
    if (!kernel) {
      report.push('- 状态：SKIPPED')
      report.push('- 原因：未发现已安装的 public CloakBrowser 内核。请用 `--kernel-directory /path/to/chromium-<version>` 重跑。')
      await writeSmokeReport(report, appendReport)
      console.log(`SKIP: no installed public CloakBrowser kernel; pass --kernel-directory (report: ${reportPath})`)
      return
    }
    report.push('- 状态：RUNNING', `- Sidecar：${sidecarExecutable ? 'frozen' : 'source'}`, `- 只读来源：${kernel.directory}`)
    const details = await verifyKernel(kernel)
    await smoke(kernel, details, sidecarExecutable, report)
    report[report.indexOf('- 状态：RUNNING')] = '- 状态：PASSED'
    await writeSmokeReport(report, appendReport)
    console.log(`profile test browser smoke passed (${process.platform}/${process.arch}); report: ${reportPath}`)
  } catch (error) {
    report.push('- 状态：FAILED', `- 错误：${error instanceof Error ? error.message : String(error)}`)
    await writeSmokeReport(report, appendReport)
    throw error
  }
}

async function writeSmokeReport(lines, append) {
  const current = `${lines.join('\n')}\n`
  if (!append) return writeFile(reportPath, current)
  const previous = await readFile(reportPath, 'utf8').catch(() => '')
  return writeFile(reportPath, previous ? `${previous.trimEnd()}\n\n---\n\n${current}` : current)
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch(error => { console.error(error instanceof Error ? error.stack : error); process.exitCode = 1 })
}
