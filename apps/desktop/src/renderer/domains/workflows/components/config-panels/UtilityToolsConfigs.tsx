// Source: WebRPA@5ccb900e, components/workflow/config-panels/UtilityToolsConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { Checkbox } from '../controls/checkbox'
import { FolderOpen } from 'lucide-react'
import { Button } from '../controls/button'
import { systemApi } from '../../api'

interface ConfigProps {
  config: Record<string, unknown>
  updateConfig: (key: string, value: unknown) => void
}

// 选择文件的辅助函数（统一走 systemApi.selectFile）
const selectFile = async (updateConfig: (key: string, value: unknown) => void, key: string, filter?: string) => {
  try {
    let fileTypes: [string, string][] | undefined
    if (filter) {
      const parts = filter.split('|')
      if (parts.length >= 2) {
        fileTypes = [[parts[0], parts[1]]]
      }
    }
    const result = await systemApi.selectFile('选择文件', undefined, fileTypes)
    const inner = result.data as any
    if (inner?.success && inner?.path) {
      updateConfig(key, inner.path)
    }
  } catch (error) {
    console.error('选择文件失败:', error)
  }
}

// 选择文件夹的辅助函数（统一走 systemApi.selectFolder）
const selectFolder = async (updateConfig: (key: string, value: unknown) => void, key: string) => {
  try {
    const result = await systemApi.selectFolder('选择文件夹')
    const inner = result.data as any
    if (inner?.success && inner?.path) {
      updateConfig(key, inner.path)
    }
  } catch (error) {
    console.error('选择文件夹失败:', error)
  }
}

// 文件哈希对比配置
export function FileHashCompareConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>文件1路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.file1Path || '')}
            onChange={(v) => updateConfig('file1Path', v)}
            placeholder="C:/files/file1.txt"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'file1Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>文件2路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.file2Path || '')}
            onChange={(v) => updateConfig('file2Path', v)}
            placeholder="C:/files/file2.txt"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'file2Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>哈希算法</Label>
        <Select value={String(config.hashAlgorithm || 'md5')} onChange={(e) => updateConfig('hashAlgorithm', e.target.value)}>
          <option value="md5">MD5</option>
          <option value="sha1">SHA1</option>
          <option value="sha256">SHA256</option>
          <option value="sha512">SHA512</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（布尔值）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="files_equal"
        />
      </div>
    </div>
  )
}

// 文件差异对比配置
export function FileDiffCompareConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>文件1路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.file1Path || '')}
            onChange={(v) => updateConfig('file1Path', v)}
            placeholder="C:/files/file1.txt"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'file1Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>文件2路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.file2Path || '')}
            onChange={(v) => updateConfig('file2Path', v)}
            placeholder="C:/files/file2.txt"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'file2Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出格式</Label>
        <Select value={String(config.outputFormat || 'unified')} onChange={(e) => updateConfig('outputFormat', e.target.value)}>
          <option value="unified">统一格式（Unified）</option>
          <option value="context">上下文格式（Context）</option>
          <option value="html">HTML格式</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（差异文本）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="file_diff"
        />
      </div>
    </div>
  )
}

// 文件夹哈希对比配置
export function FolderHashCompareConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>文件夹1路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.folder1Path || '')}
            onChange={(v) => updateConfig('folder1Path', v)}
            placeholder="C:/folder1"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'folder1Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>文件夹2路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.folder2Path || '')}
            onChange={(v) => updateConfig('folder2Path', v)}
            placeholder="C:/folder2"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'folder2Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（布尔值）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="folders_equal"
        />
      </div>
    </div>
  )
}


// 文件夹差异对比配置
export function FolderDiffCompareConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>文件夹1路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.folder1Path || '')}
            onChange={(v) => updateConfig('folder1Path', v)}
            placeholder="C:/folder1"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'folder1Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>文件夹2路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.folder2Path || '')}
            onChange={(v) => updateConfig('folder2Path', v)}
            placeholder="C:/folder2"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'folder2Path')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（差异文件列表）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="diff_files"
        />
      </div>
    </div>
  )
}

