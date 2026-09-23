import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import yaml from 'js-yaml'

test('CI avoids duplicate same-repository draft matrices but preserves ready, fork and probe checks', () => {
  const workflow = yaml.load(readFileSync(new URL('../.github/workflows/ci.yml', import.meta.url), 'utf8'))
  const check = Function('github', 'inputs', `return ${workflow.jobs.checks.if}`)
  const run = (event, draft = true, repo = 'owner/repo', native = false, worker = false) => check({ event_name: event, repository: 'owner/repo', event: { pull_request: { draft, head: { repo: { full_name: repo } } } } }, { pm9NativeProbe: native, pm9WorkerProbe: worker })
  assert.equal(run('push'), true)
  assert.equal(run('pull_request'), false)
  assert.equal(run('pull_request', false), true)
  assert.equal(run('pull_request', true, 'fork/repo'), true)
  assert.equal(run('workflow_dispatch'), true)
  assert.equal(run('workflow_dispatch', true, '', true), false)
  assert.equal(run('workflow_dispatch', true, '', false, true), false)
})
