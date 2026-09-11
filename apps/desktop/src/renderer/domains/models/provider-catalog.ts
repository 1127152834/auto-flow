import { alibabaCloudIcon, anthropicIcon, deepseekIcon, geminiIcon, moonshotIcon, ollamaIcon, openaiIcon, openrouterIcon, siliconFlowIcon } from './assets/provider-icons'

export type ProviderKind = 'openai' | 'anthropic' | 'gemini' | 'openai-compatible' | 'custom'
export type ProviderPreset = { id: string; displayName: string; aliases: string[]; providerKind: ProviderKind; category: string; defaultBaseUrl: string; apiKeyPolicy: 'required' | 'optional'; accent: string; iconPath?: string; documentationUrl: string; discoveryMode: 'catalog' }

const icons: Record<string, string> = { deepseek: deepseekIcon, openai: openaiIcon, anthropic: anthropicIcon, gemini: geminiIcon, qwen: alibabaCloudIcon, moonshot: moonshotIcon, siliconflow: siliconFlowIcon, openrouter: openrouterIcon, ollama: ollamaIcon }
const docs: Record<string, string> = {
  deepseek: 'https://api-docs.deepseek.com/', openai: 'https://developers.openai.com/api/', anthropic: 'https://docs.anthropic.com/en/api/', gemini: 'https://ai.google.dev/gemini-api/docs', qwen: 'https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api',
  'zhipu-ai': 'https://docs.bigmodel.cn/cn/guide/develop/openai/introduction', moonshot: 'https://platform.moonshot.cn/docs', siliconflow: 'https://docs.siliconflow.cn/', openrouter: 'https://openrouter.ai/docs/api/reference/overview', ollama: 'https://docs.ollama.com/api/openai-compatibility',
}

export const providerPresets: ProviderPreset[] = [
  ['deepseek', 'DeepSeek', ['深度求索'], 'openai-compatible', '官方接口', 'https://api.deepseek.com', 'required', '#4d6bfe'],
  ['openai', 'OpenAI', ['GPT'], 'openai', '官方接口', 'https://api.openai.com/v1', 'required', '#111827'],
  ['anthropic', 'Anthropic Claude', ['Claude'], 'anthropic', '官方接口', 'https://api.anthropic.com/v1', 'required', '#d97757'],
  ['gemini', 'Google Gemini', ['Google AI'], 'gemini', '官方接口', 'https://generativelanguage.googleapis.com/v1beta', 'required', '#4285f4'],
  ['qwen', '通义千问', ['Qwen', '阿里云百炼'], 'openai-compatible', '国内服务', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'required', '#615ced'],
  ['zhipu-ai', '智谱 AI', ['GLM', 'BigModel'], 'openai-compatible', '国内服务', 'https://open.bigmodel.cn/api/paas/v4', 'required', '#2454ff'],
  ['moonshot', '月之暗面', ['Moonshot', 'Kimi'], 'openai-compatible', '国内服务', 'https://api.moonshot.cn/v1', 'required', '#161616'],
  ['siliconflow', '硅基流动', ['SiliconFlow'], 'openai-compatible', '国内服务', 'https://api.siliconflow.cn/v1', 'required', '#713aed'],
  ['openrouter', 'OpenRouter', ['模型聚合'], 'openai-compatible', '聚合平台', 'https://openrouter.ai/api/v1', 'required', '#6566f1'],
  ['ollama', 'Ollama', ['本地模型'], 'openai-compatible', '本地运行', 'http://127.0.0.1:11434/v1', 'optional', '#111827'],
  ['custom-openai-compatible', '自定义 OpenAI 兼容接口', ['自定义', '兼容接口'], 'openai-compatible', '自定义', '', 'optional', '#9a684f'],
].map(([id, displayName, aliases, providerKind, category, defaultBaseUrl, apiKeyPolicy, accent]) => ({ id, displayName, aliases, providerKind, category, defaultBaseUrl, apiKeyPolicy, accent, iconPath: icons[id as string], documentationUrl: docs[id as string] ?? '', discoveryMode: 'catalog' }) as ProviderPreset)

export const findProviderPreset = (id?: string | null) => providerPresets.find((item) => item.id === id)
export const providerKindLabel = (kind: string) => ({ openai: 'OpenAI 官方接口', anthropic: 'Anthropic 官方接口', gemini: 'Google Gemini 接口', 'openai-compatible': 'OpenAI 兼容接口', custom: '自定义接口' }[kind] ?? '自定义接口')
