// Source: WebRPA@5ccb900e, components/workflow/config-panels/MathAdvancedConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// 数学对数配置
export function MathLogConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="base">底数</Label>
        <Select
          id="base"
          value={(data.base as string) || 'e'}
          onChange={(e) => onChange('base', e.target.value)}
        >
          <option value="e">自然对数 (ln)</option>
          <option value="10">常用对数 (log10)</option>
          <option value="2">二进制对数 (log2)</option>
          <option value="custom">自定义底数</option>
        </Select>
      </div>
      {(data.base as string) === 'custom' && (
        <div className="space-y-2">
          <Label htmlFor="customBase">自定义底数</Label>
          <VariableInput
            value={(data.customBase as string) || ''}
            onChange={(v) => onChange('customBase', v)}
            placeholder="输入底数"
          />
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'log'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 三角函数配置
export function MathTrigConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="function">函数类型</Label>
        <Select
          id="function"
          value={(data.function as string) || 'sin'}
          onChange={(e) => onChange('function', e.target.value)}
        >
          <option value="sin">正弦 (sin)</option>
          <option value="cos">余弦 (cos)</option>
          <option value="tan">正切 (tan)</option>
          <option value="asin">反正弦 (asin)</option>
          <option value="acos">反余弦 (acos)</option>
          <option value="atan">反正切 (atan)</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="unit">角度单位</Label>
        <Select
          id="unit"
          value={(data.unit as string) || 'radian'}
          onChange={(e) => onChange('unit', e.target.value)}
        >
          <option value="radian">弧度</option>
          <option value="degree">角度</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'trig_result'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 指数函数配置
export function MathExpConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">指数</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入指数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'exp'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        计算 e^x，其中 e 是自然常数
      </p>
    </div>
  )
}

// 最大公约数配置
export function MathGcdConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value1">数值1</Label>
        <VariableInput
          value={(data.value1 as string) || ''}
          onChange={(v) => onChange('value1', v)}
          placeholder="输入第一个数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="value2">数值2</Label>
        <VariableInput
          value={(data.value2 as string) || ''}
          onChange={(v) => onChange('value2', v)}
          placeholder="输入第二个数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'gcd'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 最小公倍数配置
export function MathLcmConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value1">数值1</Label>
        <VariableInput
          value={(data.value1 as string) || ''}
          onChange={(v) => onChange('value1', v)}
          placeholder="输入第一个数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="value2">数值2</Label>
        <VariableInput
          value={(data.value2 as string) || ''}
          onChange={(v) => onChange('value2', v)}
          placeholder="输入第二个数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'lcm'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 阶乘配置
export function MathFactorialConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="value">数值</Label>
        <VariableInput
          value={(data.value as string) || ''}
          onChange={(v) => onChange('value', v)}
          placeholder="输入非负整数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'factorial'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 排列数配置
export function MathPermutationConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="n">总数 (n)</Label>
        <VariableInput
          value={(data.n as string) || ''}
          onChange={(v) => onChange('n', v)}
          placeholder="输入总数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="r">选取数 (r)</Label>
        <VariableInput
          value={(data.r as string) || ''}
          onChange={(v) => onChange('r', v)}
          placeholder="输入选取数或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'permutation'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        计算 P(n,r) = n!/(n-r)!
      </p>
    </div>
  )
}

// 百分比计算配置
export function MathPercentageConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="operation">操作类型</Label>
        <Select
          id="operation"
          value={(data.operation as string) || 'of'}
          onChange={(e) => onChange('operation', e.target.value)}
        >
          <option value="of">X是Y的百分之几</option>
          <option value="increase">增加百分比</option>
          <option value="decrease">减少百分比</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="value1">数值1</Label>
        <VariableInput
          value={(data.value1 as string) || ''}
          onChange={(v) => onChange('value1', v)}
          placeholder="输入第一个数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="value2">数值2</Label>
        <VariableInput
          value={(data.value2 as string) || ''}
          onChange={(v) => onChange('value2', v)}
          placeholder="输入第二个数值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'percentage'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}

// 数值限制配置
export function MathClampConfig({ data, onChange }: ConfigProps) {
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
        <Label htmlFor="min">最小值</Label>
        <VariableInput
          value={(data.min as string) || ''}
          onChange={(v) => onChange('min', v)}
          placeholder="输入最小值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="max">最大值</Label>
        <VariableInput
          value={(data.max as string) || ''}
          onChange={(v) => onChange('max', v)}
          placeholder="输入最大值或变量"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'clamped'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        将数值限制在指定范围内
      </p>
    </div>
  )
}

// 高级随机数配置
export function MathRandomAdvancedConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="type">随机类型</Label>
        <Select
          id="type"
          value={(data.type as string) || 'uniform'}
          onChange={(e) => onChange('type', e.target.value)}
        >
          <option value="uniform">均匀分布</option>
          <option value="normal">正态分布</option>
          <option value="exponential">指数分布</option>
        </Select>
      </div>
      {(data.type as string) === 'uniform' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="min">最小值</Label>
            <VariableInput
              value={(data.min as string) || '0'}
              onChange={(v) => onChange('min', v)}
              placeholder="最小值"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max">最大值</Label>
            <VariableInput
              value={(data.max as string) || '100'}
              onChange={(v) => onChange('max', v)}
              placeholder="最大值"
            />
          </div>
        </>
      )}
      {(data.type as string) === 'normal' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="mean">均值 (μ)</Label>
            <VariableInput
              value={(data.mean as string) || '0'}
              onChange={(v) => onChange('mean', v)}
              placeholder="均值"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="stddev">标准差 (σ)</Label>
            <VariableInput
              value={(data.stddev as string) || '1'}
              onChange={(v) => onChange('stddev', v)}
              placeholder="标准差"
            />
          </div>
        </>
      )}
      {(data.type as string) === 'exponential' && (
        <div className="space-y-2">
          <Label htmlFor="lambda">λ参数</Label>
          <VariableInput
            value={(data.lambda as string) || '1'}
            onChange={(v) => onChange('lambda', v)}
            placeholder="λ参数"
          />
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量</Label>
        <VariableInput
          value={(data.resultVariable as string) || 'random'}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存结果的变量名"
        />
      </div>
    </div>
  )
}