// 随机密码生成配置
export function RandomPasswordGeneratorConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>密码长度</Label>
        <VariableInput
          value={String(config.length || '16')}
          onChange={(v) => updateConfig('length', v)}
          placeholder="16"
          type="number"
        />
      </div>
      <div className="space-y-3">
        <Label>字符类型</Label>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="includeUppercase"
            checked={config.includeUppercase !== false}
            onCheckedChange={(checked) => updateConfig('includeUppercase', checked)}
          />
          <Label htmlFor="includeUppercase" className="cursor-pointer">包含大写字母 (A-Z)</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="includeLowercase"
            checked={config.includeLowercase !== false}
            onCheckedChange={(checked) => updateConfig('includeLowercase', checked)}
          />
          <Label htmlFor="includeLowercase" className="cursor-pointer">包含小写字母 (a-z)</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="includeDigits"
            checked={config.includeDigits !== false}
            onCheckedChange={(checked) => updateConfig('includeDigits', checked)}
          />
          <Label htmlFor="includeDigits" className="cursor-pointer">包含数字 (0-9)</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="includeSymbols"
            checked={config.includeSymbols !== false}
            onCheckedChange={(checked) => updateConfig('includeSymbols', checked)}
          />
          <Label htmlFor="includeSymbols" className="cursor-pointer">包含特殊符号 (!@#$...)</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="excludeAmbiguous"
            checked={config.excludeAmbiguous === true}
            onCheckedChange={(checked) => updateConfig('excludeAmbiguous', checked)}
          />
          <Label htmlFor="excludeAmbiguous" className="cursor-pointer">排除易混淆字符 (il1Lo0O)</Label>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="generated_password"
        />
      </div>
    </div>
  )
}


// URL编解码配置
export function URLEncodeDecodeConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入文本</Label>
        <VariableInput
          value={String(config.inputText || '')}
          onChange={(v) => updateConfig('inputText', v)}
          placeholder="要编码或解码的文本"
        />
      </div>
      <div className="space-y-2">
        <Label>操作类型</Label>
        <Select value={String(config.operation || 'encode')} onChange={(e) => updateConfig('operation', e.target.value)}>
          <option value="encode">编码（Encode）</option>
          <option value="decode">解码（Decode）</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>字符编码</Label>
        <Select value={String(config.encoding || 'utf-8')} onChange={(e) => updateConfig('encoding', e.target.value)}>
          <option value="utf-8">UTF-8</option>
          <option value="gbk">GBK</option>
          <option value="gb2312">GB2312</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="url_result"
        />
      </div>
    </div>
  )
}

// MD5加密配置
export function MD5EncryptConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入文本</Label>
        <VariableInput
          value={String(config.inputText || '')}
          onChange={(v) => updateConfig('inputText', v)}
          placeholder="要加密的文本"
        />
      </div>
      <div className="space-y-2">
        <Label>字符编码</Label>
        <Select value={String(config.encoding || 'utf-8')} onChange={(e) => updateConfig('encoding', e.target.value)}>
          <option value="utf-8">UTF-8</option>
          <option value="gbk">GBK</option>
          <option value="gb2312">GB2312</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>输出格式</Label>
        <Select value={String(config.outputFormat || 'hex')} onChange={(e) => updateConfig('outputFormat', e.target.value)}>
          <option value="hex">十六进制（Hex）</option>
          <option value="base64">Base64</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="md5_hash"
        />
      </div>
    </div>
  )
}

// SHA加密配置
export function SHAEncryptConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入文本</Label>
        <VariableInput
          value={String(config.inputText || '')}
          onChange={(v) => updateConfig('inputText', v)}
          placeholder="要加密的文本"
        />
      </div>
      <div className="space-y-2">
        <Label>SHA算法</Label>
        <Select value={String(config.shaType || 'sha256')} onChange={(e) => updateConfig('shaType', e.target.value)}>
          <option value="sha1">SHA1</option>
          <option value="sha224">SHA224</option>
          <option value="sha256">SHA256</option>
          <option value="sha384">SHA384</option>
          <option value="sha512">SHA512</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>字符编码</Label>
        <Select value={String(config.encoding || 'utf-8')} onChange={(e) => updateConfig('encoding', e.target.value)}>
          <option value="utf-8">UTF-8</option>
          <option value="gbk">GBK</option>
          <option value="gb2312">GB2312</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>输出格式</Label>
        <Select value={String(config.outputFormat || 'hex')} onChange={(e) => updateConfig('outputFormat', e.target.value)}>
          <option value="hex">十六进制（Hex）</option>
          <option value="base64">Base64</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="sha_hash"
        />
      </div>
    </div>
  )
}


