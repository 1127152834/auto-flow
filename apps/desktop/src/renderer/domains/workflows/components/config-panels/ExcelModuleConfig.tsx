// Source: WebRPA@5ccb900e, components/workflow/config-panels/ExcelModuleConfig.tsx; see SOURCE.md for license and adaptation boundaries.
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { NumberInput } from '../controls/number-input'
import { SelectNative as Select } from '../controls/select-native'
import { Switch } from '../controls/switch'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { PathInput } from '../controls/path-input'

/** 字段定义 */
interface FieldDef {
  key: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'switch' | 'path' | 'varname'
  placeholder?: string
  hint?: string
  options?: Array<{ value: string; label: string }>
  default?: unknown
  /** 仅当某字段等于某值时显示 */
  showWhen?: { key: string; equals: string | string[] }
}

interface ExcelModuleConfigProps {
  moduleType: string
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

const XLSX_TYPES: Array<[string, string]> = [['Excel 文件', '*.xlsx'], ['所有文件', '*.*']]
const CSV_TYPES: Array<[string, string]> = [['CSV 文件', '*.csv'], ['所有文件', '*.*']]

// 通用字段
const F_FILE: FieldDef = { key: 'filePath', label: 'Excel 文件路径', type: 'path', placeholder: '如 D:\\data.xlsx，支持 {变量名}' }
const F_SHEET: FieldDef = { key: 'sheetName', label: '工作表名（留空取活动表）', type: 'text', placeholder: '如 Sheet1，支持 {变量名}' }
// 读取类模块：决定读单元格的计算结果还是公式本身
const F_READ_CONTENT: FieldDef = {
  key: 'readContent',
  label: '读取内容',
  type: 'select',
  default: 'value',
  options: [
    { value: 'value', label: '值（单元格的计算结果）' },
    { value: 'formula', label: '公式（如 =SUM(A1:A2)）' },
  ],
  hint: '默认读值。公式单元格若没有缓存计算值（文件从未用 Excel 打开保存过），会自动返回公式文本并在执行结果中提示。',
}

export function ExcelModuleConfig({ moduleType, data, onChange }: ExcelModuleConfigProps) {
  const fields = EXCEL_FIELD_SCHEMAS[moduleType]

  if (!fields) {
    return <p className="text-sm text-muted-foreground">该 Excel 模块暂无可配置项</p>
  }

  const visible = (f: FieldDef) => {
    if (!f.showWhen) return true
    const cur = String(data[f.showWhen.key] ?? f.default ?? '')
    const eq = f.showWhen.equals
    return Array.isArray(eq) ? eq.includes(cur) : cur === eq
  }

  return (
    <div className="space-y-3">
      {fields.filter(visible).map((f) => (
        <div key={f.key} className="space-y-1.5">
          {f.type !== 'switch' && <Label htmlFor={f.key}>{f.label}</Label>}
          {renderField(f, data, onChange)}
          {f.hint && <p className="text-xs text-muted-foreground">{f.hint}</p>}
        </div>
      ))}
    </div>
  )
}

function renderField(f: FieldDef, data: NodeData, onChange: (k: string, v: unknown) => void) {
  const val = data[f.key]
  switch (f.type) {
    case 'path':
      return (
        <PathInput
          value={(val as string) || ''}
          onChange={(v) => onChange(f.key, v)}
          type="file"
          placeholder={f.placeholder}
          fileTypes={f.key === 'csvPath' ? CSV_TYPES : XLSX_TYPES}
        />
      )
    case 'textarea':
      return (
        <VariableInput
          multiline
          rows={4}
          value={(val as string) || ''}
          onChange={(v) => onChange(f.key, v)}
          placeholder={f.placeholder}
        />
      )
    case 'number':
      return (
        <NumberInput
          id={f.key}
          value={(val as number) ?? (f.default as number) ?? 0}
          onChange={(v) => onChange(f.key, v)}
          defaultValue={(f.default as number) ?? 0}
        />
      )
    case 'select':
      return (
        <Select
          id={f.key}
          value={(val as string) ?? (f.default as string) ?? ''}
          onChange={(e) => onChange(f.key, e.target.value)}
        >
          {(f.options || []).map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </Select>
      )
    case 'switch':
      return (
        <div className="flex items-center justify-between">
          <Label htmlFor={f.key} className="cursor-pointer">{f.label}</Label>
          <Switch
            id={f.key}
            checked={val === undefined ? Boolean(f.default) : Boolean(val)}
            onCheckedChange={(v) => onChange(f.key, v)}
          />
        </div>
      )
    case 'varname':
      return (
        <VariableNameInput
          value={(val as string) || ''}
          onChange={(v) => onChange(f.key, v)}
          placeholder={f.placeholder || '变量名'}
          isStorageVariable={true}
        />
      )
    default:
      return (
        <VariableInput
          value={(val as string) || ''}
          onChange={(v) => onChange(f.key, v)}
          placeholder={f.placeholder}
        />
      )
  }
}


/** 各 Excel 模块的字段表单定义 */
const EXCEL_FIELD_SCHEMAS: Record<string, FieldDef[]> = {
  // ===== 工作簿 / 工作表 =====
  excel_create: [
    F_FILE,
    { key: 'sheetNames', label: '工作表名（逗号分隔）', type: 'text', placeholder: 'Sheet1,Sheet2', default: 'Sheet1' },
    { key: 'overwrite', label: '已存在时覆盖', type: 'switch', default: false },
  ],
  excel_add_sheet: [F_FILE, { key: 'sheetName', label: '新工作表名', type: 'text', placeholder: '新工作表' }],
  excel_delete_sheet: [F_FILE, { key: 'sheetName', label: '要删除的工作表名', type: 'text', placeholder: '如 Sheet2' }],
  excel_rename_sheet: [
    F_FILE,
    { key: 'oldName', label: '原工作表名', type: 'text', placeholder: '留空取活动表' },
    { key: 'newName', label: '新工作表名', type: 'text' },
  ],
  excel_list_sheets: [F_FILE, { key: 'resultVariable', label: '存储到变量', type: 'varname', placeholder: 'sheet_list' }],
  excel_copy_sheet: [
    F_FILE, F_SHEET,
    { key: 'newName', label: '副本名称（留空自动命名）', type: 'text' },
  ],
  excel_move_sheet: [
    F_FILE, F_SHEET,
    { key: 'offset', label: '移动偏移量（正右负左）', type: 'number', default: 1 },
  ],
  excel_set_tab_color: [
    F_FILE, F_SHEET,
    { key: 'color', label: '标签颜色（十六进制，留空清除）', type: 'text', placeholder: '如 FF0000' },
  ],
  excel_clear_sheet: [F_FILE, F_SHEET],
  excel_get_info: [F_FILE, F_SHEET, { key: 'resultVariable', label: '存储到变量', type: 'varname', placeholder: 'sheet_info' }],

  // ===== 单元格 / 区域 =====
  excel_write_cell: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '单元格地址', type: 'text', placeholder: '如 A1' },
    { key: 'value', label: '写入值', type: 'text', placeholder: '支持 {变量名}' },
  ],
  excel_read_cell: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '单元格地址', type: 'text', placeholder: '如 A1' },
    F_READ_CONTENT,
    { key: 'resultVariable', label: '存储到变量', type: 'varname', placeholder: 'cell_value' },
  ],
  excel_write_range: [
    F_FILE, F_SHEET,
    { key: 'startCell', label: '起始单元格', type: 'text', placeholder: 'A1', default: 'A1' },
    { key: 'data', label: '二维数组数据(JSON)', type: 'textarea', placeholder: '[[1,2],[3,4]]' },
  ],
  excel_read_range: [
    F_FILE, F_SHEET,
    { key: 'range', label: '区域', type: 'text', placeholder: '如 A1:C10' },
    F_READ_CONTENT,
    { key: 'resultVariable', label: '存储到变量', type: 'varname', placeholder: 'range_data' },
  ],
  excel_append_row: [
    F_FILE, F_SHEET,
    { key: 'rowData', label: '行数据(JSON 数组)', type: 'textarea', placeholder: '["张三",18,"北京"]' },
  ],
  excel_copy_range: [
    F_FILE, F_SHEET,
    { key: 'range', label: '源区域', type: 'text', placeholder: '如 A1:C10' },
    { key: 'destSheet', label: '目标工作表（留空同表）', type: 'text' },
    { key: 'destCell', label: '目标起始单元格', type: 'text', placeholder: '如 E1' },
  ],
  excel_clear_range: [
    F_FILE, F_SHEET,
    { key: 'range', label: '要清空的区域', type: 'text', placeholder: '如 A1:C10' },
  ],
  excel_find_replace: [
    F_FILE, F_SHEET,
    { key: 'find', label: '查找内容', type: 'text' },
    { key: 'replace', label: '替换为', type: 'text' },
    { key: 'matchEntire', label: '整单元格匹配', type: 'switch', default: false },
  ],
}


