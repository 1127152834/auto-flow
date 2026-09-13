// Source: WebRPA@5ccb900e, components/workflow/config-panels/ListAdvancedConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { NumberInput } from '../controls/number-input'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// 列表反转配置
export function ListReverseConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'reversed_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表查找配置
export function ListFindConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="searchValue">查找值</Label>
        <VariableInput
          value={(data.searchValue as string) || ''}
          onChange={(v) => onChange('searchValue', v)}
          placeholder="输入要查找的值"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量（索引）</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'index'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存索引的变量名"
        />
      </div>
    </div>
  )
}

// 列表计数配置
export function ListCountConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="searchValue">计数值</Label>
        <VariableInput
          value={(data.searchValue as string) || ''}
          onChange={(v) => onChange('searchValue', v)}
          placeholder="输入要计数的值"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'count'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存计数的变量名"
        />
      </div>
    </div>
  )
}

// 列表过滤配置
export function ListFilterConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="condition">过滤条件（Python表达式）</Label>
        <VariableInput
          value={(data.condition as string) || ''}
          onChange={(v) => onChange('condition', v)}
          placeholder="例如：x > 10"
        />
        <p className="text-xs text-muted-foreground">
          使用 x 表示列表中的每个元素
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'filtered_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表映射配置
export function ListMapConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="expression">映射表达式（Python表达式）</Label>
        <VariableInput
          value={(data.expression as string) || ''}
          onChange={(v) => onChange('expression', v)}
          placeholder="例如：x * 2"
        />
        <p className="text-xs text-muted-foreground">
          使用 x 表示列表中的每个元素
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'mapped_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表合并配置
export function ListMergeConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="list1">列表1</Label>
        <VariableInput
          value={(data.list1 as string) || ''}
          onChange={(v) => onChange('list1', v)}
          placeholder="输入第一个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="list2">列表2</Label>
        <VariableInput
          value={(data.list2 as string) || ''}
          onChange={(v) => onChange('list2', v)}
          placeholder="输入第二个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'merged_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表扁平化配置
export function ListFlattenConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="listVariable">嵌套列表变量</Label>
        <VariableInput
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="输入嵌套列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="depth">扁平化深度</Label>
        <NumberInput
          id="depth"
          value={(data.depth as number) ?? 1}
          onChange={(v) => onChange('depth', v)}
          defaultValue={1}
          min={1}
        />
        <p className="text-xs text-muted-foreground">
          1表示只扁平化一层，-1表示完全扁平化
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'flattened_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表分块配置
export function ListChunkConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="chunkSize">块大小</Label>
        <VariableInput
          value={(data.chunkSize as string) || ''}
          onChange={(v) => onChange('chunkSize', v)}
          placeholder="每块的元素数量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'chunked_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表移除空值配置
export function ListRemoveEmptyConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'cleaned_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表交集配置
export function ListIntersectionConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="list1">列表1</Label>
        <VariableInput
          value={(data.list1 as string) || ''}
          onChange={(v) => onChange('list1', v)}
          placeholder="输入第一个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="list2">列表2</Label>
        <VariableInput
          value={(data.list2 as string) || ''}
          onChange={(v) => onChange('list2', v)}
          placeholder="输入第二个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'intersection'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表并集配置
export function ListUnionConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="list1">列表1</Label>
        <VariableInput
          value={(data.list1 as string) || ''}
          onChange={(v) => onChange('list1', v)}
          placeholder="输入第一个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="list2">列表2</Label>
        <VariableInput
          value={(data.list2 as string) || ''}
          onChange={(v) => onChange('list2', v)}
          placeholder="输入第二个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'union'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表差集配置
export function ListDifferenceConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="list1">列表1</Label>
        <VariableInput
          value={(data.list1 as string) || ''}
          onChange={(v) => onChange('list1', v)}
          placeholder="输入第一个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="list2">列表2</Label>
        <VariableInput
          value={(data.list2 as string) || ''}
          onChange={(v) => onChange('list2', v)}
          placeholder="输入第二个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'difference'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表笛卡尔积配置
export function ListCartesianProductConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="list1">列表1</Label>
        <VariableInput
          value={(data.list1 as string) || ''}
          onChange={(v) => onChange('list1', v)}
          placeholder="输入第一个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="list2">列表2</Label>
        <VariableInput
          value={(data.list2 as string) || ''}
          onChange={(v) => onChange('list2', v)}
          placeholder="输入第二个列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'cartesian_product'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表随机打乱配置
export function ListShuffleConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'shuffled_list'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表随机抽样配置
export function ListSampleConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="sampleSize">抽样数量</Label>
        <VariableInput
          value={(data.sampleSize as string) || ''}
          onChange={(v) => onChange('sampleSize', v)}
          placeholder="要抽取的元素数量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'sample'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}
