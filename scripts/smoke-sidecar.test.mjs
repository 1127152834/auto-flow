import test from 'node:test'
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { smokeMode, stop } from './smoke-sidecar.mjs'

test('packaged smoke cannot silently select external health mode', () => {
  assert.throws(() => smokeMode(['--executable', '/invalid/path'], {
    AUTOFLOW_BASE_URL: 'http://127.0.0.1:1', AUTOFLOW_INSTANCE_TOKEN: 'test',
  }), /cannot be combined/)
  assert.equal(smokeMode(['--executable', '/artifact'], {}).executable, '/artifact')
})

function childProcess() {
  const child = new EventEmitter()
  child.exitCode = null
  child.signalCode = null
  child.signals = []
  child.kill = signal => { child.signals.push(signal); return true }
  child.unref = () => {}
  return child
}

test('cleanup rejects after the final deadline if the child never exits', async () => {
  const child = childProcess()
  await assert.rejects(stop(child, { graceMs: 5, killMs: 5 }), /cleanup deadline/)
  assert.deepEqual(child.signals, ['SIGTERM', 'SIGKILL'])
  assert.equal(child.listenerCount('exit'), 0)
})

test('cleanup observes close without requiring exit', async () => {
  const child = childProcess()
  child.kill = () => { queueMicrotask(() => child.emit('close', 0)); return true }
  await stop(child, { graceMs: 5, killMs: 5 })
})

test('cleanup rejects a child process error', async () => {
  const child = childProcess()
  child.kill = () => { queueMicrotask(() => child.emit('error', new Error('kill failed'))); return false }
  await assert.rejects(stop(child, { graceMs: 5, killMs: 5 }), /kill failed/)
})
