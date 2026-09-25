// Source: WebRPA@5ccb900e, types/modules.ts; see SOURCE.md for license and adaptation boundaries.
import type { ModuleConfig } from './workflow'

// ============ 基础模块配置 ============

export type WaitUntil = 'load' | 'domcontentloaded' | 'networkidle'

export interface OpenPageConfig extends ModuleConfig {
  url: string
  waitUntil?: WaitUntil
}

export type ClickType = 'single' | 'double' | 'right'

export interface ClickElementConfig extends ModuleConfig {
  selector: string
  clickType?: ClickType
  waitForSelector?: boolean
}

export interface InputTextConfig extends ModuleConfig {
  selector: string
  text: string
  clearBefore?: boolean
}

export type ElementAttribute = 'text' | 'innerHTML' | 'value' | 'href' | 'src' | 'custom'

export interface GetElementInfoConfig extends ModuleConfig {
  selector: string
  attribute?: ElementAttribute
  customAttribute?: string
  variableName: string
  columnName?: string
}

export type WaitType = 'time' | 'selector' | 'navigation'

export interface WaitConfig extends ModuleConfig {
  waitType?: WaitType
  duration?: number
  selector?: string
  state?: 'visible' | 'hidden' | 'attached' | 'detached'
}

export type ClosePageConfig = ModuleConfig

// ============ 高级模块配置 ============

export type SelectBy = 'value' | 'label' | 'index'

export interface SelectDropdownConfig extends ModuleConfig {
  selector: string
  selectBy?: SelectBy
  value: string
}

export interface SetCheckboxConfig extends ModuleConfig {
  selector: string
  checked?: boolean
}

export interface DragElementConfig extends ModuleConfig {
  sourceSelector: string
  targetSelector?: string
  targetPosition?: { x: number; y: number }
}

export type ScrollDirection = 'up' | 'down' | 'left' | 'right'

export interface ScrollPageConfig extends ModuleConfig {
  direction?: ScrollDirection
  distance?: number
  selector?: string
}

export interface UploadFileConfig extends ModuleConfig {
  selector: string
  filePath: string
}

export interface DownloadFileConfig extends ModuleConfig {
  triggerSelector: string
  savePath?: string
  variableName?: string
}

export interface SaveImageConfig extends ModuleConfig {
  selector: string
  savePath?: string
  variableName?: string
}

export interface GetChildElementsConfig extends ModuleConfig {
  parentSelector: string
  childSelector?: string
  variableName: string
}

export type SiblingType = 'all' | 'previous' | 'next'

export interface GetSiblingElementsConfig extends ModuleConfig {
  elementSelector: string
  variableName: string
  includeSelf?: boolean
  siblingType?: SiblingType
}

export interface InjectJavaScriptConfig extends ModuleConfig {
  javascriptCode: string
  saveResult?: string
  injectMode?: 'current' | 'all' | 'url_match' | 'index'
  targetUrl?: string
  targetIndex?: string
}

// ============ 验证码模块配置 ============

export interface OCRCaptchaConfig extends ModuleConfig {
  imageSelector: string
  inputSelector: string
  variableName?: string
  autoSubmit?: boolean
  submitSelector?: string
}

export interface SliderCaptchaConfig extends ModuleConfig {
  sliderSelector: string
  backgroundSelector?: string
  gapSelector?: string
}

// ============ 流程控制模块配置 ============

export type ConditionType = 'variable' | 'element_exists' | 'element_visible' | 'element_text'

export type Operator = '==' | '!=' | '>' | '<' | '>=' | '<=' | 'contains' | 'not_contains' | 'starts_with' | 'ends_with'

export interface ConditionConfig extends ModuleConfig {
  conditionType?: ConditionType
  leftOperand: string
  operator?: Operator
  rightOperand: string
}

export type LoopType = 'count' | 'range' | 'while'

export interface LoopConfig extends ModuleConfig {
  loopType?: LoopType
  // 计数循环
  loopCount?: string | number
  indexVariable?: string
  step?: string | number
  // 范围循环
  startValue?: string | number
  endValue?: string | number
  // 条件循环
  condition?: string
  maxIterations?: string | number
  // 超时配置（使用 loopTimeout 避免与 ModuleConfig.timeout 冲突）
  loopTimeout?: string | number
  onTimeout?: 'retry' | 'skip' | 'stop'
}

export interface ForeachConfig extends ModuleConfig {
  dataSource: string
  itemVariable?: string
  indexVariable?: string
}

export type BreakLoopConfig = ModuleConfig

export type ContinueLoopConfig = ModuleConfig

// ============ AI智能模块配置 ============

