// Source: WebRPA@5ccb900e, components/workflow/config-panels/NotifyModuleConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import type { NodeData } from '../../editor-store'

interface ConfigProps {
  data: NodeData
  onChange: (key: string, value: unknown) => void
}

// Discord通知配置
export function NotifyDiscordConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="Discord Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Telegram通知配置
export function NotifyTelegramConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="botToken">Bot Token</Label>
        <VariableInput
          value={(data.botToken as string) || ''}
          onChange={(v) => onChange('botToken', v)}
          placeholder="Telegram Bot Token"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="chatId">Chat ID</Label>
        <VariableInput
          value={(data.chatId as string) || ''}
          onChange={(v) => onChange('chatId', v)}
          placeholder="Telegram Chat ID"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// 钉钉通知配置
export function NotifyDingTalkConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="钉钉机器人 Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="secret">签名密钥（可选）</Label>
        <VariableInput
          value={(data.secret as string) || ''}
          onChange={(v) => onChange('secret', v)}
          placeholder="钉钉机器人签名密钥"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// 企业微信通知配置
export function NotifyWeComConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="企业微信机器人 Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// 飞书通知配置
export function NotifyFeishuConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="飞书机器人 Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="secret">签名密钥（可选）</Label>
        <VariableInput
          value={(data.secret as string) || ''}
          onChange={(v) => onChange('secret', v)}
          placeholder="飞书机器人签名密钥"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Bark通知配置
export function NotifyBarkConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="deviceKey">设备密钥</Label>
        <VariableInput
          value={(data.deviceKey as string) || ''}
          onChange={(v) => onChange('deviceKey', v)}
          placeholder="Bark 设备密钥"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="title">标题</Label>
        <VariableInput
          value={(data.title as string) || ''}
          onChange={(v) => onChange('title', v)}
          placeholder="通知标题"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Slack通知配置
export function NotifySlackConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="Slack Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Microsoft Teams通知配置
export function NotifyMSTeamsConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="Microsoft Teams Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Pushover通知配置
export function NotifyPushoverConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="userKey">User Key</Label>
        <VariableInput
          value={(data.userKey as string) || ''}
          onChange={(v) => onChange('userKey', v)}
          placeholder="Pushover User Key"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="apiToken">API Token</Label>
        <VariableInput
          value={(data.apiToken as string) || ''}
          onChange={(v) => onChange('apiToken', v)}
          placeholder="Pushover API Token"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// PushBullet通知配置
export function NotifyPushBulletConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="accessToken">Access Token</Label>
        <VariableInput
          value={(data.accessToken as string) || ''}
          onChange={(v) => onChange('accessToken', v)}
          placeholder="PushBullet Access Token"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Gotify通知配置
export function NotifyGotifyConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="serverUrl">服务器URL</Label>
        <VariableInput
          value={(data.serverUrl as string) || ''}
          onChange={(v) => onChange('serverUrl', v)}
          placeholder="Gotify 服务器 URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="appToken">App Token</Label>
        <VariableInput
          value={(data.appToken as string) || ''}
          onChange={(v) => onChange('appToken', v)}
          placeholder="Gotify App Token"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Server酱通知配置
export function NotifyServerChanConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="sendKey">SendKey</Label>
        <VariableInput
          value={(data.sendKey as string) || ''}
          onChange={(v) => onChange('sendKey', v)}
          placeholder="Server酱 SendKey"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="title">标题</Label>
        <VariableInput
          value={(data.title as string) || ''}
          onChange={(v) => onChange('title', v)}
          placeholder="通知标题"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// PushPlus通知配置
export function NotifyPushPlusConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="token">Token</Label>
        <VariableInput
          value={(data.token as string) || ''}
          onChange={(v) => onChange('token', v)}
          placeholder="PushPlus Token"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="title">标题</Label>
        <VariableInput
          value={(data.title as string) || ''}
          onChange={(v) => onChange('title', v)}
          placeholder="通知标题"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Webhook通知配置
export function NotifyWebhookConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容（JSON格式）</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder='{"message": "通知内容"}'
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y font-mono"
        />
      </div>
    </div>
  )
}

// Ntfy通知配置
export function NotifyNtfyConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="serverUrl">服务器URL</Label>
        <VariableInput
          value={(data.serverUrl as string) || 'https://ntfy.sh'}
          onChange={(v) => onChange('serverUrl', v)}
          placeholder="Ntfy 服务器 URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="topic">主题</Label>
        <VariableInput
          value={(data.topic as string) || ''}
          onChange={(v) => onChange('topic', v)}
          placeholder="Ntfy 主题"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Matrix通知配置
export function NotifyMatrixConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="homeserver">Homeserver URL</Label>
        <VariableInput
          value={(data.homeserver as string) || ''}
          onChange={(v) => onChange('homeserver', v)}
          placeholder="Matrix Homeserver URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="accessToken">Access Token</Label>
        <VariableInput
          value={(data.accessToken as string) || ''}
          onChange={(v) => onChange('accessToken', v)}
          placeholder="Matrix Access Token"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="roomId">Room ID</Label>
        <VariableInput
          value={(data.roomId as string) || ''}
          onChange={(v) => onChange('roomId', v)}
          placeholder="Matrix Room ID"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}

// Rocket.Chat通知配置
export function NotifyRocketChatConfig({ data, onChange }: ConfigProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="webhookUrl">Webhook URL</Label>
        <VariableInput
          value={(data.webhookUrl as string) || ''}
          onChange={(v) => onChange('webhookUrl', v)}
          placeholder="Rocket.Chat Webhook URL"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">消息内容</Label>
        <textarea
          value={(data.message as string) || ''}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="输入消息内容"
          className="w-full min-h-[80px] px-3 py-2 text-sm border rounded-md resize-y"
        />
      </div>
    </div>
  )
}