// ===== 行列 / 公式 / 样式 =====
Object.assign(EXCEL_FIELD_SCHEMAS, {
  excel_insert_rows: [
    F_FILE, F_SHEET,
    { key: 'rowIndex', label: '在第几行前插入', type: 'number', default: 1 },
    { key: 'count', label: '插入行数', type: 'number', default: 1 },
  ],
  excel_delete_rows: [
    F_FILE, F_SHEET,
    { key: 'rowIndex', label: '起始行号', type: 'number', default: 1 },
    { key: 'count', label: '删除行数', type: 'number', default: 1 },
  ],
  excel_insert_cols: [
    F_FILE, F_SHEET,
    { key: 'colIndex', label: '在第几列前插入', type: 'number', default: 1 },
    { key: 'count', label: '插入列数', type: 'number', default: 1 },
  ],
  excel_delete_cols: [
    F_FILE, F_SHEET,
    { key: 'colIndex', label: '起始列号', type: 'number', default: 1 },
    { key: 'count', label: '删除列数', type: 'number', default: 1 },
  ],
  excel_hide: [
    F_FILE, F_SHEET,
    { key: 'target', label: '对象', type: 'select', default: 'column', options: [{ value: 'column', label: '列' }, { value: 'row', label: '行' }] },
    { key: 'key', label: '列字母或行号（支持范围）', type: 'text', placeholder: '如 A、A:C、1、1:5' },
    { key: 'hidden', label: '隐藏（关闭则显示）', type: 'switch', default: true },
  ],
  excel_set_size: [
    F_FILE, F_SHEET,
    { key: 'target', label: '对象', type: 'select', default: 'column', options: [{ value: 'column', label: '列宽' }, { value: 'row', label: '行高' }] },
    { key: 'key', label: '列字母或行号', type: 'text', placeholder: '如 A 或 1' },
    { key: 'size', label: '尺寸', type: 'number', default: 20 },
  ],
  excel_set_formula: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '单元格', type: 'text', placeholder: '如 B10' },
    { key: 'formula', label: '公式', type: 'text', placeholder: '如 =SUM(B1:B9)' },
  ],
  excel_read_formula: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '单元格', type: 'text', placeholder: '如 B10' },
    { key: 'mode', label: '读取内容', type: 'select', default: 'value', options: [{ value: 'value', label: '计算值' }, { value: 'formula', label: '公式文本' }] },
    { key: 'resultVariable', label: '存储到变量', type: 'varname', placeholder: 'cell_value' },
  ],
  excel_merge_cells: [
    F_FILE, F_SHEET,
    { key: 'range', label: '区域', type: 'text', placeholder: '如 A1:C1' },
    { key: 'unmerge', label: '取消合并', type: 'switch', default: false },
  ],
  excel_freeze_panes: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '冻结到单元格左上', type: 'text', placeholder: 'A2 冻结首行；None 取消', default: 'A2' },
  ],
  excel_set_style: [
    F_FILE, F_SHEET,
    { key: 'range', label: '区域', type: 'text', placeholder: '如 A1 或 A1:C3' },
    { key: 'bold', label: '加粗', type: 'switch', default: false },
    { key: 'italic', label: '斜体', type: 'switch', default: false },
    { key: 'fontSize', label: '字号（0=不改）', type: 'number', default: 0 },
    { key: 'fontName', label: '字体', type: 'text', placeholder: '如 微软雅黑' },
    { key: 'fontColor', label: '字体颜色（十六进制）', type: 'text', placeholder: '如 FF0000' },
    { key: 'bgColor', label: '背景色（十六进制）', type: 'text', placeholder: '如 FFFF00' },
    { key: 'alignH', label: '水平对齐', type: 'select', default: '', options: [{ value: '', label: '默认' }, { value: 'left', label: '左' }, { value: 'center', label: '居中' }, { value: 'right', label: '右' }] },
    { key: 'alignV', label: '垂直对齐', type: 'select', default: '', options: [{ value: '', label: '默认' }, { value: 'top', label: '上' }, { value: 'center', label: '居中' }, { value: 'bottom', label: '下' }] },
    { key: 'border', label: '加边框', type: 'switch', default: false },
  ],
  excel_set_border: [
    F_FILE, F_SHEET,
    { key: 'range', label: '区域', type: 'text', placeholder: '如 A1:C5' },
    { key: 'style', label: '线型', type: 'select', default: 'thin', options: [{ value: 'thin', label: '细' }, { value: 'medium', label: '中' }, { value: 'thick', label: '粗' }, { value: 'dashed', label: '虚线' }, { value: 'dotted', label: '点线' }, { value: 'double', label: '双线' }] },
    { key: 'color', label: '颜色（十六进制）', type: 'text', placeholder: '如 000000', default: '000000' },
    { key: 'scope', label: '范围', type: 'select', default: 'all', options: [{ value: 'all', label: '全部边框' }, { value: 'outline', label: '仅外框' }] },
  ],
  excel_number_format: [
    F_FILE, F_SHEET,
    { key: 'range', label: '区域', type: 'text', placeholder: '如 B2:B100' },
    { key: 'preset', label: '格式预设', type: 'select', default: 'general', options: [
      { value: 'general', label: '常规' }, { value: 'integer', label: '整数' }, { value: 'decimal2', label: '两位小数' },
      { value: 'thousands', label: '千分位' }, { value: 'thousands2', label: '千分位两位小数' }, { value: 'percent', label: '百分比' },
      { value: 'percent2', label: '百分比两位小数' }, { value: 'currency_cny', label: '人民币' }, { value: 'currency_usd', label: '美元' },
      { value: 'date', label: '日期' }, { value: 'datetime', label: '日期时间' }, { value: 'time', label: '时间' },
      { value: 'text', label: '文本' }, { value: 'scientific', label: '科学计数' },
    ] },
    { key: 'customFormat', label: '自定义格式（优先）', type: 'text', placeholder: '如 0.00"元"，留空用预设' },
  ],
})


