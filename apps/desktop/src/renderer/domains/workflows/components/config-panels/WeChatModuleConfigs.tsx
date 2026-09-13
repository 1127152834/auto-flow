// Source: WebRPA@5ccb900e, components/workflow/config-panels/WeChatModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'
import { Button } from '../controls/button'
import { FolderOpen, Info } from 'lucide-react'
import { systemApi } from '../../api'

// 微信使用提示组件
function WeChatTip() {
  return (
    <div className="p-3 bg-green-50 rounded-lg border border-green-200 mb-4">
      <div className="flex items-start gap-2">
        <Info className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
        <div className="text-xs text-green-800 space-y-1">
          <p className="font-medium">使用前请确保：</p>
          <ul className="list-disc list-inside space-y-0.5 text-green-700">
            <li>微信已登录且窗口已打开（支持任意版本）</li>
            <li>微信窗口没有被最小化</li>
            <li>执行时不要操作鼠标键盘</li>
          </ul>
          <p className="text-xs text-gray-500 mt-2">
            本模块通过模拟键鼠操作实现，兼容微信 4.x 新版本
          </p>
        </div>
      </div>
    </div>
  )
}

// 微信发送消息配置
export function WeChatSendMessageConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <WeChatTip />
      <div className="space-y-2">
        <Label htmlFor="target">目标联系人/群名</Label>
        <VariableInput
          value={(data.target as string) || ''}
          onChange={(v) => onChange('target', v)}
          placeholder="好友昵称或群名称"
        />
        <p className="text-xs text-muted-foreground">输入好友昵称、备注名或群名称（需能通过搜索找到）</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <VariableInput
          value={(data.message as string) || ''}
          onChange={(v) => onChange('message', v)}
          placeholder="要发送的消息内容"
          multiline
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量（可选）</Label>
        <VariableNameInput
          value={(data.resultVariable as string) || ''}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存发送结果的变量名"
        />
      </div>
    </>
  )
}

// 微信发送文件配置
export function WeChatSendFileConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  return (
    <>
      <WeChatTip />
      <div className="space-y-2">
        <Label htmlFor="target">目标联系人/群名</Label>
        <VariableInput
          value={(data.target as string) || ''}
          onChange={(v) => onChange('target', v)}
          placeholder="好友昵称或群名称"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="filePath">文件路径</Label>
        <div className="flex gap-1">
          <VariableInput
            value={(data.filePath as string) || ''}
            onChange={(v) => onChange('filePath', v)}
            placeholder="文件或图片的本地路径"
            className="flex-1"
          />
          <Button
            type="button"
            variant="tonal-warning"
            size="icon"
            className="shrink-0"
            onClick={async () => {
              try {
                const result = await systemApi.selectFile('选择文件', undefined, [
                  ['图片文件', '*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp'],
                  ['文档文件', '*.doc;*.docx;*.pdf;*.xls;*.xlsx;*.ppt;*.pptx'],
                  ['压缩文件', '*.zip;*.rar;*.7z'],
                  ['所有文件', '*.*']
                ])
                if (result.data?.success && result.data.path) {
                  onChange('filePath', result.data.path)
                }
              } catch (error) {
                console.error('选择文件失败:', error)
              }
            }}
          >
            <FolderOpen className="w-4 h-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">支持图片、文档、压缩包等各类文件</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="resultVariable">结果变量（可选）</Label>
        <VariableNameInput
          value={(data.resultVariable as string) || ''}
          onChange={(v) => onChange('resultVariable', v)}
          placeholder="保存发送结果的变量名"
        />
      </div>
    </>
  )
}
