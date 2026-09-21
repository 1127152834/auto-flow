// Source: WebRPA@5ccb900e; see SOURCE.md for provenance and adaptation boundaries.
/**
 * 计划任务失败/成功通知配置编辑器（复用于创建/编辑对话框）
 * 支持邮件 / 企业微信 / 钉钉 / Server酱 / 自定义 Webhook 多渠道。
 * 敏感字段只接受 {{cred:名称.字段}}，实际值由系统凭据库在发送时解析。
 */
import { Plus, Trash2, Bell } from 'lucide-react'
import { Label } from '../controls/label'
import { Input } from '../controls/input'
import { Button } from '../controls/button'
import { Switch } from '../controls/switch'
import type { NotifyChannel } from '../../hooks/stores/scheduledTaskStore'

interface Props {
  notifyOnFailure: boolean
  notifyOnSuccess: boolean
  channels: NotifyChannel[]
  onChange: (patch: { notifyOnFailure?: boolean; notifyOnSuccess?: boolean; channels?: NotifyChannel[] }) => void
}

const CHANNEL_LABELS: Record<NotifyChannel['type'], string> = {
  email: '邮件',
  wecom: '企业微信',
  dingtalk: '钉钉',
  serverchan: 'Server酱',
  webhook: '自定义Webhook',
}

export function NotificationConfigEditor({ notifyOnFailure, notifyOnSuccess, channels, onChange }: Props) {
  const list = channels || []

  const addChannel = (type: NotifyChannel['type']) => {
    onChange({ channels: [...list, { type, enabled: true }] })
  }
  const updateChannel = (idx: number, patch: Partial<NotifyChannel>) => {
    onChange({ channels: list.map((c, i) => (i === idx ? { ...c, ...patch } : c)) })
  }
  const removeChannel = (idx: number) => {
    onChange({ channels: list.filter((_, i) => i !== idx) })
  }

  const field = (idx: number, key: keyof NotifyChannel, label: string, placeholder = '', type = 'text') => (
    <div className="space-y-1">
      <Label className="text-xs text-gray-600">{label}</Label>
      <Input
        type={type}
        value={(list[idx][key] as string | number | undefined) ?? ''}
        onChange={(e) => updateChannel(idx, { [key]: type === 'number' ? Number(e.target.value) : e.target.value } as Partial<NotifyChannel>)}
        placeholder={placeholder}
        className="h-8 text-sm"
      />
    </div>
  )

  return (
    <div className="space-y-3 pt-2 border-t border-purple-200">
      <div className="flex items-center gap-2">
        <Bell className="w-4 h-4 text-purple-500" />
        <span className="font-medium text-sm">执行通知</span>
      </div>

      <div className="flex items-center gap-6">
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <Switch checked={notifyOnFailure} onCheckedChange={(v) => onChange({ notifyOnFailure: v })} />
          失败时通知
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <Switch checked={notifyOnSuccess} onCheckedChange={(v) => onChange({ notifyOnSuccess: v })} />
          成功时通知
        </label>
      </div>

      {(notifyOnFailure || notifyOnSuccess) && (
        <div className="space-y-2">
          {list.length === 0 && (
            <p className="text-xs text-gray-400">还没有通知渠道，点下方按钮添加。密码、令牌和地址必须使用 {'{{cred:名称.字段}}'} 引用凭据库。</p>
          )}
          {list.map((c, idx) => (
            <div key={idx} className="p-2.5 rounded-lg border border-gray-200 bg-gray-50 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Switch checked={c.enabled !== false} onCheckedChange={(v) => updateChannel(idx, { enabled: v })} />
                  <span className="text-sm font-medium">{CHANNEL_LABELS[c.type]}</span>
                </div>
                <button onClick={() => removeChannel(idx)} className="p-1 text-gray-400 hover:text-red-600">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {c.type === 'email' && (
                <div className="grid grid-cols-2 gap-2">
                  {field(idx, 'smtp_server', 'SMTP服务器', 'smtp.qq.com')}
                  {field(idx, 'smtp_port', '端口', '465', 'number')}
                  {field(idx, 'username', '账号', 'you@example.com')}
                  {field(idx, 'password', '口令/授权码', '{{cred:邮箱.password}}', 'password')}
                  {field(idx, 'to', '收件人', '多个用逗号分隔')}
                </div>
              )}
              {c.type === 'wecom' && (
                <div className="grid grid-cols-1 gap-2">
                  {field(idx, 'key', '机器人 Key', '群机器人 webhook 的 key（或直接填完整 webhook）')}
                  {field(idx, 'webhook', '完整 Webhook（可选）', 'https://qyapi.weixin.qq.com/...')}
                </div>
              )}
              {c.type === 'dingtalk' && (
                <div className="grid grid-cols-1 gap-2">
                  {field(idx, 'access_token', 'access_token', '机器人 access_token')}
                  {field(idx, 'secret', '加签 secret（可选）', 'SEC...')}
                </div>
              )}
              {c.type === 'serverchan' && (
                <div className="grid grid-cols-1 gap-2">
                  {field(idx, 'sendkey', 'SendKey', 'SCT...')}
                </div>
              )}
              {c.type === 'webhook' && (
                <div className="grid grid-cols-1 gap-2">
                  {field(idx, 'url', '回调 URL', 'https://your.endpoint/notify')}
                </div>
              )}
            </div>
          ))}

          <div className="flex flex-wrap gap-2">
            {(Object.keys(CHANNEL_LABELS) as NotifyChannel['type'][]).map((t) => (
              <Button key={t} type="button" variant="outline" size="sm" onClick={() => addChannel(t)} className="h-7 text-xs">
                <Plus className="w-3.5 h-3.5 mr-1" />{CHANNEL_LABELS[t]}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