// ===== 超链接 / 批注 / 图片 / 图表 / 验证 / 条件格式 =====
Object.assign(EXCEL_FIELD_SCHEMAS, {
  excel_set_hyperlink: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '单元格', type: 'text', placeholder: '如 A1' },
    { key: 'link', label: '链接地址', type: 'text', placeholder: 'https://... 或文件路径' },
    { key: 'display', label: '显示文字（可选）', type: 'text' },
  ],
  excel_set_comment: [
    F_FILE, F_SHEET,
    { key: 'cell', label: '单元格', type: 'text', placeholder: '如 A1' },
    { key: 'text', label: '批注内容（留空清除）', type: 'textarea' },
    { key: 'author', label: '作者', type: 'text', placeholder: 'WebRPA' },
  ],
  excel_add_image: [
    F_FILE, F_SHEET,
    { key: 'imagePath', label: '图片路径', type: 'path', placeholder: '如 D:\\logo.png' },
    { key: 'anchor', label: '锚点单元格', type: 'text', placeholder: 'A1', default: 'A1' },
    { key: 'width', label: '宽度像素（0=原始）', type: 'number', default: 0 },
    { key: 'height', label: '高度像素（0=原始）', type: 'number', default: 0 },
  ],
  excel_add_chart: [
    F_FILE, F_SHEET,
    { key: 'chartType', label: '图表类型', type: 'select', default: 'bar', options: [
      { value: 'bar', label: '柱状图(横条)' }, { value: 'column', label: '柱状图(竖条)' }, { value: 'line', label: '折线图' },
      { value: 'pie', label: '饼图' }, { value: 'area', label: '面积图' }, { value: 'scatter', label: '散点图' },
    ] },
    { key: 'dataRange', label: '数据区域', type: 'text', placeholder: '如 B1:B10' },
    { key: 'catsRange', label: '分类(X轴)区域（可选）', type: 'text', placeholder: '如 A2:A10' },
    { key: 'anchor', label: '放置位置', type: 'text', placeholder: '如 H2', default: 'H2' },
    { key: 'title', label: '图表标题', type: 'text' },
    { key: 'titlesFromData', label: '首行作为系列名', type: 'switch', default: true },
  ],
  excel_data_validation: [
    F_FILE, F_SHEET,
    { key: 'range', label: '应用区域', type: 'text', placeholder: '如 A2:A100' },
    { key: 'validationType', label: '验证类型', type: 'select', default: 'list', options: [
      { value: 'list', label: '下拉列表' }, { value: 'whole', label: '整数' }, { value: 'decimal', label: '小数' }, { value: 'textLength', label: '文本长度' },
    ] },
    { key: 'options', label: '下拉选项(JSON数组)', type: 'textarea', placeholder: '["是","否"]', showWhen: { key: 'validationType', equals: 'list' } },
    { key: 'operator', label: '比较运算', type: 'select', default: 'between', showWhen: { key: 'validationType', equals: ['whole', 'decimal', 'textLength'] }, options: [
      { value: 'between', label: '介于' }, { value: 'notBetween', label: '不介于' }, { value: 'equal', label: '等于' }, { value: 'greaterThan', label: '大于' }, { value: 'lessThan', label: '小于' },
    ] },
    { key: 'formula1', label: '值1', type: 'text', showWhen: { key: 'validationType', equals: ['whole', 'decimal', 'textLength'] } },
    { key: 'formula2', label: '值2（介于时）', type: 'text', showWhen: { key: 'validationType', equals: ['whole', 'decimal', 'textLength'] } },
    { key: 'prompt', label: '输入提示（可选）', type: 'text' },
  ],
  excel_conditional_format: [
    F_FILE, F_SHEET,
    { key: 'range', label: '应用区域', type: 'text', placeholder: '如 A1:A20' },
    { key: 'ruleType', label: '规则类型', type: 'select', default: 'cellIs', options: [
      { value: 'cellIs', label: '单元格数值比较' }, { value: 'containsText', label: '包含文本' }, { value: 'colorScale', label: '色阶' }, { value: 'dataBar', label: '数据条' },
    ] },
    { key: 'operator', label: '比较运算', type: 'select', default: 'greaterThan', showWhen: { key: 'ruleType', equals: 'cellIs' }, options: [
      { value: 'greaterThan', label: '大于' }, { value: 'lessThan', label: '小于' }, { value: 'equal', label: '等于' }, { value: 'between', label: '介于' }, { value: 'notBetween', label: '不介于' },
    ] },
    { key: 'value1', label: '值1', type: 'text', showWhen: { key: 'ruleType', equals: 'cellIs' } },
    { key: 'value2', label: '值2（介于时）', type: 'text', showWhen: { key: 'ruleType', equals: 'cellIs' } },
    { key: 'text', label: '匹配文本', type: 'text', showWhen: { key: 'ruleType', equals: 'containsText' } },
    { key: 'bgColor', label: '高亮背景色', type: 'text', placeholder: '如 FFFF00', default: 'FFFF00', showWhen: { key: 'ruleType', equals: ['cellIs', 'containsText', 'dataBar'] } },
  ],
})

