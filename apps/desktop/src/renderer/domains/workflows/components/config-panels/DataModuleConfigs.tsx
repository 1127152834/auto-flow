// Source: WebRPA@5ccb900e, components/workflow/config-panels/DataModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { SelectNative as Select } from '../controls/select-native'
import { Checkbox } from '../controls/checkbox'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { VariableRefInput } from '../controls/variable-ref-input'
import { PathInput } from '../controls/path-input'

// ==================== 字符串操作模块 ====================

// 正则表达式提取配置
export function RegexExtractConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="inputText">输入文本</Label>
        <VariableInput
          value={(data.inputText as string) || ''}
          onChange={(v) => onChange('inputText', v)}
          placeholder="要匹配的文本，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="pattern">正则表达式</Label>
        <VariableInput
          value={(data.pattern as string) || ''}
          onChange={(v) => onChange('pattern', v)}
          placeholder="如: \d+、[a-z]+、(.+?)等"
        />
        <p className="text-xs text-muted-foreground">
          使用括号()捕获分组，如: 价格(\d+)元
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="extractMode">提取模式</Label>
        <Select
          id="extractMode"
          value={(data.extractMode as string) || 'first'}
          onChange={(e) => onChange('extractMode', e.target.value)}
        >
          <option value="first">提取第一个匹配</option>
          <option value="all">提取所有匹配</option>
          <option value="groups">提取捕获组</option>
        </Select>
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="ignoreCase"
          checked={(data.ignoreCase as boolean) || false}
          onCheckedChange={(checked) => onChange('ignoreCase', checked)}
        />
        <Label htmlFor="ignoreCase" className="text-sm font-normal">忽略大小写</Label>
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800">
          提示：提取所有匹配返回列表，提取捕获组返回分组内容
        </p>
      </div>
    </>
  )
}

// 字符串替换配置
export function StringReplaceConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="inputText">输入文本</Label>
        <VariableInput
          value={(data.inputText as string) || ''}
          onChange={(v) => onChange('inputText', v)}
          placeholder="要处理的文本，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="replaceMode">替换模式</Label>
        <Select
          id="replaceMode"
          value={(data.replaceMode as string) || 'text'}
          onChange={(e) => onChange('replaceMode', e.target.value)}
        >
          <option value="text">普通文本替换</option>
          <option value="regex">正则表达式替换</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="searchValue">
          {(data.replaceMode as string) === 'regex' ? '正则表达式' : '查找内容'}
        </Label>
        <VariableInput
          value={(data.searchValue as string) || ''}
          onChange={(v) => onChange('searchValue', v)}
          placeholder={(data.replaceMode as string) === 'regex' ? '正则表达式，如: \\d+' : '要查找的文本'}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="replaceValue">替换为</Label>
        <VariableInput
          value={(data.replaceValue as string) || ''}
          onChange={(v) => onChange('replaceValue', v)}
          placeholder="替换后的文本，支持 {变量名}"
        />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="replaceAll"
          checked={(data.replaceAll as boolean) !== false}
          onCheckedChange={(checked) => onChange('replaceAll', checked)}
        />
        <Label htmlFor="replaceAll" className="text-sm font-normal">替换所有匹配</Label>
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 字符串分割配置
export function StringSplitConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="inputText">输入文本</Label>
        <VariableInput
          value={(data.inputText as string) || ''}
          onChange={(v) => onChange('inputText', v)}
          placeholder="要分割的文本，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="separator">分隔符</Label>
        <VariableInput
          value={(data.separator as string) || ''}
          onChange={(v) => onChange('separator', v)}
          placeholder="如: , 或 | 或 \n（换行），支持 {变量名}"
        />
        <p className="text-xs text-muted-foreground">
          常用: 逗号(,)、竖线(|)、换行(\n)、空格( )
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="maxSplit">最大分割数 (可选)</Label>
        <VariableInput
          value={String(data.maxSplit ?? '')}
          onChange={(v) => {
            if (v === '' || v.includes('{')) {
              onChange('maxSplit', v)
            } else {
              const num = parseInt(v)
              onChange('maxSplit', isNaN(num) ? '' : num)
            }
          }}
          placeholder="留空表示不限制，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
        <p className="text-xs text-muted-foreground">
          结果为列表类型
        </p>
      </div>
    </>
  )
}

