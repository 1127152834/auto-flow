import { spawnSync } from 'node:child_process'

const sync = spawnSync('uv', ['sync', '--directory', 'apps/backend', '--group', 'build'], { stdio: 'inherit' })
if (sync.error || sync.status !== 0) {
  console.error(sync.error?.message ?? 'uv sync failed')
  process.exitCode = sync.status ?? 1
} else {
  const result = spawnSync(
    'uv',
    ['--directory', 'apps/backend', 'run', 'pyinstaller', '--noconfirm', 'autoflow-backend.spec'],
    { stdio: 'inherit' },
  )

  if (result.error) {
    console.error(result.error.message)
    process.exitCode = 1
  } else {
    process.exitCode = result.status ?? 1
  }
}
