import { execFile } from 'node:child_process'
import { readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import openapiTS, { astToString } from 'openapi-typescript'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const outputPath = resolve(root, 'apps/desktop/src/renderer/shared/api/generated.ts')
const execute = promisify(execFile)

async function main() {
  const { stdout } = await execute('uv', [
    'run', '--directory', 'apps/backend', 'python', '-m', 'autoflow.bootstrap.schema_export',
  ], { cwd: root, maxBuffer: 32 * 1024 * 1024, timeout: 30_000 })
  const schema = JSON.parse(stdout)
  const generated = astToString(await openapiTS(schema, { exportType: 'default' }))
  const current = await readFile(outputPath, 'utf8').catch(() => undefined)
  if (process.argv.includes('--check')) {
    if (current !== generated) throw new Error(`generated API is stale: ${outputPath}`)
  } else {
    await writeFile(outputPath, generated)
  }
}

main().catch(error => { console.error(error instanceof Error ? error.message : error); process.exitCode = 1 })
