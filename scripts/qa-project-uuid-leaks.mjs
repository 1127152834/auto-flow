import assert from 'node:assert/strict'

const PERCEPTIBLE_ATTRIBUTES = Object.freeze([
  'title',
  'placeholder',
  'aria-label',
  'aria-description',
])

/**
 * Runs inside the renderer. It checks only fixture-owned identities supplied by
 * the QA scenario; it does not classify arbitrary UUID-looking user content.
 */
export function auditPerceptibleIdentities(systemIds, businessIds, documentRoot = document) {
  const systems = [...new Set(systemIds.filter(value => typeof value === 'string' && value))]
  const businesses = [...new Set(businessIds.filter(value => typeof value === 'string' && value))]
  const sources = [{ source: 'body.innerText', text: documentRoot.body?.innerText ?? '' }]

  for (const attribute of ['title', 'placeholder', 'aria-label', 'aria-description']) {
    for (const element of documentRoot.querySelectorAll(`[${attribute}]`)) {
      sources.push({
        source: attribute,
        text: element.getAttribute(attribute) ?? '',
        element: element.tagName?.toLowerCase() ?? 'unknown',
      })
    }
  }

  const hits = []
  const recordMatches = (source, systemId, needle, match) => {
    let offset = source.text.indexOf(needle)
    while (offset !== -1) {
      // A full UUID also contains its prefix. Keep the stronger finding only.
      const insideFullValue = [systemId, ...businesses].some(value => {
        const start = source.text.lastIndexOf(value, offset)
        return start >= 0 && offset + needle.length <= start + value.length
      })
      if (match === 'full' || !insideFullValue) {
        hits.push({
          systemId,
          match,
          source: source.source,
          ...(source.element ? { element: source.element } : {}),
          context: source.text.slice(Math.max(0, offset - 24), offset + needle.length + 24),
        })
      }
      offset = source.text.indexOf(needle, offset + needle.length)
    }
  }
  for (const systemId of systems) {
    for (const source of sources) {
      recordMatches(source, systemId, systemId, 'full')
    }
    const prefix = systemId.slice(0, 8)
    if (prefix.length === 8) {
      for (const source of sources) {
        recordMatches(source, systemId, prefix, 'prefix')
      }
    }
  }

  return {
    hits,
    missingBusinessIds: businesses.filter(
      businessId => !sources.some(source => source.text.includes(businessId)),
    ),
  }
}

export async function checkCdpPage(cdp, systemIds, businessIds = []) {
  const expression = `(${auditPerceptibleIdentities.toString()})(${JSON.stringify(systemIds)},${JSON.stringify(businessIds)},document)`
  const result = await cdp.evaluate(expression)
  assert.deepEqual(
    result.missingBusinessIds,
    [],
    `用户业务 UUID 应保持可见: ${result.missingBusinessIds.join(', ')}`,
  )
  assert.deepEqual(result.hits, [], formatHits(result.hits))
  return result
}

function formatHits(hits) {
  if (!hits.length) return '未发现内部身份泄露'
  return `发现内部身份泄露:\n${hits.map(hit =>
    `${hit.match === 'full' ? '完整 ID' : '截断 ID'} ${hit.systemId} @ ${hit.source}${hit.element ? ` <${hit.element}>` : ''}: ${JSON.stringify(hit.context)}`,
  ).join('\n')}`
}

export { PERCEPTIBLE_ATTRIBUTES }
