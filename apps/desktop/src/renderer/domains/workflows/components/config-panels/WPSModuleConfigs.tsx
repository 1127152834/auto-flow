// Source: WebRPA@5ccb900e, components/workflow/config-panels/WPSModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { SelectNative as Select } from '../controls/select-native'
import { Textarea } from '../controls/textarea'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

function WpsCommonFields({ data, onChange }: ConfigProps) {
  return (
    <>
      <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-[11.5px] text-red-700 leading-relaxed">
        需先在 <strong>WPS 开放平台 (open.wps.cn)</strong> 创建应用，获取 AK / SK。
        文件ID 与表ID 可在多维表格的分享链接 / API 设置中查看。
      </div>
      <div className="space-y-2">
        <Label>应用 AK（AccessKey）</Label>
        <VariableInput
          value={(data.ak as string) || ''}
          onChange={(v) => onChange('ak', v)}
          placeholder="WPS 开放平台应用 AK"
        />
      </div>
      <div className="space-y-2">
        <Label>应用 SK（SecretKey）</Label>
        <VariableInput
          value={(data.sk as string) || ''}
          onChange={(v) => onChange('sk', v)}
          placeholder="WPS 开放平台应用 SK"
        />
      </div>
      <div className="space-y-2">
        <Label>多维表格文件 ID</Label>
        <VariableInput
          value={(data.fileId as string) || ''}
          onChange={(v) => onChange('fileId', v)}
          placeholder="多维表格文件 ID"
        />
      </div>
      <div className="space-y-2">
        <Label>表 ID（Sheet ID）</Label>
        <VariableInput
          value={(data.sheetId as string) || ''}
          onChange={(v) => onChange('sheetId', v)}
          placeholder="子表 ID"
        />
      </div>
      <div className="space-y-2">
        <Label>接口地址（可选）</Label>
        <VariableInput
          value={(data.baseUrl as string) || ''}
          onChange={(v) => onChange('baseUrl', v)}
          placeholder="留空使用默认 https://openapi.wps.cn"
        />
      </div>
    </>
  )
}

// WPS 多维表格写入配置
export function WpsBitableWriteConfig({ data, onChange }: ConfigProps) {
  const dataSource = (data.dataSource as string) || 'manual'
  return (
    <div className="space-y-4">
      <WpsCommonFields data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>数据来源</Label>
        <Select
          value={dataSource}
          onChange={(e) => onChange('dataSource', e.target.value)}
        >
          <option value="manual">手动输入</option>
          <option value="variable">变量数据</option>
        </Select>
      </div>
      {dataSource === 'manual' ? (
        <div className="space-y-2">
          <Label>记录字段（JSON）</Label>
          <Textarea
            value={(data.fields as string) || ''}
            onChange={(e) => onChange('fields', e.target.value)}
            placeholder='{"字段1": "值1", "字段2": "值2"}'
            rows={6}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <Label>数据变量名</Label>
          <VariableInput
            value={(data.variableName as string) || ''}
            onChange={(v) => onChange('variableName', v)}
            placeholder="data_list（字典或字典列表）"
          />
        </div>
      )}
    </div>
  )
}

// WPS 多维表格读取配置
export function WpsBitableReadConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <WpsCommonFields data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>保存到变量</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'wps_data'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="wps_data"
          isStorageVariable
        />
      </div>
    </div>
  )
}
