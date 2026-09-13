// Source: WebRPA@5ccb900e, components/workflow/config-panels/DictAdvancedConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// 字典合并配置
export function DictMergeConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dict1">字典1</Label>
        <VariableInput
          value={(data.dict1 as string) || ''}
          onChange={(v) => onChange('dict1', v)}
          placeholder="输入第一个字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="dict2">字典2</Label>
        <VariableInput
          value={(data.dict2 as string) || ''}
          onChange={(v) => onChange('dict2', v)}
          placeholder="输入第二个字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'merged_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典过滤配置
export function DictFilterConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="condition">过滤条件（Python表达式）</Label>
        <VariableInput
          value={(data.condition as string) || ''}
          onChange={(v) => onChange('condition', v)}
          placeholder="例如：v > 10"
        />
        <p className="text-xs text-muted-foreground">
          使用 k 表示键，v 表示值
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'filtered_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典值映射配置
export function DictMapValuesConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="expression">映射表达式（Python表达式）</Label>
        <VariableInput
          value={(data.expression as string) || ''}
          onChange={(v) => onChange('expression', v)}
          placeholder="例如：v * 2"
        />
        <p className="text-xs text-muted-foreground">
          使用 v 表示字典中的每个值
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'mapped_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典键值反转配置
export function DictInvertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'inverted_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典排序配置
export function DictSortConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="sortBy">排序依据</Label>
        <Select
          id="sortBy"
          value={(data.sortBy as string) || 'key'}
          onChange={(e) => onChange('sortBy', e.target.value)}
        >
          <option value="key">按键排序</option>
          <option value="value">按值排序</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="order">排序方式</Label>
        <Select
          id="order"
          value={(data.order as string) || 'asc'}
          onChange={(e) => onChange('order', e.target.value)}
        >
          <option value="asc">升序</option>
          <option value="desc">降序</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'sorted_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典深拷贝配置
export function DictDeepCopyConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'copied_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典路径获取配置
export function DictGetPathConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="path">路径</Label>
        <VariableInput
          value={(data.path as string) || ''}
          onChange={(v) => onChange('path', v)}
          placeholder="例如：user.profile.name"
        />
        <p className="text-xs text-muted-foreground">
          使用点号分隔嵌套键
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="defaultValue">默认值（可选）</Label>
        <VariableInput
          value={(data.defaultValue as string) || ''}
          onChange={(v) => onChange('defaultValue', v)}
          placeholder="路径不存在时返回的默认值"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'value'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 字典扁平化配置
export function DictFlattenConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dictVariable">嵌套字典变量</Label>
        <VariableInput
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="输入嵌套字典变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="separator">分隔符</Label>
        <VariableInput
          value={(data.separator as string) || '.'}
          onChange={(v) => onChange('separator', v)}
          placeholder="键路径分隔符（默认：.）"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'flattened_dict'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}
