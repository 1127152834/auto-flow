// Source: WebRPA@5ccb900e, components/workflow/config-panels/PDFModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Input } from '../controls/input'
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

// 选择文件夹的辅助函数（统一走 systemApi.selectFolder，避免各处重复实现导致 bug）
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

// PDF转图片配置
export function PDFToImagesConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出目录（可选）</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.outputDir || '')}
            onChange={(v) => updateConfig('outputDir', v)}
            placeholder="留空则保存到PDF所在目录"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'outputDir')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>DPI（分辨率）</Label>
          <Input
            type="number"
            value={config.dpi as number || 150}
            onChange={(e) => updateConfig('dpi', parseInt(e.target.value) || 150)}
            min={72}
            max={600}
          />
        </div>
        <div className="space-y-2">
          <Label>图片格式</Label>
          <Select value={String(config.imageFormat || 'png')} onChange={(e) => updateConfig('imageFormat', e.target.value)}>
            <option value="png">PNG</option>
            <option value="jpg">JPG</option>
            <option value="webp">WebP</option>
          </Select>
        </div>
      </div>
      <div className="space-y-2">
        <Label>页面范围（可选）</Label>
        <VariableInput
          value={String(config.pageRange || '')}
          onChange={(v) => updateConfig('pageRange', v)}
          placeholder="如 1-5 或 1,3,5 留空转换所有页"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="pdf_images"
        />
      </div>
    </div>
  )
}

// 图片转PDF配置
export function ImagesToPDFConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>图片列表</Label>
        <VariableInput
          value={String(config.images || '')}
          onChange={(v) => updateConfig('images', v)}
          placeholder="图片路径列表变量或逗号分隔的路径"
          multiline
          rows={3}
        />
        <p className="text-xs text-muted-foreground">支持变量引用列表，或逗号分隔的多个路径</p>
      </div>
      <div className="space-y-2">
        <Label>输出PDF路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.outputPath || '')}
            onChange={(v) => updateConfig('outputPath', v)}
            placeholder="C:/output/result.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'outputPath')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>页面尺寸</Label>
        <Select value={String(config.pageSize || 'A4')} onChange={(e) => updateConfig('pageSize', e.target.value)}>
          <option value="A4">A4</option>
          <option value="A3">A3</option>
          <option value="Letter">Letter</option>
          <option value="Legal">Legal</option>
          <option value="original">原始尺寸</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="pdf_result"
        />
      </div>
    </div>
  )
}

// PDF合并配置
export function PDFMergeConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件列表</Label>
        <VariableInput
          value={String(config.pdfFiles || '')}
          onChange={(v) => updateConfig('pdfFiles', v)}
          placeholder="PDF路径列表变量或逗号分隔的路径"
          multiline
          rows={3}
        />
        <p className="text-xs text-muted-foreground">至少需要2个PDF文件</p>
      </div>
      <div className="space-y-2">
        <Label>输出PDF路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.outputPath || '')}
            onChange={(v) => updateConfig('outputPath', v)}
            placeholder="C:/output/merged.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'outputPath')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="merged_pdf"
        />
      </div>
    </div>
  )
}

// PDF拆分配置
export function PDFSplitConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出目录</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.outputDir || '')}
            onChange={(v) => updateConfig('outputDir', v)}
            placeholder="留空则保存到PDF所在目录"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'outputDir')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>拆分模式</Label>
        <Select value={String(config.splitMode || 'single')} onChange={(e) => updateConfig('splitMode', e.target.value)}>
          <option value="single">每页一个PDF</option>
          <option value="range">按范围拆分</option>
        </Select>
      </div>
      {config.splitMode === 'range' && (
        <div className="space-y-2">
          <Label>页面范围</Label>
          <VariableInput
            value={String(config.pageRanges || '')}
            onChange={(v) => updateConfig('pageRanges', v)}
            placeholder="如 1-3,4-6,7-10"
          />
        </div>
      )}
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="split_pdfs"
        />
      </div>
    </div>
  )
}

// PDF提取文本配置
export function PDFExtractTextConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>页面范围（可选）</Label>
        <VariableInput
          value={String(config.pageRange || '')}
          onChange={(v) => updateConfig('pageRange', v)}
          placeholder="如 1-5 或 1,3,5 留空提取所有页"
        />
      </div>
      <div className="space-y-2">
        <Label>保存到文件（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则只保存到变量"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="pdf_text"
        />
      </div>
    </div>
  )
}

// PDF提取图片配置
export function PDFExtractImagesConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出目录</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.outputDir || '')}
            onChange={(v) => updateConfig('outputDir', v)}
            placeholder="留空则保存到PDF所在目录"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'outputDir')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>最小图片尺寸（像素）</Label>
        <Input
          type="number"
          value={config.minSize as number || 100}
          onChange={(e) => updateConfig('minSize', parseInt(e.target.value) || 100)}
          min={1}
        />
        <p className="text-xs text-muted-foreground">过滤小于此尺寸的图片</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="extracted_images"
        />
      </div>
    </div>
  )
}