// 字符串连接配置
export function StringJoinConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量名</Label>
        <VariableRefInput
          id="listVariable"
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="填写变量名，如: myList"
        />
        <p className="text-xs text-muted-foreground">
          要连接的列表变量
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="separator">连接符</Label>
        <VariableInput
          value={(data.separator as string) || ''}
          onChange={(v) => onChange('separator', v)}
          placeholder="如: , 或 - 或留空，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 字符串拼接配置
export function StringConcatConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="string1">字符串1</Label>
        <VariableInput
          value={(data.string1 as string) || ''}
          onChange={(v) => onChange('string1', v)}
          placeholder="第一个字符串，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="string2">字符串2</Label>
        <VariableInput
          value={(data.string2 as string) || ''}
          onChange={(v) => onChange('string2', v)}
          placeholder="第二个字符串，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 字符串去空白配置
export function StringTrimConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="inputText">输入文本</Label>
        <VariableInput
          value={(data.inputText as string) || ''}
          onChange={(v) => onChange('inputText', v)}
          placeholder="要处理的文本，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="trimMode">去除模式</Label>
        <Select
          id="trimMode"
          value={(data.trimMode as string) || 'both'}
          onChange={(e) => onChange('trimMode', e.target.value)}
        >
          <option value="both">去除首尾空白</option>
          <option value="start">仅去除开头空白</option>
          <option value="end">仅去除结尾空白</option>
          <option value="all">去除所有空白</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 字符串大小写转换配置
export function StringCaseConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="inputText">输入文本</Label>
        <VariableInput
          value={(data.inputText as string) || ''}
          onChange={(v) => onChange('inputText', v)}
          placeholder="要转换的文本，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="caseMode">转换模式</Label>
        <Select
          id="caseMode"
          value={(data.caseMode as string) || 'upper'}
          onChange={(e) => onChange('caseMode', e.target.value)}
        >
          <option value="upper">全部大写</option>
          <option value="lower">全部小写</option>
          <option value="capitalize">首字母大写</option>
          <option value="title">每个单词首字母大写</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 字符串截取配置
export function StringSubstringConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="inputText">输入文本</Label>
        <VariableInput
          value={(data.inputText as string) || ''}
          onChange={(v) => onChange('inputText', v)}
          placeholder="要截取的文本，支持 {变量名}"
          multiline
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="startIndex">起始位置</Label>
        <VariableInput
          value={String((data.startIndex as number) ?? 0)}
          onChange={(v) => onChange('startIndex', v)}
          placeholder="从0开始，支持负数和 {变量名}"
        />
        <p className="text-xs text-muted-foreground">
          0表示第一个字符，-1表示最后一个字符
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="endIndex">结束位置 (可选)</Label>
        <VariableInput
          value={(data.endIndex as string) || ''}
          onChange={(v) => onChange('endIndex', v)}
          placeholder="留空表示到末尾，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// JSON解析配置
export function JsonParseConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="sourceVariable">源数据变量</Label>
        <VariableRefInput
          id="sourceVariable"
          value={(data.sourceVariable as string) || ''}
          onChange={(v) => onChange('sourceVariable', v)}
          placeholder="填写变量名，如: jsonData"
        />
        <p className="text-xs text-muted-foreground">
          直接填写包含JSON数据的变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="jsonPath">JSONPath表达式</Label>
        <VariableInput
          value={(data.jsonPath as string) || ''}
          onChange={(v) => onChange('jsonPath', v)}
          placeholder="$.data.items[0].name，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="columnName">Excel列名 (可选)</Label>
        <VariableInput
          value={(data.columnName as string) || ''}
          onChange={(v) => onChange('columnName', v)}
          placeholder="用于数据导出，支持 {变量名}"
        />
      </div>
    </>
  )
}

