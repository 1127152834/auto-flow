// Source: WebRPA@5ccb900e, components/workflow/config-panels/SimilarSelectorDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState } from 'react'
import { Button } from '../controls/button'
import { Label } from '../controls/label'
import { VariableNameInput } from '../controls/variable-name-input'
import { X, CheckCircle2 } from 'lucide-react'

interface SimilarSelectorDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (variableName: string) => void
  pattern: string
  count: number
  minIndex: number
  maxIndex: number
}

export function SimilarSelectorDialog({ 
  isOpen, 
  onClose, 
  onConfirm, 
  pattern, 
  count, 
  minIndex, 
  maxIndex 
}: SimilarSelectorDialogProps) {
  const [variableName, setVariableName] = useState('index')
  
  if (!isOpen) return null
  
  const displayPattern = pattern.replace('{index}', `{${variableName}}`)
  
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 animate-fade-in" style={{ zIndex: 2147483640 }}>
      <div className="bg-white text-black border border-gray-200 rounded-xl shadow-2xl w-full max-w-lg p-4 overflow-hidden animate-scale-in">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">相似元素选择</h3>
          <Button variant="tonal-danger" size="icon" onClick={onClose} title="关闭">

            <X className="w-4 h-4" />

          </Button>
        </div>
        <div className="space-y-4">
          <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-sm text-green-800 inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-green-600" />
              找到 <strong>{count}</strong> 个相似元素 (索引 {minIndex} - {maxIndex})
            </p>
          </div>
          
          <div className="space-y-2">
            <Label className="text-gray-700">为索引变量命名</Label>
            <VariableNameInput
              value={variableName}
              onChange={(v) => setVariableName(v)}
              placeholder="index"
              isStorageVariable={true}
            />
            <p className="text-xs text-gray-500">
              变量名将用于循环遍历，如 <code className="bg-gray-100 px-1 rounded">{'{' + variableName + '}'}</code>
            </p>
          </div>
          
          <div className="space-y-2">
            <Label className="text-gray-700">生成的选择器模式</Label>
            <div className="p-2 bg-gray-100 rounded text-xs font-mono break-all">
              {displayPattern}
            </div>
            <p className="text-xs text-gray-500">
              选择器中的 <code className="bg-gray-100 px-1 rounded">{'{' + variableName + '}'}</code> 会在运行时被替换为实际索引值
            </p>
          </div>
          
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-xs text-blue-800">
              使用方法：在"循环执行"模块中设置循环范围 {minIndex} 到 {maxIndex}，
              索引变量名设为 <code className="bg-blue-100 px-1 rounded">{variableName}</code>，
              然后在后续模块中使用此选择器即可遍历所有相似元素。
            </p>
          </div>
          
          <div className="flex justify-end gap-2">
            <Button variant="outline" className="border-gray-300 text-gray-700 hover:bg-gray-100" onClick={onClose}>
              取消
            </Button>
            <Button 
              className="bg-blue-600 text-white hover:bg-blue-700" 
              onClick={() => onConfirm(variableName)}
              disabled={!variableName}
            >
              确认使用
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
