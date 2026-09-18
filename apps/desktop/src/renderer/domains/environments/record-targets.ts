export type RecordTargetWrite = {
  recordRef: Record<string, unknown>
  expectedLinkRevision: number
  replaceAllowed: boolean
}

export type BindableRecord = RecordTargetWrite & {
  key: string
  alias: string
  currentEnvironmentId: string | null
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function recordKey(ref: Record<string, unknown>): string {
  const key = asRecord(ref.recordKey) ?? {}
  return [ref.projectId, ref.tableId, ref.datasetGeneration, key.type, key.value].map(item => String(item ?? '')).join('|')
}

export function bindableRecords(inputs: unknown[]): BindableRecord[] {
  const seen = new Set<string>()
  const items: BindableRecord[] = []
  for (const [index, raw] of inputs.entries()) {
    const item = asRecord(raw)
    const recordRef = asRecord(item?.recordRef)
    const revision = item?.linkRevision
    if (!item || !recordRef || typeof revision !== 'number') continue
    const key = recordKey(recordRef)
    if (seen.has(key)) continue
    seen.add(key)
    items.push({
      key,
      alias: typeof item.alias === 'string' && item.alias.trim() ? item.alias : `记录 ${index + 1}`,
      recordRef,
      expectedLinkRevision: revision,
      replaceAllowed: false,
      currentEnvironmentId: typeof item.currentEnvironmentId === 'string' ? item.currentEnvironmentId : null,
    })
  }
  return items
}

export function selectedTargets(items: BindableRecord[], selected: Set<string>, replaceAllowed: boolean): RecordTargetWrite[] {
  return items.filter(item => selected.has(item.key)).map(item => ({
    recordRef: item.recordRef,
    expectedLinkRevision: item.expectedLinkRevision,
      replaceAllowed,
  }))
}
