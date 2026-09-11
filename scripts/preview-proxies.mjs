import { spawn } from 'node:child_process'
import { createHash, randomBytes } from 'node:crypto'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { createInterface } from 'node:readline'
import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const dataDir = resolve(tmpdir(), `autoflow-proxy-preview-${createHash('sha256').update(root).digest('hex').slice(0, 12)}`)
const token = randomBytes(32).toString('hex')
const child = spawn('uv', [
  'run', '--directory', 'apps/backend', 'python', '-m', 'autoflow',
  '--instance-id', 'proxy-preview', '--data-dir', dataDir, '--port', '0',
  '--parent-pid', String(process.pid),
], {
  cwd: root,
  env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token, AUTOFLOW_HOST_TOKEN: '' },
  stdio: ['ignore', 'pipe', 'inherit'],
})
let server
let closing = false
async function close() {
  if (closing) return
  closing = true
  await server?.close()
  await stop(child)
}
for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => { void close() })

try {
  const ready = await new Promise((resolveReady, reject) => {
    const lines = createInterface({ input: child.stdout })
    const timer = setTimeout(() => reject(new Error('sidecar readiness timeout')), 15_000)
    const finish = () => { clearTimeout(timer); lines.close() }
    lines.on('line', line => {
      if (!line.startsWith('AUTOFLOW_READY ')) return
      try {
        const value = JSON.parse(line.slice('AUTOFLOW_READY '.length))
        if (!Number.isInteger(value.port) || value.port < 1 || value.port > 65535) throw new Error('invalid readiness')
        finish(); resolveReady(value)
      } catch (error) { finish(); reject(error) }
    })
    child.once('error', error => { finish(); reject(error) })
    child.once('exit', () => { finish(); reject(new Error('sidecar stopped')) })
  })
  server = await createServer({
    configFile: false,
    root: resolve(root, 'apps/desktop/src/renderer'),
    plugins: [react(), tailwindcss()],
    server: {
      host: '127.0.0.1', port: 0,
      fs: { allow: [root] },
      proxy: {
        '/api/v1': { target: `http://127.0.0.1:${ready.port}`, headers: { 'x-autoflow-token': token } },
      },
    },
  })
  await server.listen()
  const address = server.httpServer.address()
  console.log(`代理管理预览：http://127.0.0.1:${address.port}/proxy-preview.html`)
  child.once('exit', () => { void close() })
} catch (error) {
  console.error(error instanceof Error ? error.message : 'preview failed')
  await close()
  process.exitCode = 1
}
