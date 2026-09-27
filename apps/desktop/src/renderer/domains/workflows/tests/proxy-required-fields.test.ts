import { describe, expect, it } from 'vitest'
import metadata from '../development/module-required-fields.json'
import { getMissingRequired, getMissingRequiredLabels } from '../lib/requiredFields'

describe.each(['proxy_query', 'proxy_change_ip', 'proxy_change_location'])('%s configuration admission', type => {
  const missing = (data: Record<string, unknown>) => getMissingRequired(type, data, metadata.requiredFields, metadata.conditionalRequired)
  it('requires an explicit proxy only for specified targets', () => {
    expect(missing({ target: 'specified', locationId: 'city' })).toEqual(['proxyId'])
    expect(missing({ locationId: 'city' })).toEqual([])
    expect(missing({ target: 'specified', proxyId: '${proxy}', locationId: '${city}' })).toEqual([])
  })
  it('requires a location for relocation and reports readable labels', () => {
    expect(missing({ proxyId: 'proxy' })).toEqual(type === 'proxy_change_location' ? ['locationId'] : [])
    expect(getMissingRequiredLabels(type, { target: 'specified', locationId: 'city' }, metadata.requiredFields, metadata)).toEqual(['代理 ID／变量'])
  })
})
