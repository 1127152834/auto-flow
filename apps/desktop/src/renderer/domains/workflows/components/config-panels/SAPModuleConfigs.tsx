// Source: WebRPA@5ccb900e, components/workflow/config-panels/SAPModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Input } from '../controls/input'
import { SelectNative as Select } from '../controls/select-native'
import { Switch } from '../controls/switch'
import { VariableInput } from '../controls/variable-input'
import { PathInput } from '../controls/path-input'
import type { NodeData } from '../../editor-store'
import { Info } from 'lucide-react'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

function SapTip() {
  return (
    <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <div className="flex items-start gap-2">
        <Info className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-blue-800">
          需要 SAP GUI 已安装并开启脚本支持（事务码 RZ11 → sapgui/user_scripting = TRUE）
        </p>
      </div>
    </div>
  )
}

function SessionVarField({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-2">
      <Label>会话变量</Label>
      <Input
        value={(data.sessionVariable as string) || 'sap_session'}
        onChange={(e) => onChange('sessionVariable', e.target.value)}
        placeholder="sap_session"
      />
    </div>
  )
}

function ElementIdField({ data, onChange, label = '元素ID', placeholder = 'wnd[0]/usr/...' }: ConfigProps & { label?: string; placeholder?: string }) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <VariableInput
        value={(data.elementId as string) || ''}
        onChange={(v) => onChange('elementId', v)}
        placeholder={placeholder}
      />
      <p className="text-xs text-muted-foreground">通过 SAP GUI 脚本录制获取元素路径</p>
    </div>
  )
}

export function SapLoginConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SapTip />
      <div className="space-y-2">
        <Label>连接名称（SAP Logon 快捷方式名）</Label>
        <VariableInput value={(data.connName as string) || ''} onChange={(v) => onChange('connName', v)} placeholder="例如: S4X、ERP_PRD" />
      </div>
      <div className="space-y-2">
        <Label>连接字符串（可选，优先于连接名称）</Label>
        <VariableInput value={(data.connString as string) || ''} onChange={(v) => onChange('connString', v)} placeholder="例如: /H/192.168.1.1/S/3200" />
      </div>
      <div className="space-y-2">
        <Label>用户名</Label>
        <VariableInput value={(data.username as string) || ''} onChange={(v) => onChange('username', v)} placeholder="SAP 用户名" />
      </div>
      <div className="space-y-2">
        <Label>密码</Label>
        <VariableInput value={(data.password as string) || ''} onChange={(v) => onChange('password', v)} placeholder="SAP 密码" />
      </div>
      <div className="space-y-2">
        <Label>客户端（Mandant）</Label>
        <VariableInput value={(data.mandt as string) || '800'} onChange={(v) => onChange('mandt', v)} placeholder="800" />
      </div>
      <div className="space-y-2">
        <Label>登录语言</Label>
        <Select value={(data.language as string) || 'ZH'} onChange={(e) => onChange('language', e.target.value)}>
          <option value="ZH">中文 (ZH)</option>
          <option value="EN">英文 (EN)</option>
          <option value="DE">德文 (DE)</option>
          <option value="JA">日文 (JA)</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>保存会话到变量</Label>
        <Input value={(data.saveToVariable as string) || 'sap_session'} onChange={(e) => onChange('saveToVariable', e.target.value)} placeholder="sap_session" />
      </div>
    </div>
  )
}

export function SapLogoutConfig({ data, onChange }: ConfigProps) {
  return <div className="space-y-4"><SessionVarField data={data} onChange={onChange} /></div>
}

export function SapRunTcodeConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>事务码（T-Code）</Label>
        <VariableInput value={(data.tcode as string) || ''} onChange={(v) => onChange('tcode', v)} placeholder="例如: MM60、ME21N、VA01" />
      </div>
    </div>
  )
}

export function SapSetFieldValueConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="元素ID" placeholder="wnd[0]/usr/txtRSYST-BNAME" />
      <div className="space-y-2">
        <Label>设置值</Label>
        <VariableInput value={(data.value as string) || ''} onChange={(v) => onChange('value', v)} placeholder="要填入的值" />
      </div>
    </div>
  )
}

export function SapGetFieldValueConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="元素ID" placeholder="wnd[0]/usr/txtSOME_FIELD" />
      <div className="space-y-2">
        <Label>保存到变量</Label>
        <Input value={(data.saveToVariable as string) || 'sap_value'} onChange={(e) => onChange('saveToVariable', e.target.value)} placeholder="sap_value" />
      </div>
    </div>
  )
}

export function SapClickButtonConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="按钮ID" placeholder="wnd[0]/tbar[1]/btn[8]" />
    </div>
  )
}

