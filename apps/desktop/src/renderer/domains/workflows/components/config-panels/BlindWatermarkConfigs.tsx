// Source: WebRPA@5ccb900e, components/workflow/config-panels/BlindWatermarkConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 盲水印（blind_watermark）配置面板
 *
 * 4 个模块共用一组类似的配置项：
 *  - imagePath          原图（嵌入时是载体图，提取时是带水印的图）
 *  - outputPath         嵌入/提取结果的输出路径
 *  - text               文本水印内容（仅 bwm_embed_text）
 *  - watermarkPath      水印图路径（仅 bwm_embed_image）
 *  - wmBitLen / wmH/W   提取需要的尺寸信息
 *  - passwordWm         水印置乱密码（默认 1）
 *  - passwordImg        图像置乱密码（默认 1）
 *  - resultVariable     结果变量名
 */
import { Label } from '../controls/label'
import { Input } from '../controls/input'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { ImagePathInput } from '../controls/image-path-input'
import { PathInput } from '../controls/path-input'

interface ConfigProps {
  config: Record<string, unknown>
  updateConfig: (key: string, value: unknown) => void
}

const Hint = ({ children }: { children: React.ReactNode }) => (
  <div className="rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 px-3 py-2 text-[11.5px] leading-relaxed text-[hsl(var(--muted-foreground))]">
    {children}
  </div>
)

function PasswordFields({ config, updateConfig }: ConfigProps) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        <Label>水印密码（password_wm）</Label>
        <Input
          type="number"
          value={(config.passwordWm as number) ?? 1}
          onChange={(e) => updateConfig('passwordWm', parseInt(e.target.value) || 0)}
          placeholder="默认 1"
        />
      </div>
      <div className="space-y-2">
        <Label>图像密码（password_img）</Label>
        <Input
          type="number"
          value={(config.passwordImg as number) ?? 1}
          onChange={(e) => updateConfig('passwordImg', parseInt(e.target.value) || 0)}
          placeholder="默认 1"
        />
      </div>
    </div>
  )
}

// ===== 嵌入文字水印 =====
export function BwmEmbedTextConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <Hint>
        把一段文本以隐式（肉眼不可见）方式嵌入到原图。导出后再次提取时需要相同的两个密码 + 嵌入返回的 wm_bit_len。
      </Hint>
      <div className="space-y-2">
        <Label>原图路径</Label>
        <ImagePathInput
          value={String(config.imagePath || '')}
          onChange={(v) => updateConfig('imagePath', v)}
          placeholder="选择或输入原图路径"
        />
      </div>
      <div className="space-y-2">
        <Label>水印文本</Label>
        <VariableInput
          value={String(config.text || '')}
          onChange={(v) => updateConfig('text', v)}
          placeholder="例如 © WebRPA"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像路径</Label>
        <PathInput
          type="folder"
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="选文件夹（自动用『原图名_wm.png』）或填完整路径如 D:/photo_wm.png"
          title="选择嵌入水印后图像的保存目录"
        />
      </div>
      <PasswordFields config={config} updateConfig={updateConfig} />
      <div className="space-y-2">
        <Label>结果变量名（保存 wm_bit_len，提取时必须用）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="wm_bit_len"
        />
      </div>
    </div>
  )
}

// ===== 提取文字水印 =====
export function BwmExtractTextConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <Hint>
        从带水印的图像中提取文本。需要：相同的水印密码与图像密码，以及嵌入时返回的 wm_bit_len。
      </Hint>
      <div className="space-y-2">
        <Label>带水印图像路径</Label>
        <ImagePathInput
          value={String(config.imagePath || '')}
          onChange={(v) => updateConfig('imagePath', v)}
        />
      </div>
      <div className="space-y-2">
        <Label>wm_bit_len（来自嵌入时的结果变量）</Label>
        <VariableInput
          value={String(config.wmBitLen ?? '')}
          onChange={(v) => updateConfig('wmBitLen', v)}
          placeholder="{{wm_bit_len}} 或一个具体数字"
        />
      </div>
      <PasswordFields config={config} updateConfig={updateConfig} />
      <div className="space-y-2">
        <Label>结果变量名（保存提取出的文本）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="extracted_text"
        />
      </div>
    </div>
  )
}

// ===== 嵌入图片水印 =====
export function BwmEmbedImageConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <Hint>
        把一张水印图（建议黑白二值图）以隐式方式嵌入到原图。提取时必须知道水印图原尺寸 [h, w]。
      </Hint>
      <div className="space-y-2">
        <Label>原图路径（载体）</Label>
        <ImagePathInput
          value={String(config.imagePath || '')}
          onChange={(v) => updateConfig('imagePath', v)}
        />
      </div>
      <div className="space-y-2">
        <Label>水印图路径</Label>
        <ImagePathInput
          value={String(config.watermarkPath || '')}
          onChange={(v) => updateConfig('watermarkPath', v)}
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像路径</Label>
        <PathInput
          type="folder"
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="选文件夹（自动用『原图名_wm.png』）或填完整路径"
          title="选择嵌入水印后图像的保存目录"
        />
      </div>
      <PasswordFields config={config} updateConfig={updateConfig} />
      <div className="space-y-2">
        <Label>结果变量名（保存水印图尺寸 [h,w]，提取时必须用）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="wm_image_shape"
        />
      </div>
    </div>
  )
}

// ===== 提取图片水印 =====
export function BwmExtractImageConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <Hint>
        从带水印的图像中还原出隐藏的水印图。必须知道水印图的原始高/宽（嵌入时返回的尺寸）。
      </Hint>
      <div className="space-y-2">
        <Label>带水印图像路径</Label>
        <ImagePathInput
          value={String(config.imagePath || '')}
          onChange={(v) => updateConfig('imagePath', v)}
        />
      </div>
      <div className="space-y-2">
        <Label>提取结果输出路径</Label>
        <PathInput
          type="folder"
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="选文件夹（自动用『原图名_extracted.png』）或填完整路径"
          title="选择提取出的水印图保存目录"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>水印高度（h，像素）</Label>
          <VariableInput
            value={String(config.wmHeight ?? '')}
            onChange={(v) => updateConfig('wmHeight', v)}
            placeholder="嵌入时返回的 shape[0]"
          />
        </div>
        <div className="space-y-2">
          <Label>水印宽度（w，像素）</Label>
          <VariableInput
            value={String(config.wmWidth ?? '')}
            onChange={(v) => updateConfig('wmWidth', v)}
            placeholder="嵌入时返回的 shape[1]"
          />
        </div>
      </div>
      <PasswordFields config={config} updateConfig={updateConfig} />
      <div className="space-y-2">
        <Label>结果变量名（保存输出文件路径）</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="extracted_wm_path"
        />
      </div>
    </div>
  )
}
