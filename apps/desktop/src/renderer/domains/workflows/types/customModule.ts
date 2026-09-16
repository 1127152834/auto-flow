import type { Variable } from './index'
// Source: WebRPA@5ccb900e, types/customModule.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 自定义模块类型定义
 */

export interface CustomModuleParameter {
  name: string
  label: string
  type: 'string' | 'number' | 'boolean' | 'select' | 'textarea'
  default_value: any
  required: boolean
  placeholder: string
  description: string
  options: Array<{ label: string; value: string }>
}

export interface CustomModuleOutput {
  name: string
  label: string
  description: string
}

export interface CustomModule {
  id: string
  revision: number
  name: string
  display_name: string
  description: string
  icon: string
  color: string
  category: string
  parameters: CustomModuleParameter[]
  outputs: CustomModuleOutput[]
  workflow: {
    nodes: any[]
    edges: any[]
    variables?: Variable[]
  }
  author: string
  version: string
  tags: string[]
  usage_count: number
  download_count: number
  created_at: string
  updated_at: string
  is_published: boolean
  is_builtin: boolean
  is_favorite: boolean
  sort_order: number
}

export interface CustomModuleCreate {
  name: string
  display_name: string
  description: string
  icon: string
  color: string
  category: string
  parameters: CustomModuleParameter[]
  outputs: CustomModuleOutput[]
  workflow: {
    nodes: any[]
    edges: any[]
    variables?: Variable[]
  }
  tags: string[]
}
