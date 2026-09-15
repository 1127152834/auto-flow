import assert from 'node:assert/strict'
import test from 'node:test'

import {
  auditPerceptibleIdentities,
  checkCdpPage,
} from './qa-project-uuid-leaks.mjs'

const SYSTEM_ID = '11111111-1111-4111-8111-111111111111'
const BUSINESS_ID = '22222222-2222-4222-8222-222222222222'

function fakeDocument(bodyText = '', attributes = {}) {
  return {
    body: { innerText: bodyText },
    querySelectorAll(selector) {
      const name = selector.slice(1, -1)
      return (attributes[name] ?? []).map(([tagName, value]) => ({
        tagName,
        getAttribute(attribute) {
          return attribute === name ? value : null
        },
      }))
    },
  }
}

test('reports a known full system UUID in visible text and perceptible attributes', () => {
  const result = auditPerceptibleIdentities(
    [SYSTEM_ID],
    [],
    fakeDocument(`任务 ${SYSTEM_ID}`, {
      title: [['DIV', `批次 ${SYSTEM_ID}`]],
      placeholder: [['INPUT', `搜索 ${SYSTEM_ID}`]],
      'aria-label': [['BUTTON', `删除 ${SYSTEM_ID}`]],
      'aria-description': [['BUTTON', `影响 ${SYSTEM_ID}`]],
      value: [['INPUT', SYSTEM_ID]],
      href: [['A', `#/tasks/${SYSTEM_ID}`]],
      'data-id': [['DIV', SYSTEM_ID]],
    }),
  )

  assert.equal(result.hits.filter(hit => hit.match === 'full').length, 5)
  assert.deepEqual(new Set(result.hits.map(hit => hit.source)), new Set([
    'body.innerText', 'title', 'placeholder', 'aria-label', 'aria-description',
  ]))
  assert.ok(result.hits.every(hit => hit.context.length < 100))
})

test('reports a known eight-character system prefix without scanning arbitrary UUIDs', () => {
  const result = auditPerceptibleIdentities(
    [SYSTEM_ID],
    [],
    fakeDocument('任务 11111111；用户数据 33333333-3333-4333-8333-333333333333'),
  )

  assert.equal(result.hits.length, 1)
  assert.equal(result.hits[0].match, 'prefix')
  assert.equal(result.hits[0].systemId, SYSTEM_ID)
  assert.match(result.hits[0].context, /任务 11111111/)
})

test('keeps a user-owned UUID visible and excludes its shared prefix from prefix checks', () => {
  const systemWithSharedPrefix = '22222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  const result = auditPerceptibleIdentities(
    [systemWithSharedPrefix],
    [BUSINESS_ID],
    fakeDocument(`业务身份 ${BUSINESS_ID}`),
  )

  assert.deepEqual(result, { hits: [], missingBusinessIds: [] })
})

test('does not inspect DOM value, href, hash, data attributes, or hidden implementation state', () => {
  const result = auditPerceptibleIdentities([SYSTEM_ID], [], fakeDocument('', {
    value: [['INPUT', SYSTEM_ID]],
    href: [['A', `#/tasks/${SYSTEM_ID}`]],
    'data-id': [['DIV', SYSTEM_ID]],
  }))

  assert.deepEqual(result, { hits: [], missingBusinessIds: [] })
})

test('checkCdpPage sends a self-contained audit to evaluate and rejects missing business UUIDs', async () => {
  let expression = ''
  const cdp = {
    async evaluate(value) {
      expression = value
      return { hits: [], missingBusinessIds: [BUSINESS_ID] }
    },
  }

  await assert.rejects(
    checkCdpPage(cdp, [SYSTEM_ID], [BUSINESS_ID]),
    /用户业务 UUID 应保持可见/,
  )
  assert.match(expression, /querySelectorAll/)
  assert.match(expression, new RegExp(SYSTEM_ID))
})

test('checkCdpPage audit expression executes without module bindings in the renderer', async () => {
  const documentRoot = fakeDocument(`业务身份 ${BUSINESS_ID}`)
  const cdp = {
    async evaluate(expression) {
      return Function('document', `return ${expression}`)(documentRoot)
    },
  }

  assert.deepEqual(
    await checkCdpPage(cdp, [SYSTEM_ID], [BUSINESS_ID]),
    { hits: [], missingBusinessIds: [] },
  )
})

test('a business UUID sharing a prefix does not hide a separate technical short ID', () => {
  const systemWithSharedPrefix = '22222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
  const result = auditPerceptibleIdentities([systemWithSharedPrefix], [BUSINESS_ID], fakeDocument(`任务 22222222；业务编号 ${BUSINESS_ID}`))
  assert.equal(result.hits.length, 1)
  assert.equal(result.hits[0].match, 'prefix')
  assert.deepEqual(result.missingBusinessIds, [])
})
