// Source: WebRPA@5ccb900e, components/workflow/config-panels/MathListConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import { NumberInput } from '../controls/number-input'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// 列表求和配置
export function ListSumConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'sum'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表平均值配置
export function ListAverageConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'average'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表最大值配置
export function ListMaxConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'max'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表最小值配置
export function ListMinConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'min'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表排序配置
export function ListSortConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
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
          value={(data.resultVariable as string) || 'sorted_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表去重配置
export function ListUniqueConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'unique_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表切片配置
export function ListSliceConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="startIndex">起始索引</Label>
        <VariableInput
          value={(data.startIndex as string) || '0'}
          onChange={(v) => onChange('startIndex', v)}
          placeholder="起始索引（默认：0）"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="endIndex">结束索引</Label>
        <VariableInput
          value={(data.endIndex as string) || ''}
          onChange={(v) => onChange('endIndex', v)}
          placeholder="结束索引（可选，留空表示到末尾）"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'sliced_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学四舍五入配置
export function MathRoundConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="decimals">小数位数</Label>
        <NumberInput
          id="decimals"
          value={(data.decimals as number) ?? 0}
          onChange={(v) => onChange('decimals', v)}
          defaultValue={0}
          min={0}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'rounded'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学进制转换配置
export function MathBaseConvertConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="fromBase">源进制</Label>
        <Select
          id="fromBase"
          value={(data.fromBase as string) || '10'}
          onChange={(e) => onChange('fromBase', e.target.value)}
        >
          <option value="2">二进制</option>
          <option value="8">八进制</option>
          <option value="10">十进制</option>
          <option value="16">十六进制</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="toBase">目标进制</Label>
        <Select
          id="toBase"
          value={(data.toBase as string) || '16'}
          onChange={(e) => onChange('toBase', e.target.value)}
        >
          <option value="2">二进制</option>
          <option value="8">八进制</option>
          <option value="10">十进制</option>
          <option value="16">十六进制</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'converted'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学向下取整配置
export function MathFloorConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'floor'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学取模配置
export function MathModuloConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dividend">被除数</Label>
        <VariableInput
          value={(data.dividend as string) || ''}
          onChange={(v) => onChange('dividend', v)}
          placeholder="输入被除数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="divisor">除数</Label>
        <VariableInput
          value={(data.divisor as string) || ''}
          onChange={(v) => onChange('divisor', v)}
          placeholder="输入除数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'modulo'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学绝对值配置
export function MathAbsConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'abs'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学平方根配置
export function MathSqrtConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'sqrt'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数学幂运算配置
export function MathPowerConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="base">底数</Label>
        <VariableInput
          value={(data.base as string) || ''}
          onChange={(v) => onChange('base', v)}
          placeholder="输入底数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="exponent">指数</Label>
        <VariableInput
          value={(data.exponent as string) || ''}
          onChange={(v) => onChange('exponent', v)}
          placeholder="输入指数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'power'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}