// Base64处理配置
export function Base64Config({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  const operation = (data.operation as string) || 'encode'
  
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="operation">操作类型</Label>
        <Select
          id="operation"
          value={operation}
          onChange={(e) => onChange('operation', e.target.value)}
        >
          <option value="encode">文本编码为Base64</option>
          <option value="decode">Base64解码为文本</option>
          <option value="file_to_base64">文件转Base64</option>
          <option value="base64_to_file">Base64转文件</option>
        </Select>
      </div>
      
      {operation === 'encode' && (
        <div className="space-y-2">
          <Label htmlFor="inputText">输入文本</Label>
          <VariableInput
            value={(data.inputText as string) || ''}
            onChange={(v) => onChange('inputText', v)}
            placeholder="要编码的文本，支持 {变量名}"
            multiline
            rows={3}
          />
        </div>
      )}
      
      {operation === 'decode' && (
        <div className="space-y-2">
          <Label htmlFor="inputBase64">Base64字符串</Label>
          <VariableInput
            value={(data.inputBase64 as string) || ''}
            onChange={(v) => onChange('inputBase64', v)}
            placeholder="要解码的Base64字符串，支持 {变量名}"
            multiline
            rows={3}
          />
        </div>
      )}
      
      {operation === 'file_to_base64' && (
        <div className="space-y-2">
          <Label htmlFor="filePath">文件路径</Label>
          <PathInput
            type="file"
            value={(data.filePath as string) || ''}
            onChange={(v) => onChange('filePath', v)}
            placeholder="选择要转换的文件，支持 {变量名}"
            title="选择文件"
          />
        </div>
      )}
      
      {operation === 'base64_to_file' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="inputBase64">Base64字符串</Label>
            <VariableInput
              value={(data.inputBase64 as string) || ''}
              onChange={(v) => onChange('inputBase64', v)}
              placeholder="Base64编码的数据，支持 {变量名}"
              multiline
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="outputPath">保存路径</Label>
            <PathInput
              type="folder"
              value={(data.outputPath as string) || ''}
              onChange={(v) => onChange('outputPath', v)}
              placeholder="文件保存目录，支持 {变量名}"
              title="选择保存目录"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="fileName">文件名</Label>
            <VariableInput
              value={(data.fileName as string) || ''}
              onChange={(v) => onChange('fileName', v)}
              placeholder="output.png，支持 {变量名}"
            />
          </div>
        </>
      )}
      
      <div className="space-y-2">
        <Label htmlFor="variableName">存储结果到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
      
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800">
          {operation === 'encode' && '将文本转换为Base64编码字符串'}
          {operation === 'decode' && '将Base64字符串解码为原始文本'}
          {operation === 'file_to_base64' && '读取文件并转换为Base64字符串（可用于图片上传等场景）'}
          {operation === 'base64_to_file' && '将Base64数据保存为文件'}
        </p>
      </div>
    </>
  )
}

// 随机数配置
export function RandomNumberConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="randomType">随机类型</Label>
        <Select
          id="randomType"
          value={(data.randomType as string) || 'integer'}
          onChange={(e) => onChange('randomType', e.target.value)}
        >
          <option value="integer">整数</option>
          <option value="float">小数</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="minValue">最小值</Label>
        <VariableInput
          value={String((data.minValue as number) ?? 0)}
          onChange={(v) => onChange('minValue', parseFloat(v) || 0)}
          placeholder="最小值，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="maxValue">最大值</Label>
        <VariableInput
          value={String((data.maxValue as number) ?? 100)}
          onChange={(v) => onChange('maxValue', parseFloat(v) || 100)}
          placeholder="最大值，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 获取时间配置
export function GetTimeConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="timeFormat">时间格式</Label>
        <Select
          id="timeFormat"
          value={(data.timeFormat as string) || 'datetime'}
          onChange={(e) => onChange('timeFormat', e.target.value)}
        >
          <option value="datetime">完整日期时间</option>
          <option value="date">仅日期</option>
          <option value="time">仅时间</option>
          <option value="timestamp">时间戳</option>
          <option value="iso8601">ISO 8601（本地时区）</option>
          <option value="iso8601_utc">ISO 8601（UTC）</option>
          <option value="custom">自定义格式</option>
        </Select>
      </div>
      {(data.timeFormat as string) === 'custom' && (
        <div className="space-y-2">
          <Label htmlFor="customFormat">自定义格式</Label>
          <VariableInput
            value={(data.customFormat as string) || ''}
            onChange={(v) => onChange('customFormat', v)}
            placeholder="%Y年%m月%d日，支持 {变量名}"
          />
        </div>
      )}
      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 列表操作配置
