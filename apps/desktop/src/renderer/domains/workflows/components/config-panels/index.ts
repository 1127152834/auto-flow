// Source: WebRPA@5ccb900e, components/workflow/config-panels/index.ts; see SOURCE.md for license and adaptation boundaries.
// 配置面板组件导出
// 注意：DesktopModuleConfigs 中的 Desktop*Config 是新版本，
// AdvancedModuleConfigs 中的同名 export 是旧版占位符。
// 必须先 export DesktopModuleConfigs，再用 named re-export 排除 AdvancedModuleConfigs 中重复的 Desktop* 名称。
export * from './ReadExcelConfig'
export * from './SimilarSelectorDialog'
export * from './UrlInputDialog'
export * from './BasicModuleConfigs'
export * from './DesktopModuleConfigs'
// 显式 re-export AdvancedModuleConfigs 中独有的非 Desktop* 组件
export {
  ClickImageConfig,
  ClickTextConfig,
  DownloadFileConfig,
  DragElementConfig,
  DragImageConfig,
  ElementExistsConfig,
  ElementVisibleConfig,
  ExportLogConfig,
  GetChildElementsConfig,
  GetClipboardConfig,
  GetMousePositionConfig,
  GetSiblingElementsConfig,
  HoverImageConfig,
  HoverTextConfig,
  ImageExistsConfig,
  KeyboardActionConfig,
  LockScreenConfig,
  MacroRecorderConfig,
  NetworkCaptureConfig,
  NetworkMonitorStartConfig,
  NetworkMonitorStopConfig,
  NetworkMonitorWaitConfig,
  OCRCaptchaConfig,
  RealKeyboardConfig,
  RealMouseClickConfig,
  RealMouseDragConfig,
  RealMouseMoveConfig,
  RealMouseScrollConfig,
  RenameFileConfig,
  RunCommandConfig,
  SaveImageConfig,
  ScreenshotConfig,
  ScreenshotScreenConfig,
  ScrollPageConfig,
  SelectDropdownConfig,
  SendEmailConfig,
  SetCheckboxConfig,
  SetClipboardConfig,
  ShareFileConfig,
  ShareFolderConfig,
  ShutdownSystemConfig,
  SliderCaptchaConfig,
  StartScreenShareConfig,
  StopScreenShareConfig,
  StopShareConfig,
  UploadFileConfig,
  WindowFocusConfig,
} from './AdvancedModuleConfigs'
export * from './ControlModuleConfigs'
export * from './AIModuleConfigs'
export * from './DataModuleConfigs'
export * from './DocumentConvertConfigs'
export * from './PillowImageConfigs'
export * from './BlindWatermarkConfigs'
export * from './MathListConfigs'
export * from './WebhookModuleConfigs'
export * from './FeishuModuleConfigs'
export * from './DatabaseAdvancedConfigs'
export * from './SSHModuleConfigs'
export * from './AIMediaConfigs'
export * from './NotifyModuleConfigs'
export * from './ListAdvancedConfigs'
export * from './DictAdvancedConfigs'
export * from './StatisticsConfigs'
export * from './MathAdvancedConfigs'
export * from './SAPModuleConfigs'
