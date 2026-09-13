// Source: WebRPA@5ccb900e, components/workflow/config-panels/PillowImageConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Input } from '../controls/input'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { Checkbox } from '../controls/checkbox'
import { ImagePathInput } from '../controls/image-path-input'

interface ConfigProps {
  config: Record<string, unknown>
  updateConfig: (key: string, value: unknown) => void
}

// 图像缩放配置
export function ImageResizeConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>宽度（像素）</Label>
          <Input
            type="number"
            value={config.width as number || 0}
            onChange={(e) => updateConfig('width', parseInt(e.target.value) || 0)}
            placeholder="0表示不限制"
            min={0}
          />
        </div>
        <div className="space-y-2">
          <Label>高度（像素）</Label>
          <Input
            type="number"
            value={config.height as number || 0}
            onChange={(e) => updateConfig('height', parseInt(e.target.value) || 0)}
            placeholder="0表示不限制"
            min={0}
          />
        </div>
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="keepAspect"
          checked={config.keepAspect !== false}
          onCheckedChange={(checked) => updateConfig('keepAspect', checked)}
        />
        <Label htmlFor="keepAspect" className="cursor-pointer">保持宽高比</Label>
      </div>
      <div className="space-y-2">
        <Label>重采样算法</Label>
        <Select value={String(config.resample || 'LANCZOS')} onChange={(e) => updateConfig('resample', e.target.value)}>
          <option value="LANCZOS">LANCZOS（高质量）</option>
          <option value="BILINEAR">BILINEAR（双线性）</option>
          <option value="BICUBIC">BICUBIC（双三次）</option>
          <option value="NEAREST">NEAREST（最近邻）</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="resized_image"
        />
      </div>
    </div>
  )
}

// 图像裁剪配置
export function ImageCropConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>左上角X坐标</Label>
          <Input
            type="number"
            value={config.left as number || 0}
            onChange={(e) => updateConfig('left', parseInt(e.target.value) || 0)}
            min={0}
          />
        </div>
        <div className="space-y-2">
          <Label>左上角Y坐标</Label>
          <Input
            type="number"
            value={config.top as number || 0}
            onChange={(e) => updateConfig('top', parseInt(e.target.value) || 0)}
            min={0}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>右下角X坐标</Label>
          <Input
            type="number"
            value={config.right as number || 0}
            onChange={(e) => updateConfig('right', parseInt(e.target.value) || 0)}
            placeholder="0表示图像宽度"
            min={0}
          />
        </div>
        <div className="space-y-2">
          <Label>右下角Y坐标</Label>
          <Input
            type="number"
            value={config.bottom as number || 0}
            onChange={(e) => updateConfig('bottom', parseInt(e.target.value) || 0)}
            placeholder="0表示图像高度"
            min={0}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="cropped_image"
        />
      </div>
    </div>
  )
}

// 图像旋转配置
export function ImageRotateConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>旋转角度（度）</Label>
        <Input
          type="number"
          value={config.angle as number || 0}
          onChange={(e) => updateConfig('angle', parseFloat(e.target.value) || 0)}
          placeholder="正数逆时针，负数顺时针"
          step={0.1}
        />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="expand"
          checked={config.expand !== false}
          onCheckedChange={(checked) => updateConfig('expand', checked)}
        />
        <Label htmlFor="expand" className="cursor-pointer">扩展画布以容纳旋转后的图像</Label>
      </div>
      <div className="space-y-2">
        <Label>填充颜色</Label>
        <VariableInput
          value={String(config.fillColor || 'white')}
          onChange={(v) => updateConfig('fillColor', v)}
          placeholder="white, black, #FF0000"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="rotated_image"
        />
      </div>
    </div>
  )
}

// 图像翻转配置
export function ImageFlipConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>翻转模式</Label>
        <Select value={String(config.flipMode || 'horizontal')} onChange={(e) => updateConfig('flipMode', e.target.value)}>
          <option value="horizontal">水平翻转</option>
          <option value="vertical">垂直翻转</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="flipped_image"
        />
      </div>
    </div>
  )
}

