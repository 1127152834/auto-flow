// Source: WebRPA@5ccb900e, components/workflow/EditCustomModuleDialog.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 编辑自定义模块对话框
 */
import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './controls/dialog'
import { Button } from './controls/button'
import { Input } from './controls/input'
import { Label } from './controls/label'
import { Textarea } from './controls/textarea'
import { SelectNative as Select } from './controls/select-native'
import { ColorPicker } from './controls/color-picker'
import { useCustomModuleStore } from '../hooks/stores/customModuleStore'
import { Plus, Trash2, AlertCircle, Edit, Save } from 'lucide-react'
import type { CustomModule, CustomModuleParameter, CustomModuleOutput } from '../types/customModule'

interface EditCustomModuleDialogProps {
  open: boolean
  onClose: () => void
  module: CustomModule
  onEditWorkflow?: () => void
}

export function EditCustomModuleDialog({ open, onClose, module, onEditWorkflow }: EditCustomModuleDialogProps) {
  const { updateModule } = useCustomModuleStore()
  
  const [displayName, setDisplayName] = useState(module.display_name)
  const [description, setDescription] = useState(module.description)
  const [icon, setIcon] = useState(module.icon)
  const [color, setColor] = useState(module.color || '#8B5CF6')
  const [category, setCategory] = useState(module.category)
  const [tags, setTags] = useState(module.tags?.join(', ') || '')
  const [parameters, setParameters] = useState<CustomModuleParameter[]>(module.parameters || [])
  const [outputs, setOutputs] = useState<CustomModuleOutput[]>(module.outputs || [])
  const [error, setError] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)
  
  // 当模块变化时重置表单
  useEffect(() => {
    if (module) {
      setDisplayName(module.display_name)
      setDescription(module.description)
      setIcon(module.icon)
      setColor(module.color || '#8B5CF6')
      setCategory(module.category)
      setTags(module.tags?.join(', ') || '')
      setParameters(module.parameters || [])
      setOutputs(module.outputs || [])
      setError('')
    }
  }, [module])
  
  // 添加参数
  const addParameter = () => {
    setParameters([...parameters, {
      name: `param${parameters.length + 1}`,
      label: `参数${parameters.length + 1}`,
      type: 'string',
      default_value: '',
      required: false,
      placeholder: '',
      description: '',
      options: []
    }])
  }
  
  // 删除参数
  const removeParameter = (index: number) => {
    setParameters(parameters.filter((_, i) => i !== index))
  }
  
  // 更新参数
  const updateParameter = (index: number, field: string, value: any) => {
    const newParams = [...parameters]
    newParams[index] = { ...newParams[index], [field]: value }
    setParameters(newParams)
  }
  
  // 添加输出
  const addOutput = () => {
    setOutputs([...outputs, {
      name: `output${outputs.length + 1}`,
      label: `输出${outputs.length + 1}`,
      description: ''
    }])
  }
  
  // 删除输出
  const removeOutput = (index: number) => {
    setOutputs(outputs.filter((_, i) => i !== index))
  }
  
  // 更新输出
  const updateOutput = (index: number, field: string, value: any) => {
    const newOutputs = [...outputs]
    newOutputs[index] = { ...newOutputs[index], [field]: value }
    setOutputs(newOutputs)
  }
  
  // 保存修改
  const handleSave = async () => {
    // 验证
    if (!displayName.trim()) {
      setError('请输入显示名称')
      return
    }
    
    setIsUpdating(true)
    setError('')
    
    try {
      const updateData = {
        display_name: displayName.trim(),
        description: description.trim(),
        icon,
        color,
        category,
        parameters,
        outputs,
        tags: tags.split(',').map(t => t.trim()).filter(Boolean)
      }
      
      const result = await updateModule(module.id, updateData)
      
      if (result) {
        onClose()
      } else {
        setError('更新失败，请重试')
      }
    } catch (err) {
      console.error('[EditCustomModuleDialog] 更新模块异常:', err)
      setError(String(err))
    } finally {
      setIsUpdating(false)
    }
  }
  
  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto bg-white">
        <DialogHeader>
          <DialogTitle>编辑自定义模块</DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6 py-4">
          {/* 基本信息 */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium">基本信息</h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="displayName">显示名称 *</Label>
                <Input
                  id="displayName"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="例如：数据处理"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="icon">图标</Label>
                <Input
                  id="icon"
                  value={icon}
                  onChange={(e) => setIcon(e.target.value)}
                  placeholder="例如："
                  maxLength={2}
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="description">描述</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="描述这个模块的功能..."
                rows={3}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <ColorPicker
                label="模块颜色"
                value={color}
                onChange={setColor}
              />
              
              <div className="space-y-2">
                <Label htmlFor="category">分类</Label>
                <Select
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="自定义">自定义</option>
                  <option value="自动化">自动化</option>
                  <option value="数据处理">数据处理</option>
                  <option value="AI">AI</option>
                  <option value="工具">工具</option>
                  <option value="网页操作">网页操作</option>
                  <option value="文件操作">文件操作</option>
                  <option value="API">API</option>
                  <option value="邮件">邮件</option>
                  <option value="通知">通知</option>
                  <option value="图像处理">图像处理</option>
                  <option value="文本处理">文本处理</option>
                  <option value="Excel">Excel</option>
                  <option value="PDF">PDF</option>
                  <option value="爬虫">爬虫</option>
                  <option value="测试">测试</option>
                  <option value="监控">监控</option>
                  <option value="定时任务">定时任务</option>
                  <option value="流程控制">流程控制</option>
                  <option value="系统操作">系统操作</option>
                  <option value="网络">网络</option>
                  <option value="安全">安全</option>
                  <option value="其他">其他</option>
                </Select>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="tags">标签（用逗号分隔）</Label>
              <Input
                id="tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="例如：数据,处理,自动化"
              />
            </div>
          </div>

          {/* 工作流编辑按钮 */}
          {onEditWorkflow && (
            <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
              <div className="flex items-start gap-3">
                <Edit className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-900">编辑内部工作流</p>
                  <p className="text-xs text-blue-700 mt-1">
                    点击下方按钮可以编辑模块内部的工作流逻辑
                  </p>
                  <Button
                    onClick={onEditWorkflow}
                    size="sm"
                    className="mt-2 bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <Edit className="w-4 h-4 mr-1" />
                    编辑工作流
                  </Button>
                </div>
              </div>
            </div>
          )}
          
          {/* 参数定义 */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">输入参数</h3>
              <Button onClick={addParameter} size="sm" variant="tonal-success">
                <Plus className="w-4 h-4 mr-1" />
                添加参数
              </Button>
            </div>
            
            {parameters.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                还没有参数，点击上方按钮添加
              </p>
            ) : (
              <div className="space-y-3">
                {parameters.map((param, index) => (
                  <div key={index} className="p-3 rounded-lg border bg-gray-50 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">参数 {index + 1}</span>
                      <Button
                        onClick={() => removeParameter(index)}
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">参数名（英文）</Label>
                        <Input
                          value={param.name}
                          onChange={(e) => updateParameter(index, 'name', e.target.value)}
                          placeholder="param1"
                          className="h-8 text-sm"
                        />
                      </div>
                      
                      <div className="space-y-1">
                        <Label className="text-xs">显示标签</Label>
                        <Input
                          value={param.label}
                          onChange={(e) => updateParameter(index, 'label', e.target.value)}
                          placeholder="参数1"
                          className="h-8 text-sm"
                        />
                      </div>
                      
                      <div className="space-y-1">
                        <Label className="text-xs">类型</Label>
                        <Select
                          value={param.type}
                          onChange={(e) => updateParameter(index, 'type', e.target.value)}
                          className="h-8 text-sm"
                        >
                          <option value="string">文本</option>
                          <option value="number">数字</option>
                          <option value="boolean">布尔值</option>
                          <option value="textarea">多行文本</option>
                          <option value="select">下拉选择</option>
                        </Select>
                      </div>
                      
                      <div className="space-y-1">
                        <Label className="text-xs">默认值</Label>
                        <Input
                          value={param.default_value}
                          onChange={(e) => updateParameter(index, 'default_value', e.target.value)}
                          placeholder="默认值"
                          className="h-8 text-sm"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-1">
                      <Label className="text-xs">描述</Label>
                      <Input
                        value={param.description}
                        onChange={(e) => updateParameter(index, 'description', e.target.value)}
                        placeholder="参数说明"
                        className="h-8 text-sm"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* 输出定义 */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">输出变量</h3>
              <Button onClick={addOutput} size="sm" variant="tonal-success">
                <Plus className="w-4 h-4 mr-1" />
                添加输出
              </Button>
            </div>
            
            {outputs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                还没有输出变量，点击上方按钮添加
              </p>
            ) : (
              <div className="space-y-3">
                {outputs.map((output, index) => (
                  <div key={index} className="p-3 rounded-lg border bg-gray-50 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">输出 {index + 1}</span>
                      <Button
                        onClick={() => removeOutput(index)}
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">变量名（英文）</Label>
                        <Input
                          value={output.name}
                          onChange={(e) => updateOutput(index, 'name', e.target.value)}
                          placeholder="output1"
                          className="h-8 text-sm"
                        />
                      </div>
                      
                      <div className="space-y-1">
                        <Label className="text-xs">显示标签</Label>
                        <Input
                          value={output.label}
                          onChange={(e) => updateOutput(index, 'label', e.target.value)}
                          placeholder="输出1"
                          className="h-8 text-sm"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-1">
                      <Label className="text-xs">描述</Label>
                      <Input
                        value={output.description}
                        onChange={(e) => updateOutput(index, 'description', e.target.value)}
                        placeholder="输出说明"
                        className="h-8 text-sm"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* 错误提示 */}
          {error && (
            <div className="flex items-start gap-3 p-4 rounded-lg bg-red-50 border border-red-200">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-900">错误</p>
                <p className="text-xs text-red-700 mt-1">{error}</p>
              </div>
            </div>
          )}
        </div>
        
        <DialogFooter>
          <Button onClick={onClose} variant="outline" disabled={isUpdating}>
            取消
          </Button>
          <Button variant="success" onClick={handleSave} disabled={isUpdating}>
            <Save className="w-4 h-4 mr-1" />
            {isUpdating ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