export function SapSendVKeyConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>虚拟键编号</Label>
        <Select value={String((data.vkey as number) ?? 0)} onChange={(e) => onChange('vkey', parseInt(e.target.value))}>
          <option value="0">0 - Enter（回车）</option>
          <option value="1">1 - F1</option>
          <option value="2">2 - F2</option>
          <option value="3">3 - F3（返回）</option>
          <option value="4">4 - F4（帮助）</option>
          <option value="5">5 - F5</option>
          <option value="6">6 - F6</option>
          <option value="7">7 - F7</option>
          <option value="8">8 - F8（执行）</option>
          <option value="11">11 - F11</option>
          <option value="12">12 - F12（取消）</option>
          <option value="21">21 - Ctrl+S（保存）</option>
          <option value="70">70 - Ctrl+F（查找）</option>
        </Select>
        <p className="text-xs text-muted-foreground">常用：0=回车, 3=返回, 8=执行, 12=取消, 21=保存</p>
      </div>
      <div className="space-y-2">
        <Label>窗口索引</Label>
        <Input type="number" min={0} value={(data.windowIndex as number) ?? 0} onChange={(e) => onChange('windowIndex', parseInt(e.target.value) || 0)} />
      </div>
    </div>
  )
}

export function SapGetStatusMessageConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>保存消息到变量</Label>
        <Input value={(data.saveToVariable as string) || 'sap_status_message'} onChange={(e) => onChange('saveToVariable', e.target.value)} placeholder="sap_status_message" />
      </div>
      <div className="space-y-2">
        <Label>保存消息类型到变量（可选）</Label>
        <Input value={(data.saveTypeVariable as string) || ''} onChange={(e) => onChange('saveTypeVariable', e.target.value)} placeholder="sap_status_type" />
        <p className="text-xs text-muted-foreground">类型: S=成功, E=错误, W=警告, I=信息</p>
      </div>
      <div className="space-y-2">
        <Label>窗口索引</Label>
        <Input type="number" min={0} value={(data.windowIndex as number) ?? 0} onChange={(e) => onChange('windowIndex', parseInt(e.target.value) || 0)} />
      </div>
    </div>
  )
}

export function SapGetTitleConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>保存标题到变量</Label>
        <Input value={(data.saveToVariable as string) || 'sap_title'} onChange={(e) => onChange('saveToVariable', e.target.value)} placeholder="sap_title" />
      </div>
      <div className="space-y-2">
        <Label>窗口索引</Label>
        <Input type="number" min={0} value={(data.windowIndex as number) ?? 0} onChange={(e) => onChange('windowIndex', parseInt(e.target.value) || 0)} />
      </div>
    </div>
  )
}

export function SapCloseWarningConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
        自动关闭所有 SAP 警告/提示弹窗
      </div>
      <SessionVarField data={data} onChange={onChange} />
    </div>
  )
}

export function SapSetCheckboxConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="复选框ID" placeholder="wnd[0]/usr/chkSOME_FIELD" />
      <div className="flex items-center justify-between">
        <Label>是否勾选</Label>
        <Switch checked={(data.checked as boolean) ?? true} onCheckedChange={(v) => onChange('checked', v)} />
      </div>
    </div>
  )
}

export function SapSelectComboBoxConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="下拉框ID" placeholder="wnd[0]/usr/cmbSOME_FIELD" />
      <div className="space-y-2">
        <Label>Key值</Label>
        <VariableInput value={(data.key as string) || ''} onChange={(v) => onChange('key', v)} placeholder="下拉框的 key 值" />
      </div>
    </div>
  )
}

export function SapReadGridViewConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="GridView ID" placeholder="wnd[0]/usr/cntlGRID1/shellcont/shell" />
      <div className="space-y-2">
        <Label>保存数据到变量</Label>
        <Input value={(data.saveToVariable as string) || 'sap_table_data'} onChange={(e) => onChange('saveToVariable', e.target.value)} placeholder="sap_table_data" />
        <p className="text-xs text-muted-foreground">数据以列表格式保存，每行为一个字典</p>
      </div>
    </div>
  )
}

export function SapExportGridViewExcelConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="GridView ID" placeholder="wnd[0]/usr/cntlGRID1/shellcont/shell" />
      <div className="space-y-2">
        <Label>保存路径</Label>
        <PathInput
          type="folder"
          value={(data.savePath as string) || 'sap_export.xlsx'}
          onChange={(v) => onChange('savePath', v)}
          placeholder="C:/output/sap_data.xlsx 或选个文件夹"
          title="选择保存目录"
        />
        <p className="text-xs text-muted-foreground">支持 .xlsx 格式，列标题自动使用 SAP 显示名称；选文件夹时会自动追加 sap_export.xlsx 文件名</p>
      </div>
    </div>
  )
}

export function SapSetFocusConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField data={data} onChange={onChange} label="元素ID" placeholder="wnd[0]/usr/txtSOME_FIELD" />
    </div>
  )
}

export function SapSelectTabConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <ElementIdField
        data={data}
        onChange={onChange}
        label="选项卡元素ID"
        placeholder="wnd[0]/usr/tabsTABSTRIP/tabpTAB01"
      />
      <p className="text-xs text-muted-foreground">
        用 SAP 脚本录制器取选项卡（tabp 开头）的元素ID；切换后该选项卡内的控件才能被操作
      </p>
    </div>
  )
}

export function SapMaximizeWindowConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <SessionVarField data={data} onChange={onChange} />
      <div className="space-y-2">
        <Label>窗口索引</Label>
        <Input type="number" min={0} value={(data.windowIndex as number) ?? 0} onChange={(e) => onChange('windowIndex', parseInt(e.target.value) || 0)} />
      </div>
    </div>
  )
}