// 图像模糊配置
export function ImageBlurConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>模糊半径</Label>
        <Input
          type="number"
          value={config.radius as number || 2}
          onChange={(e) => updateConfig('radius', parseInt(e.target.value) || 2)}
          min={1}
          max={50}
        />
        <p className="text-xs text-muted-foreground">值越大模糊效果越强</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="blurred_image"
        />
      </div>
    </div>
  )
}

// 图像锐化配置
export function ImageSharpenConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>锐化因子</Label>
        <Input
          type="number"
          value={config.factor as number || 2.0}
          onChange={(e) => updateConfig('factor', parseFloat(e.target.value) || 2.0)}
          step={0.1}
          min={0}
          max={10}
        />
        <p className="text-xs text-muted-foreground">1.0=原始，&gt;1.0=更锐利</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="sharpened_image"
        />
      </div>
    </div>
  )
}

// 图像亮度配置
export function ImageBrightnessConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>亮度因子</Label>
        <Input
          type="number"
          value={config.factor as number || 1.0}
          onChange={(e) => updateConfig('factor', parseFloat(e.target.value) || 1.0)}
          step={0.1}
          min={0}
          max={3}
        />
        <p className="text-xs text-muted-foreground">0.0=全黑，1.0=原始，&gt;1.0=更亮</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="brightness_image"
        />
      </div>
    </div>
  )
}

// 图像对比度配置
export function ImageContrastConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>对比度因子</Label>
        <Input
          type="number"
          value={config.factor as number || 1.0}
          onChange={(e) => updateConfig('factor', parseFloat(e.target.value) || 1.0)}
          step={0.1}
          min={0}
          max={3}
        />
        <p className="text-xs text-muted-foreground">1.0=原始，&gt;1.0=对比度更高</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="contrast_image"
        />
      </div>
    </div>
  )
}

// 图像色彩平衡配置
export function ImageColorBalanceConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>色彩因子</Label>
        <Input
          type="number"
          value={config.factor as number || 1.0}
          onChange={(e) => updateConfig('factor', parseFloat(e.target.value) || 1.0)}
          step={0.1}
          min={0}
          max={3}
        />
        <p className="text-xs text-muted-foreground">0.0=灰度，1.0=原始，&gt;1.0=色彩更鲜艳</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="color_image"
        />
      </div>
    </div>
  )
}


// 图像格式转换配置
export function ImageConvertFormatConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>输出格式</Label>
        <Select value={String(config.outputFormat || 'PNG')} onChange={(e) => updateConfig('outputFormat', e.target.value)}>
          <option value="PNG">PNG</option>
          <option value="JPEG">JPEG</option>
          <option value="BMP">BMP</option>
          <option value="GIF">GIF</option>
          <option value="TIFF">TIFF</option>
          <option value="WEBP">WEBP</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>JPEG质量（仅JPEG格式）</Label>
        <Input
          type="number"
          value={config.quality as number || 95}
          onChange={(e) => updateConfig('quality', parseInt(e.target.value) || 95)}
          min={1}
          max={100}
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="converted_image"
        />
      </div>
    </div>
  )
}

// 图像添加文字配置
export function ImageAddTextConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>文字内容</Label>
        <VariableInput
          value={String(config.text || '')}
          onChange={(v) => updateConfig('text', v)}
          placeholder="© 2026 青云制作_彭明航"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>X坐标</Label>
          <Input
            type="number"
            value={config.positionX as number || 10}
            onChange={(e) => updateConfig('positionX', parseInt(e.target.value) || 10)}
            min={0}
          />
        </div>
        <div className="space-y-2">
          <Label>Y坐标</Label>
          <Input
            type="number"
            value={config.positionY as number || 10}
            onChange={(e) => updateConfig('positionY', parseInt(e.target.value) || 10)}
            min={0}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>字体大小</Label>
          <Input
            type="number"
            value={config.fontSize as number || 20}
            onChange={(e) => updateConfig('fontSize', parseInt(e.target.value) || 20)}
            min={1}
          />
        </div>
        <div className="space-y-2">
          <Label>字体颜色</Label>
          <VariableInput
            value={String(config.fontColor || 'black')}
            onChange={(v) => updateConfig('fontColor', v)}
            placeholder="black, white, #FF0000"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="text_image"
        />
      </div>
    </div>
  )
}

