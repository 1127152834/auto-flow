// Source: WebRPA@5ccb900e, components/workflow/config-panels/CustomModuleConfig.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 自定义模块配置面板
 */
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { Package, AlertCircle, Info } from 'lucide-react'
import { useCustomModuleStore } from '../../hooks/stores/customModuleStore'
import { useEffect, useState } from 'react'
import type { NodeData } from '../../editor-store'

interface CustomModuleConfigProps {
  data: NodeData
  onChange: (key: string, value: any) => void
}

export function CustomModuleConfig({ data, onChange }: CustomModuleConfigProps) {
  const { getModule } = useCustomModuleStore()
  const [module, setModule] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const moduleId = data.customModuleId as string

  useEffect(() => {
    const loadModule = async () => {
      if (!moduleId) {
        setLoading(false)
        return
      }

      try {
        const mod = await getModule(moduleId)
        setModule(mod)
      } catch (error) {
        console.error('加载自定义模块失败:', error)
      } finally {
        setLoading(false)
      }
    }

    loadModule()
  }, [moduleId, getModule])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-sm text-muted-foreground">加载中...</div>
      </div>
    )
  }

  if (!module) {
    return (
      <div className="space-y-4">
        <div className="flex items-start gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200">
          <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-900">模块不存在</p>
            <p className="text-xs text-amber-700 mt-1">
              该自定义模块可能已被删除，请重新选择模块或删除此节点。
            </p>
          </div>
        </div>
      </div>
    )
  }

  // 初始化参数值
  const parameterValues = (data.parameterValues as Record<string, any>) || {}

  const handleParameterChange = (paramName: string, value: any) => {
    const newValues = { ...parameterValues, [paramName]: value }
    onChange('parameterValues', newValues)
  }

  return (
    <div className="space-y-4">
      {/* 模块信息 */}
      <div className="bg-[hsl(var(--card))] p-4 rounded-lg border border-purple-200">
        <div className="flex items-start gap-3">
          <div className="bg-[hsl(var(--brand-600))] w-10 h-10 rounded-lg flex items-center justify-center text-white shadow-sm flex-shrink-0">
            <Package className="w-5 h-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-medium text-purple-900">{module.display_name || module.name}</h3>
            {module.description && (
              <p className="text-sm text-purple-700 mt-1">{module.description}</p>
            )}
            <div className="flex items-center gap-3 mt-2 text-xs text-purple-600">
              <span>{module.parameters?.length || 0} 个参数</span>
              <span>•</span>
              <span>{module.outputs?.length || 0} 个输出</span>
            </div>
          </div>
        </div>
      </div>

      {/* 参数配置 */}
      {module.parameters && module.parameters.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Info className="w-4 h-4 text-blue-500" />
            <span>输入参数</span>
          </div>
          {module.parameters.map((param: any) => (
            <div key={param.name} className="space-y-2">
              <Label htmlFor={`param-${param.name}`}>
                {param.label || param.name}
                {param.required && <span className="text-red-500 ml-1">*</span>}
              </Label>
              {param.description && (
                <p className="text-xs text-muted-foreground">{param.description}</p>
              )}
              <VariableInput
                id={`param-${param.name}`}
                value={parameterValues[param.name] || param.default_value || ''}
                onChange={(value) => handleParameterChange(param.name, value)}
                placeholder={param.placeholder || param.description || `请输入${param.label || param.name}`}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-6 text-sm text-muted-foreground">
          此模块没有输入参数
        </div>
      )}

      {/* 输出变量说明 */}
      {module.outputs && module.outputs.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Info className="w-4 h-4 text-green-500" />
            <span>输出变量</span>
          </div>
          <div className="p-3 rounded-lg bg-green-50 border border-green-200 space-y-2">
            {module.outputs.map((output: any) => (
              <div key={output.name} className="text-sm">
                <span className="font-mono text-green-700">{output.name}</span>
                <span className="text-green-600 ml-2">
                  ({output.label || output.name})
                </span>
                {output.description && (
                  <span className="text-green-600 ml-2">- {output.description}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 使用提示 */}
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-blue-700">
            <p className="font-medium mb-1">使用说明</p>
            <p>此模块会执行预定义的工作流逻辑，输入参数会传递给内部工作流，执行完成后输出变量会自动创建。</p>
          </div>
        </div>
      </div>
    </div>
  )
}