export type LLMProvider = 'ollama' | 'openai' | 'groq' | 'gemini' | 'azure'

export interface AISmartScraperConfig extends ModuleConfig {
  url: string
  prompt: string
  variableName: string
  llmProvider?: LLMProvider
  llmModel?: string
  apiKey?: string
  azureEndpoint?: string
  verbose?: boolean
  headless?: boolean
}

export interface AIElementSelectorConfig extends ModuleConfig {
  elementDescription: string
  variableName: string
  llmProvider?: LLMProvider
  llmModel?: string
  apiKey?: string
  azureEndpoint?: string
  verbose?: boolean
}

// ============ 手机自动化模块配置 ============

export interface PhoneConnectConfig extends ModuleConfig {
  deviceId?: string
}

export interface PhoneTapConfig extends ModuleConfig {
  x: string | number
  y: string | number
}

export interface PhoneSwipeConfig extends ModuleConfig {
  startX: string | number
  startY: string | number
  endX: string | number
  endY: string | number
  duration?: number
}

export interface PhoneLongPressConfig extends ModuleConfig {
  x: string | number
  y: string | number
  duration?: number
}

export interface PhoneInputTextConfig extends ModuleConfig {
  text: string
}

export type PhoneKeyType = 'HOME' | 'BACK' | 'RECENT' | 'POWER' | 'VOLUME_UP' | 'VOLUME_DOWN' | 'MENU' | 'ENTER'

export interface PhonePressKeyConfig extends ModuleConfig {
  key: PhoneKeyType
}

export interface PhoneScreenshotConfig extends ModuleConfig {
  savePath?: string
  variableName?: string
}

export interface PhoneStartMirrorConfig extends ModuleConfig {
  bitRate?: number
  maxSize?: number
  stayAwake?: boolean
  turnScreenOff?: boolean
}

export type PhoneStopMirrorConfig = ModuleConfig

export interface PhoneInstallAppConfig extends ModuleConfig {
  apkPath: string
}

export interface PhoneStartAppConfig extends ModuleConfig {
  packageName: string
  activityName?: string
}

export interface PhoneStopAppConfig extends ModuleConfig {
  packageName: string
}

export interface PhoneUninstallAppConfig extends ModuleConfig {
  packageName: string
}

export interface PhonePushFileConfig extends ModuleConfig {
  localPath: string
  remotePath: string
}

export interface PhonePullFileConfig extends ModuleConfig {
  remotePath: string
  localPath: string
  variableName?: string
}

// 所有模块配置类型联合
export type AnyModuleConfig =
  | ProxyControlConfig
  | OpenPageConfig
  | ClickElementConfig
  | InputTextConfig
  | GetElementInfoConfig
  | WaitConfig
  | ClosePageConfig
  | SelectDropdownConfig
  | SetCheckboxConfig
  | DragElementConfig
  | ScrollPageConfig
  | UploadFileConfig
  | DownloadFileConfig
  | SaveImageConfig
  | GetChildElementsConfig
  | GetSiblingElementsConfig
  | InjectJavaScriptConfig
  | OCRCaptchaConfig
  | SliderCaptchaConfig
  | AISmartScraperConfig
  | AIElementSelectorConfig
  | ConditionConfig
  | LoopConfig
  | ForeachConfig
  | BreakLoopConfig
  | ContinueLoopConfig
  | PhoneConnectConfig
  | PhoneTapConfig
  | PhoneSwipeConfig
  | PhoneLongPressConfig
  | PhoneInputTextConfig
  | PhonePressKeyConfig
  | PhoneScreenshotConfig
  | PhoneStartMirrorConfig
  | PhoneStopMirrorConfig
  | PhoneInstallAppConfig
  | PhoneStartAppConfig
  | PhoneStopAppConfig
  | PhoneUninstallAppConfig
  | PhonePushFileConfig
  | PhonePullFileConfig

export interface ProxyControlConfig extends ModuleConfig {
  target?: 'current' | 'specified'
  proxyId?: string
  locationId?: string
  operationId?: string
  retryIntervalSeconds?: number | string
  maxAttempts?: number | string
  confirmationTimeoutSeconds?: number | string
  failureMode?: 'raise' | 'capture'
  resultVariable?: string
}
export interface ProxyControlResult {
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'unknown'
  action: 'change_ip' | 'relocate' | 'query'
  proxyId: string | null
  operationId: string | null
  attemptsUsed: number
  requestsSent: number
  configuration: Record<string, unknown>
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  targetLocation: Record<string, unknown> | null
  changed: boolean
  error: { code: string; message: string; lastCode?: string; retryAfterSeconds: number | null; retryAllowed: boolean; outcomeUnknown: boolean } | null
}