// 图像拼接配置
export function ImageMergeConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>图像路径列表</Label>
        <VariableInput
          value={String(config.imagePaths || '')}
          onChange={(v) => updateConfig('imagePaths', v)}
          placeholder="C:/img1.jpg,C:/img2.jpg,C:/img3.jpg"
          multiline
          rows={3}
        />
        <p className="text-xs text-muted-foreground">逗号分隔的多个图像路径</p>
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>拼接方向</Label>
        <Select value={String(config.direction || 'horizontal')} onChange={(e) => updateConfig('direction', e.target.value)}>
          <option value="horizontal">水平拼接</option>
          <option value="vertical">垂直拼接</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>图像间距（像素）</Label>
        <Input
          type="number"
          value={config.spacing as number || 0}
          onChange={(e) => updateConfig('spacing', parseInt(e.target.value) || 0)}
          min={0}
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="merged_image"
        />
      </div>
    </div>
  )
}

// 生成缩略图配置
export function ImageThumbnailConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>最大尺寸（像素）</Label>
        <Input
          type="number"
          value={config.maxSize as number || 128}
          onChange={(e) => updateConfig('maxSize', parseInt(e.target.value) || 128)}
          min={16}
          max={1024}
        />
        <p className="text-xs text-muted-foreground">保持宽高比，最长边不超过此值</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="thumbnail_image"
        />
      </div>
    </div>
  )
}

// 图像滤镜配置
export function ImageFilterConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成"
        />
      </div>
      <div className="space-y-2">
        <Label>滤镜类型</Label>
        <Select value={String(config.filterType || 'BLUR')} onChange={(e) => updateConfig('filterType', e.target.value)}>
          <option value="BLUR">模糊</option>
          <option value="CONTOUR">轮廓</option>
          <option value="DETAIL">细节增强</option>
          <option value="EDGE_ENHANCE">边缘增强</option>
          <option value="EDGE_ENHANCE_MORE">边缘增强（强）</option>
          <option value="EMBOSS">浮雕</option>
          <option value="FIND_EDGES">查找边缘</option>
          <option value="SMOOTH">平滑</option>
          <option value="SMOOTH_MORE">平滑（强）</option>
          <option value="SHARPEN">锐化</option>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="filtered_image"
        />
      </div>
    </div>
  )
}

// 获取图像信息配置
export function ImageGetInfoConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="image_info"
        />
        <p className="text-xs text-muted-foreground">返回包含尺寸、格式、文件大小等信息的字典</p>
      </div>
    </div>
  )
}

// 简单去背景配置
export function ImageRemoveBgConfig({ config, updateConfig }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>输入图像</Label>
        <ImagePathInput
          value={String(config.inputPath || '')}
          onChange={(v) => updateConfig('inputPath', v)}
          placeholder="从图像资源中选择或输入路径"
        />
      </div>
      <div className="space-y-2">
        <Label>输出图像（可选）</Label>
        <VariableInput
          value={String(config.outputPath || '')}
          onChange={(v) => updateConfig('outputPath', v)}
          placeholder="留空则自动生成PNG"
        />
      </div>
      <div className="space-y-2">
        <Label>背景颜色</Label>
        <Select value={String(config.bgColor || 'white')} onChange={(e) => updateConfig('bgColor', e.target.value)}>
          <option value="white">白色</option>
          <option value="black">黑色</option>
          <option value="red">红色</option>
          <option value="green">绿色</option>
          <option value="blue">蓝色</option>
        </Select>
        <p className="text-xs text-muted-foreground">或输入RGB值，如"255,255,255"</p>
      </div>
      <div className="space-y-2">
        <Label>容差</Label>
        <Input
          type="number"
          value={config.tolerance as number || 30}
          onChange={(e) => updateConfig('tolerance', parseInt(e.target.value) || 30)}
          min={0}
          max={255}
        />
        <p className="text-xs text-muted-foreground">值越大，移除的颜色范围越广</p>
      </div>
      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={String(config.resultVariable || '')}
          onChange={(v) => updateConfig('resultVariable', v)}
          placeholder="nobg_image"
        />
      </div>
    </div>
  )
}