// 时间戳转换器配置
export function TimestampConverterConfig({ config, updateConfig }: ConfigProps) {
  const operation = String(config.operation || 'to_timestamp')
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>操作类型</Label>
        <Select value={operation} onChange={(e) => updateConfig('operation', e.target.value)}>
          <option value="to_timestamp">日期时间 → 时间戳</option>
          <option value="to_datetime">时间戳 → 日期时间</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>输入值</Label>
        <VariableInput
          value={String(config.inputValue || '')}
          onChange={(v) => updateConfig('inputValue', v)}
          placeholder={operation === 'to_timestamp' ? '2024-01-01 12:00:00 (留空=当前时间)' : '1704096000'}
        />
        <p className="text-xs text-muted-foreground">
          {operation === 'to_timestamp' ? '日期时间格式需与下方格式匹配，留空则使用当前时间' : '输入时间戳数值'}
        </p>
      </div>
      <div className="space-y-2">
        <Label>时间戳单位</Label>
        <Select value={String(config.timestampUnit || 'seconds')} onChange={(e) => updateConfig('timestampUnit', e.target.value)}>
          <option value="seconds">秒（Seconds）</option>
          <option value="milliseconds">毫秒（Milliseconds）</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>日期时间格式</Label>
        <VariableInput
          value={String(config.datetimeFormat || '%Y-%m-%d %H:%M:%S')}
          onChange={(v) => updateConfig('datetimeFormat', v)}
          placeholder="%Y-%m-%d %H:%M:%S"
        />
        <p className="text-xs text-muted-foreground">
          Python strftime格式，如：%Y-%m-%d %H:%M:%S
        </p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="timestamp_result"
        />
      </div>
    </div>
  )
}

// RGB转HSV配置
export function RGBToHSVConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label>R (0-255)</Label>
          <VariableInput
            value={String(config.r || '0')}
            onChange={(v) => updateConfig('r', v)}
            placeholder="0"
            type="number"
          />
        </div>
        <div className="space-y-2">
          <Label>G (0-255)</Label>
          <VariableInput
            value={String(config.g || '0')}
            onChange={(v) => updateConfig('g', v)}
            placeholder="0"
            type="number"
          />
        </div>
        <div className="space-y-2">
          <Label>B (0-255)</Label>
          <VariableInput
            value={String(config.b || '0')}
            onChange={(v) => updateConfig('b', v)}
            placeholder="0"
            type="number"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（HSV对象）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="hsv_color"
        />
        <p className="text-xs text-muted-foreground">
          结果包含：h (0-360), s (0-100%), v (0-100%), string
        </p>
      </div>
    </div>
  )
}

// RGB转CMYK配置
export function RGBToCMYKConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label>R (0-255)</Label>
          <VariableInput
            value={String(config.r || '0')}
            onChange={(v) => updateConfig('r', v)}
            placeholder="0"
            type="number"
          />
        </div>
        <div className="space-y-2">
          <Label>G (0-255)</Label>
          <VariableInput
            value={String(config.g || '0')}
            onChange={(v) => updateConfig('g', v)}
            placeholder="0"
            type="number"
          />
        </div>
        <div className="space-y-2">
          <Label>B (0-255)</Label>
          <VariableInput
            value={String(config.b || '0')}
            onChange={(v) => updateConfig('b', v)}
            placeholder="0"
            type="number"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（CMYK对象）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="cmyk_color"
        />
        <p className="text-xs text-muted-foreground">
          结果包含：c, m, y, k (百分比), string
        </p>
      </div>
    </div>
  )
}


