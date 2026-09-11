import { randomUUID } from 'node:crypto'
import { closeSync, copyFileSync, existsSync, fsyncSync, lstatSync, mkdirSync, openSync, readFileSync, readdirSync, realpathSync, renameSync, unlinkSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import type { UiPreferences } from '../../shared/settings'

export class SettingsError extends Error {
  constructor(readonly code: string, message: string) { super(message); this.name = 'SettingsError' }
}
export type StoredSettings = { schemaVersion: 1; currentPath: string; previousPath: string | null; preferences: UiPreferences }
export const WORKSPACE_MARKER = '.autoflow-workspace.json'
export const DEFAULT_PREFERENCES: UiPreferences = { zoom: 100, motion: 'system' }

export function validatePreferences(value: unknown): UiPreferences {
  if (!value || typeof value !== 'object') throw new SettingsError('INVALID_PREFERENCES', '界面偏好格式无效')
  const p = value as Record<string, unknown>
  if (![90, 100, 110, 125].includes(Number(p.zoom)) || typeof p.zoom !== 'number' || !['system', 'reduce', 'full'].includes(String(p.motion)) || Object.keys(p).some(key => !['zoom', 'motion'].includes(key))) throw new SettingsError('INVALID_PREFERENCES', '请选择支持的缩放比例与动效模式')
  return { zoom: p.zoom, motion: p.motion } as UiPreferences
}

function readSettings(path: string): StoredSettings {
  if (lstatSync(path).isSymbolicLink() || lstatSync(path).size > 65_536) throw new Error('Invalid settings file')
  const value = JSON.parse(readFileSync(path, 'utf8')) as StoredSettings
  if (value.schemaVersion !== 1 || typeof value.currentPath !== 'string' || !value.currentPath || resolve(value.currentPath) !== value.currentPath || (value.previousPath !== null && (typeof value.previousPath !== 'string' || resolve(value.previousPath) !== value.previousPath))) throw new Error('Invalid settings schema')
  return { schemaVersion: 1, currentPath: value.currentPath, previousPath: value.previousPath, preferences: validatePreferences(value.preferences) }
}

export function writeAtomic(path: string, contents: string): void {
  if (existsSync(path) && lstatSync(path).isSymbolicLink()) throw new SettingsError('INVALID_PATH', '不能写入符号链接')
  const temporary = `${path}.${randomUUID()}.tmp`
  let descriptor: number | undefined
  try {
    descriptor = openSync(temporary, 'wx', 0o600)
    writeFileSync(descriptor, contents)
    fsyncSync(descriptor)
    closeSync(descriptor); descriptor = undefined
    renameSync(temporary, path)
  } finally {
    if (descriptor !== undefined) closeSync(descriptor)
    if (existsSync(temporary)) unlinkSync(temporary)
  }
}

export function inspectWorkspace(input: string, allowEmpty = true): { path: string; kind: 'empty' | 'existing' } {
  try {
    if (!lstatSync(input).isDirectory() || lstatSync(input).isSymbolicLink()) throw new SettingsError('INVALID_WORKSPACE', '请选择真实目录，不能使用文件或符号链接')
    const path = realpathSync(input)
    const marker = join(path, WORKSPACE_MARKER)
    if (existsSync(marker)) {
      if (lstatSync(marker).isSymbolicLink() || lstatSync(marker).size > 4096) throw new SettingsError('INVALID_WORKSPACE', '工作区标记无效')
      const value = JSON.parse(readFileSync(marker, 'utf8'))
      if (value.schemaVersion !== 1 || value.kind !== 'autoflow-workspace') throw new SettingsError('INVALID_WORKSPACE', '此目录不是当前版本的 AutoFlow 工作区')
      for (const child of ['data', 'workspace', 'logs', 'cache', 'tmp', 'data/kernels', 'workspace/profiles', 'data/autoflow.sqlite3', 'data/autoflow.sqlite3-wal', 'data/autoflow.sqlite3-shm']) {
        const entry = join(path, child)
        const stat = lstatSync(entry, { throwIfNoEntry: false })
        const databaseFile = child.startsWith('data/autoflow.sqlite3')
        if (stat && (stat.isSymbolicLink() || (databaseFile ? !stat.isFile() : !stat.isDirectory()))) throw new SettingsError('INVALID_WORKSPACE', '工作区目录或数据库文件无效，不能使用符号链接')
      }
      return { path, kind: 'existing' }
    }
    if (allowEmpty && readdirSync(path).length === 0) return { path, kind: 'empty' }
    throw new SettingsError('UNRECOGNIZED_WORKSPACE', '目录非空且没有本版工作区标记；请选择空目录或本版工作区，旧数据不能直接打开')
  } catch (error) {
    if (error instanceof SettingsError) throw error
    throw new SettingsError('INVALID_WORKSPACE', '无法读取工作区，请检查目录是否存在及访问权限')
  }
}

export function ensureWritable(path: string): void {
  const probe = join(path, `.autoflow-write-${randomUUID()}`)
  try { writeFileSync(probe, '', { flag: 'wx', mode: 0o600 }) } catch { throw new SettingsError('WORKSPACE_NOT_WRITABLE', '目录不可写，请选择其他位置') } finally { if (existsSync(probe)) unlinkSync(probe) }
}

export function initializeWorkspace(path: string): void {
  const inspected = inspectWorkspace(path)
  ensureWritable(inspected.path)
  if (inspected.kind === 'empty') writeFileSync(join(inspected.path, WORKSPACE_MARKER), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }), { flag: 'wx', mode: 0o600 })
}

