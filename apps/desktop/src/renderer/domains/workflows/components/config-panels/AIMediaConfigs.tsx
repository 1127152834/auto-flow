// Source: WebRPA@5ccb900e, components/workflow/config-panels/AIMediaConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../controls/select'
import { Textarea } from '../controls/textarea'
import { VariableInput } from '../controls/variable-input'
import { PathInput } from '../controls/path-input'
import { ImagePathInput } from '../controls/image-path-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { NumberInput } from '../controls/number-input'
import type { NodeData } from '../../editor-store'
import { AIModelPicker } from './AIModuleConfigs'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

interface MediaConfigProps extends ConfigProps {
  onBatchChange: (data: Partial<NodeData>) => void
}

// AI生图配置
export function AIGenerateImageConfig({ data, onChange, onBatchChange }: MediaConfigProps) {
  return (
    <div className="space-y-4">
      <AIModelPicker data={data} onBatchChange={onBatchChange} />

      <div className="space-y-2">
        <Label>接口协议</Label>
        <Select value={(data.provider as string) || 'openai'} onValueChange={(v) => onChange('provider', v)}>
          <SelectTrigger><SelectValue placeholder="选择接口协议" /></SelectTrigger>
          <SelectContent><SelectItem value="openai">OpenAI Images</SelectItem><SelectItem value="stability">Stability AI</SelectItem></SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>提示词</Label>
        <VariableInput
          value={(data.prompt as string) || ''}
          onChange={(value) => onChange('prompt', value)}
          multiline
          placeholder="一只可爱的猫咪在花园里玩耍"
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>负面提示词（可选）</Label>
        <Textarea
          value={(data.negativePrompt as string) || ''}
          onChange={(e) => onChange('negativePrompt', e.target.value)}
          placeholder="低质量，模糊"
          rows={2}
        />
      </div>

      {(data.provider as string) !== 'stability' && <>
        <div className="space-y-2">
          <Label>质量</Label>
          <Select value={(data.quality as string) || 'standard'} onValueChange={(v) => onChange('quality', v)}>
            <SelectTrigger><SelectValue placeholder="选择质量" /></SelectTrigger>
            <SelectContent><SelectItem value="standard">标准</SelectItem><SelectItem value="hd">高清</SelectItem></SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>风格</Label>
          <Select value={(data.style as string) || 'vivid'} onValueChange={(v) => onChange('style', v)}>
            <SelectTrigger><SelectValue placeholder="选择风格" /></SelectTrigger>
            <SelectContent><SelectItem value="vivid">生动</SelectItem><SelectItem value="natural">自然</SelectItem></SelectContent>
          </Select>
        </div>
      </>}

      <div className="space-y-2">
        <Label>图片尺寸</Label>
        <Select
          value={(data.size as string) || '1024x1024'}
          onValueChange={(v) => onChange('size', v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择尺寸" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="256x256">256x256</SelectItem>
            <SelectItem value="512x512">512x512</SelectItem>
            <SelectItem value="1024x1024">1024x1024</SelectItem>
            <SelectItem value="1792x1024">1792x1024</SelectItem>
            <SelectItem value="1024x1792">1024x1792</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>生成数量</Label>
        <NumberInput
          value={(data.n as number) || 1}
          onChange={(v) => onChange('n', v)}
          defaultValue={1}
          min={1}
          max={10}
        />
      </div>

      <div className="space-y-2">
        <Label>保存路径（可选）</Label>
        <ImagePathInput
          value={(data.savePath as string) || ''}
          onChange={(v) => onChange('savePath', v)}
          placeholder="C:/images/output.png"
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'ai_image_urls'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="ai_image_urls"
        />
      </div>
    </div>
  )
}

// AI生视频配置
export function AIGenerateVideoConfig({ data, onChange, onBatchChange }: MediaConfigProps) {
  return (
    <div className="space-y-4">
      <AIModelPicker data={data} onBatchChange={onBatchChange} />

      <div className="space-y-2">
        <Label>接口协议</Label>
        <Select value={(data.provider as string) || 'runway'} onValueChange={(v) => onChange('provider', v)}>
          <SelectTrigger><SelectValue placeholder="选择接口协议" /></SelectTrigger>
          <SelectContent><SelectItem value="runway">Runway 异步接口</SelectItem><SelectItem value="custom">通用同步接口</SelectItem></SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>提示词</Label>
        <VariableInput
          value={(data.prompt as string) || ''}
          onChange={(value) => onChange('prompt', value)}
          multiline
          placeholder="一只猫咪在草地上奔跑"
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <Label>视频时长（秒）</Label>
        <NumberInput
          value={(data.duration as number) || 5}
          onChange={(v) => onChange('duration', v)}
          defaultValue={5}
          min={1}
          max={30}
        />
      </div>

      <div className="space-y-2">
        <Label>宽高比</Label>
        <Select
          value={(data.aspectRatio as string) || '16:9'}
          onValueChange={(v) => onChange('aspectRatio', v)}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择宽高比" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="16:9">16:9</SelectItem>
            <SelectItem value="9:16">9:16</SelectItem>
            <SelectItem value="1:1">1:1</SelectItem>
            <SelectItem value="4:3">4:3</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>帧率</Label>
        <NumberInput
          value={(data.fps as number) || 24}
          onChange={(v) => onChange('fps', v)}
          defaultValue={24}
          min={12}
          max={60}
        />
      </div>

      <div className="space-y-2">
        <Label>保存路径（可选）</Label>
        <PathInput
          value={(data.savePath as string) || ''}
          onChange={(v) => onChange('savePath', v)}
          type="file"
          title="选择视频保存位置"
          fileTypes={[['视频文件', '*.mp4;*.avi;*.mkv;*.mov;*.webm'], ['所有文件', '*.*']]}
          placeholder="C:/videos/output.mp4"
        />
      </div>

      <div className="space-y-2">
        <Label>结果变量名</Label>
        <VariableNameInput
          value={(data.variableName as string) || 'ai_video_url'}
          onChange={(v) => onChange('variableName', v)}
          placeholder="ai_video_url"
        />
      </div>
    </div>
  )
}

// 概率触发器配置
export function ProbabilityTriggerConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>触发路径1的概率（%）</Label>
        <NumberInput
          value={(data.probability as number) || 50}
          onChange={(v) => onChange('probability', v)}
          defaultValue={50}
          min={0}
          max={100}
        />
        <p className="text-sm text-muted-foreground">
          设置触发路径1的概率百分比，剩余概率将触发路径2
        </p>
      </div>

      <div className="p-4 bg-muted rounded-lg">
        <p className="text-sm">
          <strong>说明：</strong>此模块会根据设置的概率随机选择执行路径。
          <br />
          • 路径1概率：{(data.probability as number) || 50}%
          <br />
          • 路径2概率：{100 - ((data.probability as number) || 50)}%
        </p>
      </div>
    </div>
  )
}
