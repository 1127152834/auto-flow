/** Project-owned errors are presented by code. Raw diagnostics never become UI copy. */
const messages: Record<string, string> = {
  REVISION_CONFLICT: '数据已更新，请读取最新内容后重试',
  VERSION_CONFLICT: '数据已更新，请读取最新内容后重试',
  RESOURCE_UNAVAILABLE: '所需资源暂不可用，请检查配置',
  NOT_FOUND: '资料暂不可用，请刷新后重试', RECORD_NOT_FOUND: '记录暂不可用，请刷新后重试',
  PROJECT_NAME_CONFLICT: '项目名称已存在，请使用其他名称', NAME_CONFLICT: '名称已存在，请使用其他名称',
  VALIDATION_ERROR: '填写内容有误，请检查后重试', INVALID_PROJECT_DATA: '填写内容有误，请检查后重试', INVALID_PROJECT_DATA_QUERY: '查询条件有误，请检查后重试',
  PROJECT_CLOSING: '项目正在关闭，请稍后重试', LIFECYCLE_CONFLICT: '项目当前为只读状态',
  RESOURCE_BUSY: '资源正在使用，请稍后重试', SETTINGS_QUIESCE_BLOCKED: '工作区正在切换，请稍后重试',
  OPERATION_NOT_FOUND: '原操作尚未接受，请核对后使用原请求重试',
  OPERATION_PAYLOAD_MISMATCH: '原请求与当前内容不一致，请先核对原操作',
  SIDECAR_UNAUTHORIZED: '本地服务连接已失效，请重新连接', UNAUTHORIZED: '本地服务连接已失效，请重新连接',
  EXCEL_IMPORT_FAILED: '导入失败，请检查文件后重试', EXCEL_EXPORT_FAILED: '导出失败，请重试',
  EXCEL_EXPORT_TARGET_CONFLICT: '目标文件已存在，请选择新的文件名',
  EXCEL_INSPECTION_EXPIRED: '文件检查已过期，请重新选择并检查文件',
  EXCEL_IMPORT_INTERRUPTED: '导入已中断，请先核对原操作', EXCEL_EXPORT_INTERRUPTED: '导出已中断，请先核对原操作',
  WORKFLOW_NOT_RUNNABLE: '工作流暂不可运行，请检查节点配置', WORKFLOW_NOT_FOUND: '工作流暂不可用，请重新选择',
  WORKFLOW_REVISION_CONFLICT: '工作流已更新，请重新检查运行条件',
  CORE_UNAVAILABLE: '运行服务暂不可用，请稍后重试', CAPABILITY_UNAVAILABLE: '当前运行能力暂不可用',
  ENVIRONMENT_SOURCE_NOT_SUPPORTED: '当前仅支持从浏览器配置创建临时环境',
  PM4_INPUTS_NOT_SUPPORTED: '已保存数据输入；数据执行能力暂未开放',
  RUN_EVENT_HISTORY_UNAVAILABLE: '运行历史暂不完整，请重新读取并核验',
  RUN_FACTS_INCOMPLETE: '运行资料暂不完整，请重新读取并核验',
  OPERATION_RESULT_UNKNOWN: '运行结果尚未确认，请先核对原操作',
  RUN_ARTIFACT_UNAVAILABLE: '运行产物暂不可用，请刷新后重试',
  PROFILE_NOT_FOUND: '浏览器配置暂不可用，请重新选择', KERNEL_NOT_INSTALLED: '浏览器内核未安装，请先安装',
  EXTERNAL_LINK_FAILED: '无法打开链接，请重试或复制链接',
  STATUS_IN_USE: '仍有记录使用此状态，请先修改这些记录的业务状态',
  FIELD_VALUES_INCOMPATIBLE: '现有记录不满足新的字段规则，请检查后重试',
}
export function safeProjectError(error: unknown): string {
  if (error && typeof error === 'object') {
    if ('name' in error && error.name === 'DataCommandUncertain') return '上次操作结果尚未确认，请先核对原操作'
    if ('name' in error && error.name === 'DataCommandNotAccepted') return '原操作尚未接受，请核对后使用原请求重试'
    const code = 'code' in error && typeof error.code === 'string' ? error.code : undefined
    if (code && Object.hasOwn(messages, code)) return messages[code]
  }
  return '操作失败，请重试'
}
export function safeProjectFieldErrors(fields: Record<string, string> | undefined): Record<string, string> {
  return Object.fromEntries(Object.keys(fields ?? {}).map(key => [key, '该字段填写有误，请检查']))
}
