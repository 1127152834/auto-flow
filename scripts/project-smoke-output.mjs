import assert from 'node:assert/strict'
import { realpath } from 'node:fs/promises'
import path from 'node:path'

export function isWithinPath(parent, target, paths = path) {
  const relative = paths.relative(parent, target)
  return !paths.isAbsolute(relative) && relative !== '..' && !relative.startsWith(`..${paths.sep}`)
}

// Resolve the nearest existing ancestor without creating a directory. This also
// catches /alias/new when /alias points to the historical evidence directory.
async function canonicalDestination(destination) {
  let current = path.resolve(destination)
  const suffix = []
  while (true) {
    try {
      return path.resolve(await realpath(current), ...suffix.reverse())
    } catch (error) {
      const parent = path.dirname(current)
      if (error.code !== 'ENOENT' || parent === current) throw error
      suffix.push(path.basename(current))
      current = parent
    }
  }
}

export async function assertOutsideHistory(history, destination) {
  const [canonicalHistory, canonicalOutput] = await Promise.all([
    canonicalDestination(history), canonicalDestination(destination),
  ])
  assert.ok(!isWithinPath(canonicalHistory, canonicalOutput), 'output directory must preserve PM1 historical evidence')
}

export function redactSidecarLog(log, token) {
  return log.split('\n').filter(line => !line.trimStart().startsWith('AUTOFLOW_READY ')).join('\n').replaceAll(token || '[no-service-token]', '[redacted]').slice(-20_000)
}