// PDF加密配置
export function PDFEncryptConfig({ config, updateConfig }: ConfigProps) {
  const permissions = (config.permissions || {}) as Record<string, boolean>
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>打开密码（用户密码）</Label>
        <VariableInput
          value={String(config.userPassword || '')}
          onChange={(v) => updateConfig('userPassword', v)}
          placeholder="打开PDF时需要输入的密码"
        />
      </div>
      <div className="space-y-2">
        <Label>权限密码（所有者密码）</Label>
        <VariableInput
          value={String(config.ownerPassword || '')}
          onChange={(v) => updateConfig('ownerPassword', v)}
          placeholder="修改权限时需要的密码"
        />
      </div>
      <div className="space-y-2">
        <Label>权限设置</Label>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Checkbox
              checked={permissions.print !== false}
              onCheckedChange={(v) => updateConfig('permissions', { ...permissions, print: v })}
            />
            <span className="text-sm">允许打印</span>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              checked={permissions.copy !== false}
              onCheckedChange={(v) => updateConfig('permissions', { ...permissions, copy: v })}
            />
            <span className="text-sm">允许复制</span>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              checked={permissions.modify === true}
              onCheckedChange={(v) => updateConfig('permissions', { ...permissions, modify: v })}
            />
            <span className="text-sm">允许修改</span>
          </div>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="encrypted_pdf"
        />
      </div>
    </div>
  )
}

// PDF解密配置
export function PDFDecryptConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/encrypted.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>密码</Label>
        <VariableInput
          value={String(config.password || '')}
          onChange={(v) => updateConfig('password', v)}
          placeholder="PDF的密码"
        />
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="decrypted_pdf"
        />
      </div>
    </div>
  )
}

// PDF添加水印配置
export function PDFAddWatermarkConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>水印类型</Label>
        <Select value={String(config.watermarkType || 'text')} onChange={(e) => updateConfig('watermarkType', e.target.value)}>
          <option value="text">文字水印</option>
          <option value="image">图片水印</option>
        </Select>
      </div>
      {config.watermarkType === 'image' ? (
        <div className="space-y-2">
          <Label>水印图片路径</Label>
          <ImagePathInput
            value={String(config.watermarkImage || '')}
            onChange={(v) => updateConfig('watermarkImage', v)}
            placeholder="从图像资源中选择或输入路径"
          />
        </div>
      ) : (
        <div className="space-y-2">
          <Label>水印文字</Label>
          <VariableInput
            value={String(config.watermarkText || '')}
            onChange={(v) => updateConfig('watermarkText', v)}
            placeholder="机密文件"
          />
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>透明度</Label>
          <Input
            type="number"
            value={config.opacity as number || 0.3}
            onChange={(e) => updateConfig('opacity', parseFloat(e.target.value) || 0.3)}
            min={0.1}
            max={1}
            step={0.1}
          />
        </div>
        <div className="space-y-2">
          <Label>旋转角度</Label>
          <Input
            type="number"
            value={config.rotation as number || 45}
            onChange={(e) => updateConfig('rotation', parseInt(e.target.value) || 45)}
            min={-180}
            max={180}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>水印位置</Label>
        <Select value={String(config.position || 'center')} onChange={(e) => updateConfig('position', e.target.value)}>
          <option value="center">居中</option>
          <option value="tile">平铺</option>
          <option value="top-left">左上角</option>
          <option value="top-right">右上角</option>
          <option value="bottom-left">左下角</option>
          <option value="bottom-right">右下角</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="watermarked_pdf"
        />
      </div>
    </div>
  )
}

// PDF旋转配置
export function PDFRotateConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>旋转角度</Label>
        <Select value={String(config.rotation || '90')} onChange={(e) => updateConfig('rotation', parseInt(e.target.value))}>
          <option value="90">顺时针90°</option>
          <option value="180">180°</option>
          <option value="270">逆时针90°</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>页面范围（可选）</Label>
        <VariableInput
          value={String(config.pageRange || '')}
          onChange={(v) => updateConfig('pageRange', v)}
          placeholder="如 1-5 或 1,3,5 留空旋转所有页"
        />
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="rotated_pdf"
        />
      </div>
    </div>
  )
}


// PDF删除页面配置
export function PDFDeletePagesConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>要删除的页面</Label>
        <VariableInput
          value={String(config.pages || '')}
          onChange={(v) => updateConfig('pages', v)}
          placeholder="如 1,3,5 或 2-4"
        />
        <p className="text-xs text-muted-foreground">支持单页、多页和范围，如: 1,3,5-8</p>
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="result_pdf"
        />
      </div>
    </div>
  )
}

