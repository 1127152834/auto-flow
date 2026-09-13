/** Compare persisted editor content without source-export timestamps or React Flow selection. */
export function snapshotKey(serialized: string): string {
  const document = JSON.parse(serialized)
  delete document.createdAt
  delete document.updatedAt
  if (Array.isArray(document.nodes)) document.nodes = document.nodes.map((node: Record<string, unknown>) => {
    const content = { ...node }
    delete content.selected
    delete content.dragging
    delete content.measured
    return content
  })
  return JSON.stringify(document)
}
