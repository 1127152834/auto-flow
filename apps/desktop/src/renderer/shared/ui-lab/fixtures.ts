export const kernelOptions = Array.from({ length: 500 }, (_, index) => ({
  id: `kernel-${index + 1}`,
  label: `CloakBrowser 146 · #${String(index + 1).padStart(4, '0')}`,
}))
export const longOption = { id: 'long-kernel', label: `长名称验收 · ${'中文描述与资源标识 '.repeat(20)}` }
export type LabOption = typeof kernelOptions[number]