// ===== 筛选 / 排序 / 去重 / 字典 / CSV / 保护 / 页面 / 视图 =====
Object.assign(EXCEL_FIELD_SCHEMAS, {
  excel_auto_filter: [
    F_FILE, F_SHEET,
    { key: 'range', label: '筛选区域（留空清除）', type: 'text', placeholder: '如 A1:D100' },
  ],
  excel_sort_range: [
    F_FILE, F_SHEET,
    { key: 'range', label: '数据区域', type: 'text', placeholder: '如 A1:D100' },
    { key: 'sortColumn', label: '按区域内第几列排序', type: 'number', default: 1 },
    { key: 'descending', label: '降序', type: 'switch', default: false },
    { key: 'hasHeader', label: '首行为表头', type: 'switch', default: true },
  ],
  excel_remove_duplicates: [
    F_FILE, F_SHEET,
    { key: 'range', label: '数据区域（留空整表）', type: 'text', placeholder: '如 A1:D100' },
    { key: 'keyColumns', label: '判重列号（逗号分隔，留空整行）', type: 'text', placeholder: '如 1,2' },
    { key: 'hasHeader', label: '首行为表头', type: 'switch', default: true },
  ],
  excel_write_dicts: [
    F_FILE, F_SHEET,
    { key: 'data', label: '字典数组(JSON)', type: 'textarea', placeholder: '[{"姓名":"张三","年龄":18}]' },
    { key: 'startCell', label: '起始单元格', type: 'text', placeholder: 'A1', default: 'A1' },
    { key: 'writeHeader', label: '写入表头', type: 'switch', default: true },
  ],
  excel_read_dicts: [
    F_FILE, F_SHEET,
    { key: 'headerRow', label: '表头所在行号', type: 'number', default: 1 },
    { key: 'resultVariable', label: '存储到变量', type: 'varname', placeholder: 'records' },
  ],
  excel_to_csv: [
    F_FILE, F_SHEET,
    { key: 'csvPath', label: 'CSV 输出路径', type: 'path', placeholder: '如 D:\\out.csv' },
    { key: 'encoding', label: '编码', type: 'select', default: 'utf-8-sig', options: [{ value: 'utf-8-sig', label: 'UTF-8(带BOM,Excel友好)' }, { value: 'utf-8', label: 'UTF-8' }, { value: 'gbk', label: 'GBK' }] },
    { key: 'delimiter', label: '分隔符', type: 'text', placeholder: ',', default: ',' },
  ],
  excel_from_csv: [
    { key: 'csvPath', label: 'CSV 文件路径', type: 'path', placeholder: '如 D:\\data.csv' },
    { key: 'filePath', label: '输出 Excel 路径', type: 'path', placeholder: '如 D:\\out.xlsx' },
    { key: 'sheetName', label: '工作表名', type: 'text', placeholder: 'Sheet1', default: 'Sheet1' },
    { key: 'encoding', label: '编码', type: 'select', default: 'utf-8-sig', options: [{ value: 'utf-8-sig', label: 'UTF-8(带BOM)' }, { value: 'utf-8', label: 'UTF-8' }, { value: 'gbk', label: 'GBK' }] },
    { key: 'delimiter', label: '分隔符', type: 'text', placeholder: ',', default: ',' },
  ],
  excel_protect_sheet: [
    F_FILE, F_SHEET,
    { key: 'protect', label: '保护（关闭则取消）', type: 'switch', default: true },
    { key: 'password', label: '密码（可选）', type: 'text' },
  ],
  excel_page_setup: [
    F_FILE, F_SHEET,
    { key: 'orientation', label: '方向', type: 'select', default: '', options: [{ value: '', label: '不改' }, { value: 'portrait', label: '纵向' }, { value: 'landscape', label: '横向' }] },
    { key: 'paperSize', label: '纸张', type: 'select', default: '', options: [{ value: '', label: '不改' }, { value: 'A4', label: 'A4' }, { value: 'A3', label: 'A3' }, { value: 'A5', label: 'A5' }, { value: 'Letter', label: 'Letter' }] },
    { key: 'fitToWidth', label: '适配页宽（0=不启用）', type: 'number', default: 0 },
    { key: 'fitToHeight', label: '适配页高（0=不启用）', type: 'number', default: 0 },
    { key: 'printArea', label: '打印区域（可选）', type: 'text', placeholder: '如 A1:F50' },
  ],
  excel_set_zoom: [
    F_FILE, F_SHEET,
    { key: 'zoom', label: '缩放比例(10~400)', type: 'number', default: 100 },
    { key: 'showGridLines', label: '显示网格线', type: 'switch', default: true },
  ],
})


