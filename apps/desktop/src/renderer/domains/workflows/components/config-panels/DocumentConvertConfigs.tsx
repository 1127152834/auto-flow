// Source: WebRPA@5ccb900e, components/workflow/config-panels/DocumentConvertConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { Checkbox } from '../controls/checkbox'
import { FolderOpen } from 'lucide-react'
import { Button } from '../controls/button'
import { systemApi } from '../../api'
import { ImagePathInput } from '../controls/image-path-input'

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

// 选择保存文件夹的辅助函数（用于输出路径，让用户可视化选择保存目录）
const selectSaveFolder = async (updateConfig: (key: string, value: unknown) => void, key: string) => {
  try {
    const result = await systemApi.selectFolder('选择保存文件夹')
    const inner = result.data as any
    if (inner?.success && inner?.path) {
      updateConfig(key, inner.path)
    }
  } catch (error) {
    console.error('选择文件夹失败:', error)
  }
}

/** 输出路径输入框：VariableInput + 文件夹选择按钮（统一样式） */
function OutputPathField({
  config,
  updateConfig,
  fieldKey = 'outputPath',
  placeholder = '留空则自动生成',
}: ConfigProps & { fieldKey?: string; placeholder?: string }) {
  return (
    <div className="flex gap-2">
      <VariableInput
        value={String(config[fieldKey] || '')}
        onChange={(v) => updateConfig(fieldKey, v)}
        placeholder={placeholder}
        className="flex-1"
      />
      <Button type="button" variant="tonal-warning" size="icon" title="选择保存文件夹" onClick={() => selectSaveFolder(updateConfig, fieldKey)}>
        <FolderOpen className="w-4 h-4" />
      </Button>
    </div>
  )
}

// Markdown转HTML配置
export function MarkdownToHTMLConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Markdown文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/readme.md"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Markdown文件|*.md')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出HTML文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="standalone"
          checked={config.standalone !== false}
          onCheckedChange={(checked) => updateConfig('standalone', checked)}
        />
        <Label htmlFor="standalone" className="cursor-pointer">生成完整HTML文档</Label>
      </div>
      <div className="space-y-2">
        <Label>CSS样式文件（可选）</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.cssFile || '')}
            onChange={(v) => updateConfig('cssFile', v)}
            placeholder="C:/styles/custom.css"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'cssFile', 'CSS文件|*.css')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="html_output"
        />
      </div>
    </div>
  )
}

// HTML转Markdown配置
export function HTMLToMarkdownConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入HTML文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/page.html"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'HTML文件|*.html;*.htm')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出Markdown文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="wrapText"
          checked={config.wrapText !== false}
          onCheckedChange={(checked) => updateConfig('wrapText', checked)}
        />
        <Label htmlFor="wrapText" className="cursor-pointer">自动换行</Label>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="markdown_output"
        />
      </div>
    </div>
  )
}

// Markdown转PDF配置
export function MarkdownToPDFConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Markdown文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/readme.md"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Markdown文件|*.md')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出PDF文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="space-y-2">
        <Label>PDF引擎</Label>
        <Select value={String(config.pdfEngine || 'pdflatex')} onChange={(e) => updateConfig('pdfEngine', e.target.value)}>
          <option value="pdflatex">pdflatex</option>
          <option value="xelatex">xelatex（支持中文）</option>
          <option value="lualatex">lualatex</option>
        </Select>
        <p className="text-xs text-muted-foreground">需要安装LaTeX环境（如MiKTeX）</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="pdf_output"
        />
      </div>
    </div>
  )
}

// Markdown转Word配置
export function MarkdownToDocxConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Markdown文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/readme.md"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Markdown文件|*.md')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出Word文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="space-y-2">
        <Label>参考文档（样式模板，可选）</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.referenceDoc || '')}
            onChange={(v) => updateConfig('referenceDoc', v)}
            placeholder="C:/templates/template.docx"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'referenceDoc', 'Word文件|*.docx')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="docx_output"
        />
      </div>
    </div>
  )
}

// Word转Markdown配置
export function DocxToMarkdownConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Word文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/document.docx"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Word文件|*.docx')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出Markdown文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="extractMedia"
          checked={config.extractMedia !== false}
          onCheckedChange={(checked) => updateConfig('extractMedia', checked)}
        />
        <Label htmlFor="extractMedia" className="cursor-pointer">提取媒体文件</Label>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="markdown_output"
        />
      </div>
    </div>
  )
}

