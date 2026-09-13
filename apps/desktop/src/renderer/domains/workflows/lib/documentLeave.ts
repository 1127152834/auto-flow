export type LeaveOptions = { preserveMainDocument?: boolean }
type LeaveHandler = (options?: LeaveOptions) => Promise<boolean>
let handler: LeaveHandler | undefined

/** Bridge non-React commands to the mounted Studio's save/discard/cancel UI. */
export function registerDocumentLeaveHandler(next: LeaveHandler): () => void {
  handler = next
  return () => { if (handler === next) handler = undefined }
}

export async function requestDocumentLeave(options?: LeaveOptions): Promise<boolean> {
  // A background command must not bypass protection when no editor is mounted.
  return handler ? handler(options) : false
}