// ===== 影刀对标补全模块 =====
Object.assign(EXCEL_FIELD_SCHEMAS, {
  excel_count_rows: [
    F_FILE, F_SHEET,
    { key: 'resultVariable', label: '存储到变量（总行数）', type: 'varname', placeholder: 'row_count' },
  ],
  excel_find_empty_row: [
    F_FILE, F_SHEET,
    { key: 'column', label: '判断列（按此列找空行）', type: 'text', placeholder: '如 A', default: 'A' },
    { key: 'direction', label: '方向', type: 'select', default: 'down', options: [{ value: 'down', label: '从上往下' }, { value: 'up', label: '从下往上(末尾追加位置)' }] },
    { key: 'resultVariable', label: '存储到变量（行号）', type: 'varname', placeholder: 'empty_row' },
  ],
  excel_find_empty_col: [
    F_FILE, F_SHEET,
    { key: 'row', label: '判断行（按此行找空列）', type: 'number', default: 1 },
    { key: 'resultVariable', label: '存储到变量（列字母）', type: 'varname', placeholder: 'empty_col' },
  ],
  excel_find_empty_cell: [
    F_FILE, F_SHEET,
    { key: 'column', label: '列', type: 'text', placeholder: '如 A', default: 'A' },
    { key: 'startRow', label: '起始行', type: 'number', default: 1 },
    { key: 'resultVariable', label: '存储到变量（单元格地址）', type: 'varname', placeholder: 'empty_cell' },
  ],
  excel_fill_range: [
    F_FILE, F_SHEET,
    { key: 'range', label: '填充区域', type: 'text', placeholder: '如 A1:C10' },
    { key: 'value', label: '填充值（支持 {变量}/公式）', type: 'text' },
  ],
  excel_clear_style: [
    F_FILE, F_SHEET,
    { key: 'range', label: '区域（清除样式保留内容）', type: 'text', placeholder: '如 A1:C10' },
  ],
  excel_activate_sheet: [
    F_FILE,
    { key: 'sheetName', label: '要激活的工作表名', type: 'text', placeholder: '如 Sheet2' },
  ],
  excel_save_as: [
    F_FILE,
    { key: 'newPath', label: '另存为路径', type: 'path', placeholder: '如 D:\\副本.xlsx' },
  ],
  excel_pivot_table: [
    F_FILE, F_SHEET,
    { key: 'sourceRange', label: '源数据区域（含表头，留空整表）', type: 'text', placeholder: '如 A1:D100' },
    { key: 'groupBy', label: '分组列名（表头，逗号分隔多列）', type: 'text', placeholder: '如 部门' },
    { key: 'valueColumn', label: '聚合列名（表头）', type: 'text', placeholder: '如 业绩' },
    { key: 'aggregation', label: '聚合方式', type: 'select', default: 'sum', options: [
      { value: 'sum', label: '求和' }, { value: 'count', label: '计数' }, { value: 'average', label: '平均' }, { value: 'max', label: '最大' }, { value: 'min', label: '最小' },
    ] },
    { key: 'destSheet', label: '结果工作表（留空当前表）', type: 'text' },
    { key: 'destCell', label: '结果起始单元格', type: 'text', placeholder: 'A1', default: 'A1' },
  ],
  excel_to_pdf: [
    F_FILE,
    { key: 'sheetName', label: '工作表（留空导出整个工作簿）', type: 'text' },
    { key: 'pdfPath', label: 'PDF 输出路径（留空同名）', type: 'path', placeholder: '如 D:\\out.pdf' },
  ],
  excel_run_macro: [
    F_FILE,
    { key: 'macroName', label: '宏名称', type: 'text', placeholder: '如 Module1.MyMacro' },
    { key: 'saveAfter', label: '运行后保存', type: 'switch', default: false },
    { key: 'resultVariable', label: '存储宏返回值（可选）', type: 'varname', placeholder: 'macro_result' },
  ],
  excel_refresh_data: [
    F_FILE,
  ],
})