// HTML转Word配置
export function HTMLToDocxConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入HTML文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/page.html"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'HTML文件|*.html;*.htm')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出Word文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="docx_output"
        />
      </div>
    </div>
  )
}

// Word转HTML配置
export function DocxToHTMLConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Word文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/document.docx"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Word文件|*.docx')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出HTML文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="standalone"
          checked={config.standalone !== false}
          onCheckedChange={(checked) => updateConfig('standalone', checked)}
        />
        <Label htmlFor="standalone" className="cursor-pointer">生成完整HTML文档</Label>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="html_output"
        />
      </div>
    </div>
  )
}

// Markdown转EPUB配置
export function MarkdownToEPUBConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Markdown文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/book.md"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Markdown文件|*.md')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出EPUB文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="space-y-2">
        <Label>书名（可选）</Label>
        <VariableInput
          value={String(config.title || '')}
          onChange={(v) => updateConfig('title', v)}
          placeholder="我的电子书"
        />
      </div>
      <div className="space-y-2">
        <Label>作者（可选）</Label>
        <VariableInput
          value={String(config.author || '')}
          onChange={(v) => updateConfig('author', v)}
          placeholder="作者名"
        />
      </div>
      <div className="space-y-2">
        <Label>封面图片（可选）</Label>
        <ImagePathInput
          value={String(config.coverImage || '')}
          onChange={(v) => updateConfig('coverImage', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="epub_output"
        />
      </div>
    </div>
  )
}

// EPUB转Markdown配置
export function EPUBToMarkdownConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入EPUB文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/books/book.epub"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'EPUB文件|*.epub')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出Markdown文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="markdown_output"
        />
      </div>
    </div>
  )
}

// LaTeX转PDF配置
export function LaTeXToPDFConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入LaTeX文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/paper.tex"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'LaTeX文件|*.tex')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出PDF文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="space-y-2">
        <Label>PDF引擎</Label>
        <Select value={String(config.pdfEngine || 'pdflatex')} onChange={(e) => updateConfig('pdfEngine', e.target.value)}>
          <option value="pdflatex">pdflatex</option>
          <option value="xelatex">xelatex（支持中文）</option>
          <option value="lualatex">lualatex</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="pdf_output"
        />
      </div>
    </div>
  )
}

// RST转HTML配置
export function RSTToHTMLConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入RST文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/readme.rst"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'RST文件|*.rst')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出HTML文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="standalone"
          checked={config.standalone !== false}
          onCheckedChange={(checked) => updateConfig('standalone', checked)}
        />
        <Label htmlFor="standalone" className="cursor-pointer">生成完整HTML文档</Label>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="html_output"
        />
      </div>
    </div>
  )
}

// Org转HTML配置
export function OrgToHTMLConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入Org文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/notes.org"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath', 'Org文件|*.org')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出HTML文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="standalone"
          checked={config.standalone !== false}
          onCheckedChange={(checked) => updateConfig('standalone', checked)}
        />
        <Label htmlFor="standalone" className="cursor-pointer">生成完整HTML文档</Label>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="html_output"
        />
      </div>
    </div>
  )
}

// 通用文档转换配置
export function UniversalDocConvertConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.inputPath || '')}
            onChange={(v) => updateConfig('inputPath', v)}
            placeholder="C:/docs/document.md"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'inputPath')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出文件（可选）</Label>
        <OutputPathField config={config} updateConfig={updateConfig} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>源格式（可选）</Label>
          <VariableInput
            value={String(config.fromFormat || '')}
            onChange={(v) => updateConfig('fromFormat', v)}
            placeholder="如 markdown, html"
          />
          <p className="text-xs text-muted-foreground">留空自动检测</p>
        </div>
        <div className="space-y-2">
          <Label>目标格式</Label>
          <VariableInput
            value={String(config.toFormat || '')}
            onChange={(v) => updateConfig('toFormat', v)}
            placeholder="如 html, pdf, docx"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>额外选项（可选）</Label>
        <VariableInput
          value={String(config.extraOptions || '')}
          onChange={(v) => updateConfig('extraOptions', v)}
          placeholder="如 --standalone --toc"
        />
        <p className="text-xs text-muted-foreground">Pandoc命令行参数，空格分隔</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="convert_output"
        />
      </div>
    </div>
  )
}
