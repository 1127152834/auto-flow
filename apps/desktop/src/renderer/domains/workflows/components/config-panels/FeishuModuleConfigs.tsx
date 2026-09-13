// Source: WebRPA@5ccb900e, components/workflow/config-panels/FeishuModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../controls/select'
import { Textarea } from '../controls/textarea'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { NumberInput } from '../controls/number-input'
import { useGlobalConfigStore } from '../../hooks/stores/globalConfigStore'
import { useEffect } from 'react'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// 飞书多维表格写入配置
export function FeishuBitableWriteConfig({ data, onChange }: ConfigProps) {
  const { config } = useGlobalConfigStore()

  useEffect(() => {
    if (!data.appId && config.feishu?.appId) {
      onChange('appId', config.feishu.appId)
    }
    if (!data.appSecret && config.feishu?.appSecret) {
      onChange('appSecret', config.feishu.appSecret)
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>App ID</Label>
        <VariableInput
          value={(data.appId as string) || ''}
          onChange={(v) => onChange('appId', v)}
          placeholder="请输入飞书应用ID"
        />
      </div>

      <div className="space-y-2">
        <Label>App Secret</Label>
        <VariableInput
          value={(data.appSecret as string) || ''}
          onChange={(v) => onChange('appSecret', v)}
          placeholder="请输入飞书应用密钥"
        />
      </div>

      <div className="space-y-2">
        <Label>多维表格Token</Label>
        <VariableInput
          value={(data.appToken as string) || ''}
          onChange={(v) => onChange('appToken', v)}
          placeholder="请输入多维表格Token"
        />
      </div>

      <div className="space-y-2">
        <Label>数据表ID</Label>
        <VariableInput
          value={(data.tableId as string) || ''}
          onChange={(v) => onChange('tableId', v)}
          placeholder="请输入数据表ID"
        />
      </div>

      <div className="space-y-2">
        <Label>数据来源</Label>
        <Select
          value={(data.dataSource as string) || 'manual'}
          onValueChange={(v) => onChange('dataSource', v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择数据来源" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">手动输入</SelectItem>
            <SelectItem value="variable">变量数据</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {((data.dataSource as string) || 'manual') === 'manual' ? (
        <div className="space-y-2">
          <Label>记录数据（JSON格式）</Label>
          <Textarea
            value={(data.recordData as string) || ''}
            onChange={(e) => onChange('recordData', e.target.value)}
            placeholder='{"字段1": "值1", "字段2": "值2"}'
            rows={6}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <Label>数据变量名</Label>
          <VariableInput
            value={(data.dataVariable as string) || ''}
            onChange={(v) => onChange('dataVariable', v)}
            placeholder="data_list"
          />
        </div>
      )}
    </div>
  )
}

// 飞书多维表格读取配置
export function FeishuBitableReadConfig({ data, onChange }: ConfigProps) {
  const { config } = useGlobalConfigStore()

  useEffect(() => {
    if (!data.appId && config.feishu?.appId) {
      onChange('appId', config.feishu.appId)
    }
    if (!data.appSecret && config.feishu?.appSecret) {
      onChange('appSecret', config.feishu.appSecret)
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>App ID</Label>
        <VariableInput
          value={(data.appId as string) || ''}
          onChange={(v) => onChange('appId', v)}
          placeholder="请输入飞书应用ID"
        />
      </div>

      <div className="space-y-2">
        <Label>App Secret</Label>
        <VariableInput
          value={(data.appSecret as string) || ''}
          onChange={(v) => onChange('appSecret', v)}
          placeholder="请输入飞书应用密钥"
        />
      </div>

      <div className="space-y-2">
        <Label>多维表格Token</Label>
        <VariableInput
          value={(data.appToken as string) || ''}
          onChange={(v) => onChange('appToken', v)}
          placeholder="请输入多维表格Token"
        />
      </div>

      <div className="space-y-2">
        <Label>数据表ID</Label>
        <VariableInput
          value={(data.tableId as string) || ''}
          onChange={(v) => onChange('tableId', v)}
          placeholder="请输入数据表ID"
        />
      </div>

      <div className="space-y-2">
        <Label>每页记录数</Label>
        <NumberInput
          value={(data.pageSize as number) || 100}
          onChange={(v) => onChange('pageSize', v)}
          defaultValue={100}
          min={1}
          max={500}
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'feishu_records'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="feishu_records"
        />
      </div>
    </div>
  )
}

// 飞书电子表格写入配置
export function FeishuSheetWriteConfig({ data, onChange }: ConfigProps) {
  const { config } = useGlobalConfigStore()

  useEffect(() => {
    if (!data.appId && config.feishu?.appId) {
      onChange('appId', config.feishu.appId)
    }
    if (!data.appSecret && config.feishu?.appSecret) {
      onChange('appSecret', config.feishu.appSecret)
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>App ID</Label>
        <VariableInput
          value={(data.appId as string) || ''}
          onChange={(v) => onChange('appId', v)}
          placeholder="请输入飞书应用ID"
        />
      </div>

      <div className="space-y-2">
        <Label>App Secret</Label>
        <VariableInput
          value={(data.appSecret as string) || ''}
          onChange={(v) => onChange('appSecret', v)}
          placeholder="请输入飞书应用密钥"
        />
      </div>

      <div className="space-y-2">
        <Label>电子表格Token</Label>
        <VariableInput
          value={(data.spreadsheetToken as string) || ''}
          onChange={(v) => onChange('spreadsheetToken', v)}
          placeholder="请输入电子表格Token"
        />
      </div>

      <div className="space-y-2">
        <Label>工作表ID</Label>
        <VariableInput
          value={(data.sheetId as string) || ''}
          onChange={(v) => onChange('sheetId', v)}
          placeholder="请输入工作表ID"
        />
      </div>

      <div className="space-y-2">
        <Label>起始单元格</Label>
        <VariableInput
          value={(data.startCell as string) || 'A1'}
          onChange={(v) => onChange('startCell', v)}
          placeholder="A1"
        />
      </div>

      <div className="space-y-2">
        <Label>数据来源</Label>
        <Select
          value={(data.dataSource as string) || 'manual'}
          onValueChange={(v) => onChange('dataSource', v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择数据来源" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">手动输入</SelectItem>
            <SelectItem value="variable">变量数据</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {((data.dataSource as string) || 'manual') === 'manual' ? (
        <div className="space-y-2">
          <Label>数据内容（JSON格式二维数组）</Label>
          <Textarea
            value={(data.values as string) || ''}
            onChange={(e) => onChange('values', e.target.value)}
            placeholder='[["值1", "值2"], ["值3", "值4"]]'
            rows={6}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <Label>数据变量名</Label>
          <VariableInput
            value={(data.dataVariable as string) || ''}
            onChange={(v) => onChange('dataVariable', v)}
            placeholder="data_list"
          />
        </div>
      )}
    </div>
  )
}

// 飞书电子表格读取配置
export function FeishuSheetReadConfig({ data, onChange }: ConfigProps) {
  const { config } = useGlobalConfigStore()

  useEffect(() => {
    if (!data.appId && config.feishu?.appId) {
      onChange('appId', config.feishu.appId)
    }
    if (!data.appSecret && config.feishu?.appSecret) {
      onChange('appSecret', config.feishu.appSecret)
    }
  }, [])

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>App ID</Label>
        <VariableInput
          value={(data.appId as string) || ''}
          onChange={(v) => onChange('appId', v)}
          placeholder="请输入飞书应用ID"
        />
      </div>

      <div className="space-y-2">
        <Label>App Secret</Label>
        <VariableInput
          value={(data.appSecret as string) || ''}
          onChange={(v) => onChange('appSecret', v)}
          placeholder="请输入飞书应用密钥"
        />
      </div>

      <div className="space-y-2">
        <Label>电子表格Token</Label>
        <VariableInput
          value={(data.spreadsheetToken as string) || ''}
          onChange={(v) => onChange('spreadsheetToken', v)}
          placeholder="请输入电子表格Token"
        />
      </div>

      <div className="space-y-2">
        <Label>工作表ID</Label>
        <VariableInput
          value={(data.sheetId as string) || ''}
          onChange={(v) => onChange('sheetId', v)}
          placeholder="请输入工作表ID"
        />
      </div>

      <div className="space-y-2">
        <Label>读取范围</Label>
        <VariableInput
          value={(data.range as string) || 'A1:Z1000'}
          onChange={(v) => onChange('range', v)}
          placeholder="A1:Z1000"
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'feishu_data'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="feishu_data"
        />
      </div>
    </div>
  )
}