export function ListOperationConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量名</Label>
        <VariableRefInput
          id="listVariable"
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="填写变量名，如: myList"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要操作的列表变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="listAction">操作类型</Label>
        <Select
          id="listAction"
          value={(data.listAction as string) || 'append'}
          onChange={(e) => onChange('listAction', e.target.value)}
        >
          <option value="append">追加元素</option>
          <option value="insert">插入元素</option>
          <option value="remove">删除元素</option>
          <option value="pop">弹出元素</option>
          <option value="clear">清空列表</option>
          <option value="reverse">反转列表</option>
          <option value="sort">排序列表</option>
        </Select>
      </div>
      {['append', 'insert', 'remove'].includes((data.listAction as string) || 'append') && (
        <div className="space-y-2">
          <Label htmlFor="listValue">操作值</Label>
          <VariableInput
            value={(data.listValue as string) || ''}
            onChange={(v) => onChange('listValue', v)}
            placeholder="要添加/删除的值，支持 {变量名}"
          />
        </div>
      )}
      {['insert', 'pop'].includes((data.listAction as string) || '') && (
        <div className="space-y-2">
          <Label htmlFor="listIndex">索引位置</Label>
          <VariableInput
            value={String(data.listIndex ?? '')}
            onChange={(v) => {
              if (v === '' || v.includes('{')) {
                onChange('listIndex', v)
              } else {
                const num = parseInt(v)
                onChange('listIndex', isNaN(num) ? v : num)
              }
            }}
            placeholder="从0开始的索引，支持 {变量名}"
          />
        </div>
      )}
      {(data.listAction as string) === 'pop' && (
        <div className="space-y-2">
          <Label htmlFor="resultVariable">存储弹出值到变量</Label>
          <VariableNameInput
            id="resultVariable"
            value={(data.resultVariable as string) || ''}
            onChange={(v) => onChange('resultVariable', v)}
            placeholder="变量名"
          />
        </div>
      )}
    </>
  )
}

// 获取列表元素配置
export function ListGetConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量名</Label>
        <VariableRefInput
          id="listVariable"
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="填写变量名，如: myList"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要获取元素的列表变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="listIndex">索引位置</Label>
        <VariableInput
          value={(data.listIndex as string) || ''}
          onChange={(v) => onChange('listIndex', v)}
          placeholder="从0开始，支持负数和 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 获取列表长度配置
export function ListLengthConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量名</Label>
        <VariableRefInput
          id="listVariable"
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="填写变量名，如: myList"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要获取长度的列表变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储长度到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 列表数据导出配置
export function ListExportConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="listVariable">列表变量名</Label>
        <VariableRefInput
          id="listVariable"
          value={(data.listVariable as string) || ''}
          onChange={(v) => onChange('listVariable', v)}
          placeholder="填写变量名，如: myList"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要导出的列表变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="outputPath">输出文件路径</Label>
        <PathInput
          value={(data.outputPath as string) || ''}
          onChange={(v) => onChange('outputPath', v)}
          placeholder="D:\data\output.txt，支持 {变量名}"
          type="file"
          title="选择保存位置"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="separator">分隔符</Label>
        <Select
          id="separator"
          value={(data.separator as string) || '\n'}
          onChange={(e) => onChange('separator', e.target.value)}
        >
          <option value="\n">换行符（每行一条）</option>
          <option value="\r\n">Windows换行符</option>
          <option value=",">逗号</option>
          <option value="\t">制表符</option>
          <option value=" ">空格</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="encoding">文件编码</Label>
        <Select
          id="encoding"
          value={(data.encoding as string) || 'utf-8'}
          onChange={(e) => onChange('encoding', e.target.value)}
        >
          <option value="utf-8">UTF-8</option>
          <option value="gbk">GBK（中文Windows）</option>
          <option value="utf-8-sig">UTF-8 BOM</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="appendMode">写入模式</Label>
        <Select
          id="appendMode"
          value={String(data.appendMode ?? false)}
          onChange={(e) => onChange('appendMode', e.target.value === 'true')}
        >
          <option value="false">覆盖写入</option>
          <option value="true">追加写入</option>
        </Select>
      </div>
      <p className="text-xs text-muted-foreground">
        将列表中的每个元素导出为文本文件，每个元素占一行
      </p>
    </>
  )
}

