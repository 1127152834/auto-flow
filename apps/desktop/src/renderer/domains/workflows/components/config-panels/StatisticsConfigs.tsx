// Source: WebRPA@5ccb900e, components/workflow/config-panels/StatisticsConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import { NumberInput } from '../controls/number-input'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// 中位数配置
export function StatMedianConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'median'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 众数配置
export function StatModeConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'mode'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 方差配置
export function StatVarianceConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'variance'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 标准差配置
export function StatStdevConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'stdev'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 百分位数配置
export function StatPercentileConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="percentile">百分位</Label>
        <NumberInput
          id="percentile"
          value={(data.percentile as number) ?? 50}
          onChange={(v) => onChange('percentile', v)}
          defaultValue={50}
          min={0}
          max={100}
        />
        <p className="text-xs text-muted-foreground">
          0-100之间的数值，50表示中位数
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'percentile'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 归一化配置
export function StatNormalizeConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="method">归一化方法</Label>
        <Select
          id="method"
          value={(data.method as string) || 'minmax'}
          onChange={(e) => onChange('method', e.target.value)}
        >
          <option value="minmax">Min-Max归一化 (0-1)</option>
          <option value="custom">自定义范围</option>
        </Select>
      </div>
      {(data.method as string) === 'custom' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="newMin">新最小值</Label>
            <VariableInput
              value={(data.newMin as string) || '0'}
              onChange={(v) => onChange('newMin', v)}
              placeholder="归一化后的最小值"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="newMax">新最大值</Label>
            <VariableInput
              value={(data.newMax as string) || '1'}
              onChange={(v) => onChange('newMax', v)}
              placeholder="归一化后的最大值"
            />
          </div>
        </>
      )}
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'normalized'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 标准化配置
export function StatStandardizeConfig({ data, onChange }: ConfigProps) {
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
          value={(data.resultVariable as string) || 'standardized'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Z-score标准化：(x - μ) / σ
      </p>
    </div>
  )
}

// CSV解析配置
export function CsvParseConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="csvContent">CSV内容</Label>
        <VariableInput
          value={(data.csvContent as string) || ''}
          onChange={(v) => onChange('csvContent', v)}
          placeholder="输入CSV内容或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="delimiter">分隔符</Label>
        <VariableInput
          value={(data.delimiter as string) || ','}
          onChange={(v) => onChange('delimiter', v)}
          placeholder="分隔符（默认：,）"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="hasHeader">包含表头</Label>
        <Select
          id="hasHeader"
          value={(data.hasHeader as string) || 'true'}
          onChange={(e) => onChange('hasHeader', e.target.value)}
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'csv_data'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// CSV生成配置
export function CsvGenerateConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="dataVariable">数据变量</Label>
        <VariableInput
          value={(data.dataVariable as string) || ''}
          onChange={(v) => onChange('dataVariable', v)}
          placeholder="输入数据列表变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="delimiter">分隔符</Label>
        <VariableInput
          value={(data.delimiter as string) || ','}
          onChange={(v) => onChange('delimiter', v)}
          placeholder="分隔符（默认：,）"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="includeHeader">包含表头</Label>
        <Select
          id="includeHeader"
          value={(data.includeHeader as string) || 'true'}
          onChange={(e) => onChange('includeHeader', e.target.value)}
        >
          <option value="true">是</option>
          <option value="false">否</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'csv_string'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 列表转字符串高级配置
export function ListToStringAdvancedConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="separator">分隔符</Label>
        <VariableInput
          value={(data.separator as string) || ', '}
          onChange={(v) => onChange('separator', v)}
          placeholder="元素之间的分隔符"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="prefix">前缀（可选）</Label>
        <VariableInput
          value={(data.prefix as string) || ''}
          onChange={(v) => onChange('prefix', v)}
          placeholder="字符串前缀"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="suffix">后缀（可选）</Label>
        <VariableInput
          value={(data.suffix as string) || ''}
          onChange={(v) => onChange('suffix', v)}
          placeholder="字符串后缀"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'string'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}