// HEX转CMYK配置
export function HEXToCMYKConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>HEX颜色值</Label>
        <VariableInput
          value={String(config.hexColor || '')}
          onChange={(v) => updateConfig('hexColor', v)}
          placeholder="#FF5733 或 FF5733"
        />
        <p className="text-xs text-muted-foreground">
          支持 #RGB、#RRGGBB 格式
        </p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名（CMYK对象）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="cmyk_color"
        />
        <p className="text-xs text-muted-foreground">
          结果包含：c, m, y, k (百分比), string
        </p>
      </div>
    </div>
  )
}

// UUID生成器配置
export function UUIDGeneratorConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>UUID版本</Label>
        <Select value={String(config.uuidVersion || '4')} onChange={(e) => updateConfig('uuidVersion', e.target.value)}>
          <option value="1">UUID v1（基于时间戳）</option>
          <option value="4">UUID v4（随机生成）</option>
          <option value="3">UUID v3（基于MD5哈希）</option>
          <option value="5">UUID v5（基于SHA1哈希）</option>
        </Select>
      </div>
      {(config.uuidVersion === '3' || config.uuidVersion === '5' || config.uuidVersion === 3 || config.uuidVersion === 5) && (
        <>
          <div className="space-y-2">
            <Label>命名空间</Label>
            <Select value={String(config.namespace || 'dns')} onChange={(e) => updateConfig('namespace', e.target.value)}>
              <option value="dns">DNS</option>
              <option value="url">URL</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>名称</Label>
            <VariableInput
              value={String(config.name || '')}
              onChange={(v) => updateConfig('name', v)}
              placeholder="example.com"
            />
          </div>
        </>
      )}
      <div className="space-y-3">
        <Label>格式选项</Label>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="uppercase"
            checked={config.uppercase === true}
            onCheckedChange={(checked) => updateConfig('uppercase', checked)}
          />
          <Label htmlFor="uppercase" className="cursor-pointer">大写字母</Label>
        </div>
        <div className="flex items-center space-x-2">
          <Checkbox
            id="removeHyphens"
            checked={config.removeHyphens === true}
            onCheckedChange={(checked) => updateConfig('removeHyphens', checked)}
          />
          <Label htmlFor="removeHyphens" className="cursor-pointer">移除连字符</Label>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="generated_uuid"
        />
      </div>
    </div>
  )
}

// 打印机调用配置
export function PrinterCallConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.filePath || '')}
            onChange={(v) => updateConfig('filePath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'filePath', '文档文件|*.pdf;*.docx;*.doc;*.jpg;*.png')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          支持 PDF、Word、图片等格式
        </p>
      </div>
      <div className="space-y-2">
        <Label>打印机名称（可选）</Label>
        <VariableInput
          value={String(config.printerName || '')}
          onChange={(v) => updateConfig('printerName', v)}
          placeholder="留空使用默认打印机"
        />
      </div>
      <div className="space-y-2">
        <Label>打印份数</Label>
        <VariableInput
          value={String(config.copies || '1')}
          onChange={(v) => updateConfig('copies', v)}
          placeholder="1"
          type="number"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>颜色模式</Label>
          <Select value={String(config.colorMode || 'color')} onChange={(e) => updateConfig('colorMode', e.target.value)}>
            <option value="color">彩色</option>
            <option value="grayscale">黑白</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>双面打印</Label>
          <Select value={String(config.duplex || 'none')} onChange={(e) => updateConfig('duplex', e.target.value)}>
            <option value="none">单面</option>
            <option value="long_edge">双面（长边翻转）</option>
            <option value="short_edge">双面（短边翻转）</option>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>纸张方向</Label>
          <Select value={String(config.orientation || 'portrait')} onChange={(e) => updateConfig('orientation', e.target.value)}>
            <option value="portrait">纵向</option>
            <option value="landscape">横向</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>纸张大小</Label>
          <Select value={String(config.paperSize || 'A4')} onChange={(e) => updateConfig('paperSize', e.target.value)}>
            <option value="A4">A4</option>
            <option value="A3">A3</option>
            <option value="A5">A5</option>
            <option value="Letter">Letter</option>
            <option value="Legal">Legal</option>
          </Select>
        </div>
      </div>
    </div>
  )
}