// 字典操作配置
export function DictOperationConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量名</Label>
        <VariableRefInput
          id="dictVariable"
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="填写变量名，如: myDict"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要操作的字典变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="dictAction">操作类型</Label>
        <Select
          id="dictAction"
          value={(data.dictAction as string) || 'set'}
          onChange={(e) => onChange('dictAction', e.target.value)}
        >
          <option value="set">设置键值</option>
          <option value="delete">删除键</option>
          <option value="clear">清空字典</option>
        </Select>
      </div>
      {['set', 'delete'].includes((data.dictAction as string) || 'set') && (
        <div className="space-y-2">
          <Label htmlFor="dictKey">键名</Label>
          <VariableInput
            value={(data.dictKey as string) || ''}
            onChange={(v) => onChange('dictKey', v)}
            placeholder="键名，支持 {变量名}"
          />
        </div>
      )}
      {((data.dictAction as string) || 'set') === 'set' && (
        <div className="space-y-2">
          <Label htmlFor="dictValue">值</Label>
          <VariableInput
            value={(data.dictValue as string) || ''}
            onChange={(v) => onChange('dictValue', v)}
            placeholder="要设置的值，支持 {变量名}"
          />
        </div>
      )}
    </>
  )
}

// 获取字典值配置
export function DictGetConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量名</Label>
        <VariableRefInput
          id="dictVariable"
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="填写变量名，如: myDict"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要获取值的字典变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="dictKey">键名</Label>
        <VariableInput
          value={(data.dictKey as string) || ''}
          onChange={(v) => onChange('dictKey', v)}
          placeholder="键名，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="defaultValue">默认值 (可选)</Label>
        <VariableInput
          value={(data.defaultValue as string) || ''}
          onChange={(v) => onChange('defaultValue', v)}
          placeholder="键不存在时的默认值，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 获取字典键配置
export function DictKeysConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="dictVariable">字典变量名</Label>
        <VariableRefInput
          id="dictVariable"
          value={(data.dictVariable as string) || ''}
          onChange={(v) => onChange('dictVariable', v)}
          placeholder="填写变量名，如: myDict"
        />
        <p className="text-xs text-muted-foreground">
          直接填写要获取键的字典变量名
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="keyType">获取类型</Label>
        <Select
          id="keyType"
          value={(data.keyType as string) || 'keys'}
          onChange={(e) => onChange('keyType', e.target.value)}
        >
          <option value="keys">所有键</option>
          <option value="values">所有值</option>
          <option value="items">键值对</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}


// ==================== 数据表格操作模块 ====================

// 添加数据行配置
export function TableAddRowConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="rowData">行数据 (JSON格式)</Label>
        <VariableInput
          value={(data.rowData as string) || ''}
          onChange={(v) => onChange('rowData', v)}
          placeholder='{"列名1": "值1", "列名2": "值2"}，支持 {变量名}'
          multiline
          rows={3}
        />
        <p className="text-xs text-muted-foreground">
          JSON对象格式，键为列名，值为单元格内容
        </p>
      </div>
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800">
          向数据表格添加一行数据，数据将显示在底部的数据预览面板中
        </p>
      </div>
    </>
  )
}

// 添加数据列配置
export function TableAddColumnConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="columnName">列名</Label>
        <VariableInput
          value={(data.columnName as string) || ''}
          onChange={(v) => onChange('columnName', v)}
          placeholder="新列的名称，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="defaultValue">默认值 (可选)</Label>
        <VariableInput
          value={(data.defaultValue as string) || ''}
          onChange={(v) => onChange('defaultValue', v)}
          placeholder="新列的默认值，支持 {变量名}"
        />
      </div>
      <p className="text-xs text-muted-foreground">
        为数据表格添加新列，已有的行将使用默认值填充
      </p>
    </>
  )
}