export class DesktopSettingsStore {
  readonly path: string
  constructor(readonly userData: string) { mkdirSync(userData, { recursive: true }); this.path = join(userData, 'desktop-settings.json') }

  load(): { settings: StoredSettings; recovery: string | null; needsSelection: boolean } {
    const defaults: StoredSettings = { schemaVersion: 1, currentPath: realpathSync(this.userData), previousPath: null, preferences: { ...DEFAULT_PREFERENCES } }
    if (!existsSync(this.path) && !existsSync(`${this.path}.bak`)) {
      // The OS-provided baseline root is already owned by this app; adopt it in place.
      if (existsSync(join(this.userData, '.autoflow-rebuild-workspace'))) return { settings: defaults, recovery: '检测到旧版工作区，请重新选择本版工作区或空目录', needsSelection: true }
      const marker = join(this.userData, WORKSPACE_MARKER)
      if (!existsSync(marker)) writeFileSync(marker, JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }), { flag: 'wx', mode: 0o600 })
      this.save(defaults)
      return { settings: defaults, recovery: null, needsSelection: false }
    }
    try { return { settings: readSettings(this.path), recovery: null, needsSelection: false } } catch { /* Try the last valid backup without overwriting evidence. */ }
    try {
      const settings = readSettings(`${this.path}.bak`)
      if (existsSync(this.path)) {
        if (lstatSync(this.path).isSymbolicLink()) throw new Error('Invalid settings path')
        copyFileSync(this.path, `${this.path}.corrupt-${randomUUID()}`)
      }
      writeAtomic(this.path, JSON.stringify(settings, null, 2))
      return { settings, recovery: '本机设置已从备份恢复，原损坏文件已保留', needsSelection: false }
    } catch {
      return { settings: defaults, recovery: '本机设置与备份无法读取，请重新选择工作区；原文件已保留', needsSelection: true }
    }
  }

  save(settings: StoredSettings): void {
    if (existsSync(this.path)) {
      if (lstatSync(this.path).isSymbolicLink()) throw new SettingsError('INVALID_PATH', '本机设置文件不能是符号链接')
      let valid = false
      try { readSettings(this.path); valid = true } catch {
        copyFileSync(this.path, `${this.path}.corrupt-${randomUUID()}`)
      }
      if (valid) writeAtomic(`${this.path}.bak`, readFileSync(this.path, 'utf8'))
    }
    writeAtomic(this.path, JSON.stringify(settings, null, 2))
  }
}