// PDF获取信息配置
export function PDFGetInfoConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="pdf_info"
        />
        <p className="text-xs text-muted-foreground">返回包含页数、标题、作者等信息的对象</p>
      </div>
    </div>
  )
}

// PDF压缩配置
export function PDFCompressConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>压缩质量</Label>
        <Select value={String(config.quality || 'medium')} onChange={(e) => updateConfig('quality', e.target.value)}>
          <option value="high">高质量（压缩率低）</option>
          <option value="medium">中等质量</option>
          <option value="low">低质量（压缩率高）</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="compressed_pdf"
        />
      </div>
    </div>
  )
}

// PDF插入页面配置
export function PDFInsertPagesConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>目标PDF文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.targetPdf || '')}
            onChange={(v) => updateConfig('targetPdf', v)}
            placeholder="C:/documents/target.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'targetPdf', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>要插入的PDF文件</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.sourcePdf || '')}
            onChange={(v) => updateConfig('sourcePdf', v)}
            placeholder="C:/documents/source.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'sourcePdf', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>插入位置（页码）</Label>
        <Input
          type="number"
          value={config.insertAt as number || 1}
          onChange={(e) => updateConfig('insertAt', parseInt(e.target.value) || 1)}
          min={0}
        />
        <p className="text-xs text-muted-foreground">在第几页之后插入，0表示插入到开头</p>
      </div>
      <div className="space-y-2">
        <Label>要插入的页面范围（可选）</Label>
        <VariableInput
          value={String(config.sourcePages || '')}
          onChange={(v) => updateConfig('sourcePages', v)}
          placeholder="如 1-3 或 1,2,5 留空插入所有页"
        />
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="result_pdf"
        />
      </div>
    </div>
  )
}

// PDF重排页面配置
export function PDFReorderPagesConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>新的页面顺序</Label>
        <VariableInput
          value={String(config.pageOrder || '')}
          onChange={(v) => updateConfig('pageOrder', v)}
          placeholder="如 3,1,2,5,4 表示新顺序"
        />
        <p className="text-xs text-muted-foreground">用逗号分隔的页码，表示新的页面顺序</p>
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="reordered_pdf"
        />
      </div>
    </div>
  )
}

// PDF添加页眉页脚配置
export function PDFAddHeaderFooterConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>页眉文字（可选）</Label>
        <VariableInput
          value={String(config.headerText || '')}
          onChange={(v) => updateConfig('headerText', v)}
          placeholder="文档标题"
        />
      </div>
      <div className="space-y-2">
        <Label>页脚文字（可选）</Label>
        <VariableInput
          value={String(config.footerText || '')}
          onChange={(v) => updateConfig('footerText', v)}
          placeholder="第 {page} 页 / 共 {total} 页"
        />
        <p className="text-xs text-muted-foreground">支持 {'{page}'} 和 {'{total}'} 占位符</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>字体大小</Label>
          <Input
            type="number"
            value={config.fontSize as number || 10}
            onChange={(e) => updateConfig('fontSize', parseInt(e.target.value) || 10)}
            min={6}
            max={24}
          />
        </div>
        <div className="space-y-2">
          <Label>对齐方式</Label>
          <Select value={String(config.alignment || 'center')} onChange={(e) => updateConfig('alignment', e.target.value)}>
            <option value="left">左对齐</option>
            <option value="center">居中</option>
            <option value="right">右对齐</option>
          </Select>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出路径（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="result_pdf"
        />
      </div>
    </div>
  )
}


// PDF转Word配置
export function PDFToWordConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>PDF文件路径</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.pdfPath || '')}
            onChange={(v) => updateConfig('pdfPath', v)}
            placeholder="C:/documents/file.pdf"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFile(updateConfig, 'pdfPath', 'PDF文件|*.pdf')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出目录（可选）</Label>
        <div className="flex gap-2">
          <VariableInput
            value={String(config.outputDir || '')}
            onChange={(v) => updateConfig('outputDir', v)}
            placeholder="留空则保存到PDF所在目录"
            className="flex-1"
          />
          <Button type="button" variant="tonal-warning" size="icon" onClick={() => selectFolder(updateConfig, 'outputDir')}>
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <Label>输出格式</Label>
        <Select value={String(config.outputFormat || 'docx')} onChange={(e) => updateConfig('outputFormat', e.target.value)}>
          <option value="docx">DOCX (Word 2007+)</option>
          <option value="doc">DOC (Word 97-2003)</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>页面范围（可选）</Label>
        <VariableInput
          value={String(config.pageRange || '')}
          onChange={(v) => updateConfig('pageRange', v)}
          placeholder="如 1-5 或 1,3,5 留空转换所有页"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="word_file"
        />
      </div>
    </div>
  )
}