// 设置单元格配置
export function TableSetCellConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="rowIndex">行索引</Label>
        <VariableInput
          value={String((data.rowIndex as number) ?? 0)}
          onChange={(v) => onChange('rowIndex', v)}
          placeholder="从0开始，支持负数和 {变量名}"
        />
        <p className="text-xs text-muted-foreground">
          0表示第一行，-1表示最后一行
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="columnName">列名</Label>
        <VariableInput
          value={(data.columnName as string) || ''}
          onChange={(v) => onChange('columnName', v)}
          placeholder="要设置的列名，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="cellValue">单元格值</Label>
        <VariableInput
          value={(data.cellValue as string) || ''}
          onChange={(v) => onChange('cellValue', v)}
          placeholder="要设置的值，支持 {变量名}"
        />
      </div>
    </>
  )
}

// 获取单元格配置
export function TableGetCellConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="rowIndex">行索引</Label>
        <VariableInput
          value={String((data.rowIndex as number) ?? 0)}
          onChange={(v) => onChange('rowIndex', v)}
          placeholder="从0开始，支持负数和 {变量名}"
        />
        <p className="text-xs text-muted-foreground">
          0表示第一行，-1表示最后一行
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="columnName">列名</Label>
        <VariableInput
          value={(data.columnName as string) || ''}
          onChange={(v) => onChange('columnName', v)}
          placeholder="要获取的列名，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}

// 删除数据行配置
export function TableDeleteRowConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="rowIndex">行索引</Label>
        <VariableInput
          value={String((data.rowIndex as number) ?? 0)}
          onChange={(v) => onChange('rowIndex', v)}
          placeholder="从0开始，支持负数和 {变量名}"
        />
        <p className="text-xs text-muted-foreground">
          0表示第一行，-1表示最后一行
        </p>
      </div>
      <p className="text-xs text-muted-foreground">
        删除指定索引的数据行
      </p>
    </>
  )
}

// 清空数据表配置
export function TableClearConfig() {
  return (
    <>
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
        <p className="text-xs text-amber-800">
          此操作将清空数据表格中的所有数据，无法恢复
        </p>
      </div>
      <p className="text-xs text-muted-foreground">
        清空数据预览面板中的所有数据
      </p>
    </>
  )
}

// 导出数据表配置
export function TableExportConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="exportFormat">导出格式</Label>
        <Select
          id="exportFormat"
          value={(data.exportFormat as string) || 'excel'}
          onChange={(e) => onChange('exportFormat', e.target.value)}
        >
          <option value="excel">Excel (.xlsx)</option>
          <option value="csv">CSV (.csv)</option>
        </Select>
      </div>
      
      {/* 仅在Excel格式时显示Sheet名称配置 */}
      {((data.exportFormat as string) || 'excel') === 'excel' && (
        <div className="space-y-2">
          <Label htmlFor="sheetName">Sheet名称</Label>
          <VariableInput
            id="sheetName"
            value={(data.sheetName as string) || '数据'}
            onChange={(v) => onChange('sheetName', v)}
            placeholder="数据，支持 {变量名}"
          />
          <p className="text-xs text-muted-foreground">
            若文件已存在且包含同名Sheet，将覆盖该Sheet；若不存在则自动创建
          </p>
        </div>
      )}
      
      <div className="space-y-2">
        <Label htmlFor="savePath">保存路径 (可选)</Label>
        <PathInput
          type="folder"
          value={(data.savePath as string) || ''}
          onChange={(v) => onChange('savePath', v)}
          placeholder="C:\data，支持 {变量名}"
          title="选择导出保存目录"
        />
        <p className="text-xs text-muted-foreground">
          留空则自动保存到 data 目录
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="fileNamePattern">文件名模式</Label>
        <VariableInput
          value={(data.fileNamePattern as string) || ''}
          onChange={(v) => onChange('fileNamePattern', v)}
          placeholder="data_{时间戳}，支持 {变量名}"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variableName">存储路径到变量</Label>
        <VariableNameInput
          id="variableName"
          value={(data.variableName as string) || ''}
          onChange={(v) => onChange('variableName', v)}
          placeholder="变量名"
        />
      </div>
    </>
  )
}
