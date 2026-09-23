import type { ExperimentRecord } from './types'

const key = (workspaceKey: string) => `autoflow:laya-lab:v1:${JSON.stringify(workspaceKey)}`

export function readRecords(workspaceKey: string): ExperimentRecord[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key(workspaceKey)) ?? '[]')
    return Array.isArray(value) ? value.filter((item): item is ExperimentRecord =>
      typeof item === 'object' && item !== null && typeof item.id === 'string' && typeof item.createdAt === 'string' && typeof item.request === 'object' && typeof item.result === 'object').slice(0, 20) : []
  } catch { return [] }
}

export function saveRecord(workspaceKey: string, record: ExperimentRecord): ExperimentRecord[] {
  const records = [record, ...readRecords(workspaceKey)].slice(0, 20)
  localStorage.setItem(key(workspaceKey), JSON.stringify(records))
  return records
}

export function removeRecord(workspaceKey: string, id: string): ExperimentRecord[] {
  const records = readRecords(workspaceKey).filter(record => record.id !== id)
  localStorage.setItem(key(workspaceKey), JSON.stringify(records))
  return records
}
