import { spawn } from 'node:child_process'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const outputPath = resolve(root, 'apps/desktop/src/renderer/shared/api/generated.ts')
const token = `openapi-${process.pid}-${Date.now()}`

function waitForReady(child, timeoutMs = 15_000) {
  return new Promise((resolveReady, reject) => {
    let buffer = ''
    const timer = setTimeout(() => reject(new Error('backend readiness timeout')), timeoutMs)
    const fail = error => { clearTimeout(timer); reject(error) }
    child.stdout.on('data', chunk => {
      buffer += chunk.toString()
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('AUTOFLOW_READY ')) continue
        try {
          const ready = JSON.parse(line.slice('AUTOFLOW_READY '.length))
          if (!Number.isInteger(ready.port) || ready.port < 1 || ready.port > 65535) throw new Error('invalid backend readiness')
          clearTimeout(timer)
          resolveReady(ready)
        } catch (error) { fail(error) }
      }
    })
    child.once('error', fail)
    child.once('exit', code => fail(new Error(`backend exited before readiness (${code ?? 'unknown'})`)))
  })
}

async function stop(child) {
  if (child.exitCode !== null) return
  child.kill('SIGTERM')
  await new Promise(resolveDone => {
    const timer = setTimeout(() => { child.kill('SIGKILL'); resolveDone() }, 3_000)
    child.once('exit', () => { clearTimeout(timer); resolveDone() })
  })
}

async function main() {
  const dataDir = await mkdtemp(resolve(tmpdir(), 'autoflow-openapi-'))
  const child = spawn('uv', ['run', '--directory', 'apps/backend', 'python', '-m', 'autoflow', '--instance-id', 'openapi-generator', '--data-dir', dataDir, '--port', '0'], {
    cwd: root,
    env: { ...process.env, AUTOFLOW_INSTANCE_TOKEN: token },
    stdio: ['ignore', 'pipe', 'inherit'],
  })
  try {
    const ready = await waitForReady(child)
    const response = await fetch(`http://127.0.0.1:${ready.port}/openapi.json`)
    if (!response.ok) throw new Error(`openapi export failed: ${response.status}`)
    const schema = await response.json()
    const generated = astToString(await openapiTS(schema, { exportType: 'default' }))
    const current = await readFile(outputPath, 'utf8').catch(() => undefined)
    if (process.argv.includes('--check')) {
      if (current !== generated) throw new Error(`generated API is stale: ${outputPath}`)
    } else {
      await writeFile(outputPath, generated)
    }
  } finally {
    await stop(child)
    await rm(dataDir, { recursive: true, force: true })
  }
}

main().catch(error => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1 })
