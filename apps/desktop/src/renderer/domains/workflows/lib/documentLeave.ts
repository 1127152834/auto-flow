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

export type LeaveResource = {
  id: string
  label: string
  release: () => Promise<boolean>
}
type ResourceReader = () => LeaveResource | null
const resources = new Set<ResourceReader>()

/** Readers capture actual session identities, including requests awaiting confirmation. */
export function registerDocumentLeaveResource(read: ResourceReader): () => void {
  resources.add(read)
  return () => { resources.delete(read) }
}

export function getDocumentLeaveResources(): LeaveResource[] {
  return Array.from(resources, read => read()).filter((resource): resource is LeaveResource => resource !== null)
}
