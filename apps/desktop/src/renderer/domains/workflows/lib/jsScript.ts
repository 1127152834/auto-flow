import type { components } from '../../../shared/api/generated'
type ScriptResult = components['schemas']['StudioJsScriptResult']
export type JsScriptOutcome = Pick<ScriptResult, 'success'> & Partial<Pick<ScriptResult, 'result' | 'variables' | 'error'>>

/** JSON roundtrip without silently dropping unsupported values or converting non-finite numbers. */
function jsonCopy<T>(value: T): T {
  const ancestors = new Set<object>()
  const check = (item: unknown): void => {
    if (item === null || typeof item === 'string' || typeof item === 'boolean') return
    if (typeof item === 'number' && Number.isFinite(item)) return
    if (typeof item !== 'object' || (!Array.isArray(item) && Object.getPrototypeOf(item) !== Object.prototype && Object.getPrototypeOf(item) !== null)) throw new Error('脚本结果包含非 JSON 值')
    if (Object.getOwnPropertySymbols(item).length || ancestors.has(item)) throw new Error('脚本结果包含符号或循环引用')
    ancestors.add(item)
    for (const value of Array.isArray(item) ? item : Object.values(item)) check(value)
    ancestors.delete(item)
  }
  check(value)
  return JSON.parse(JSON.stringify(value)) as T
}

export function evaluateJsScript(code: string, variables: Record<string, unknown>): JsScriptOutcome {
  try {
    const vars = jsonCopy(variables)
    const execute = new Function('vars', `${code}\nif (typeof main !== 'function') throw new Error('未找到 main(vars) 函数');\nreturn main(vars);`)
    const value: unknown = execute(vars)
    if (value && (typeof value === 'object' || typeof value === 'function') && 'then' in value && typeof value.then === 'function') {
      // Consume rejection to avoid an unhandled Promise while rejecting unsupported asynchronous results.
      void Promise.resolve(value).catch(() => {})
      throw new Error('脚本节点仅支持同步 main(vars)，不支持异步结果')
    }
    return { success: true, result: jsonCopy(value === undefined ? null : value), variables: jsonCopy(vars) }
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : String(error) }
  }
}
