# F1 服务消费契约矩阵

本文件由 scripts/inventory-studio-services.mjs 从当前源码生成，配合 service-inventory.json 阅读。它逐项登记实际声明及静态消费入口，不是全量已冻结合同或验收通过声明。dynamic 表示必须追踪调用参数，不能假定为 GET；没有显式响应类型也不能解释为任意响应都合法。

## 已有局部合同与证据

| 范围 | 当前约束 | 尚未完成 |
|---|---|---|
| 命令公共包络 | commandId、success、查询 httpStatus 由 OpenAPI 生成；见 command-schema-validation.md、command-identity-validation.md | 各事件业务 payload、持久化命令、独立运行身份 |
| 图像元数据和变更响应 | 上传/重命名 asset 包络，目录位置及删除数量；见 image-schema-validation.md、image-command-validation.md | 全量网络运行时校验、实际文件系统及宿主资源端点 |
| HTTP/SSE | 共用受控传输；空行确认事件，序号补读，EOF 半包不提交；见 authenticated-transport.md、sse-framing-validation.md | epoch/服务重启后的状态重建 |
| Debug | 只接受 POST resume/step/breakpoints；404 未知动作，405 方法错误，409 状态冲突，422 断点非法；见 debug-command-validation.md | pauseId、控制修订、真正执行和清理 |
| 必填字段规则 | 生成DTO、覆盖列表、条件规则、失败重试及连接代际隔离；见 required-field-service-contract.md | 冻结源仅覆盖69个保留节点，215个无源规则，不当作完整校验 |
| 拾取 | 原文档/节点/字段响应隔离；见 picker-context-validation.md、similar-atomic-validation.md | 跨入口 session/request 所有权、启动取消和清理重试 |

## 静态服务方法

| 操作 ID | 方法与端点表达式 | 请求体表达式 | 声明的响应类型 | 静态消费者数 | 定义位置 | 验收状态 |
|---|---|---|---|---:|---|---|
| service:aiAssistantApi.addMemory | POST '/ai-assistant/memories' | body: JSON.stringify({ content, tags }) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:100 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.cancel | POST &#96;/ai-assistant/sessions/${sessionId}/cancel&#96; | 未显式声明 | { success: boolean; session_id: string } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:70 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.chat | POST '/ai-assistant/chat' | body: JSON.stringify(req) | ChatResponsePayload | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:63 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.createSession | POST '/ai-assistant/sessions' | body: JSON.stringify({ title }) | { session_id: string; title: string } | 0 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:34 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.deleteMemory | DELETE &#96;/ai-assistant/memories/${id}&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:106 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.deleteSession | DELETE &#96;/ai-assistant/sessions/${id}&#96; | 未显式声明 | { success: boolean } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:45 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.extractFile | POST '/ai-assistant/extract-file' | body: JSON.stringify({ filename, content_base64: contentBase64 }) | { success: boolean; text: string; error?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:82 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.getSession | GET &#96;/ai-assistant/sessions/${id}&#96; | 未显式声明 | { id: string; title: string; messages: ChatMessage[] } | 2 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:40 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.getSharedConfig | GET '/ai-assistant/config' | 未显式声明 | { config: any &#124; null } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:110 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.listMemories | GET '/ai-assistant/memories' | 未显式声明 | { entries: any[] } | 0 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:97 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.listSessions | GET '/ai-assistant/sessions' | 未显式声明 | SessionListItem[] | 3 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:31 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.listSkills | GET '/ai-assistant/skills' | 未显式声明 | { count: number; skills: any[] } | 0 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:94 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.renameSession | PATCH &#96;/ai-assistant/sessions/${id}/title&#96; | body: JSON.stringify({ title }) | { success: boolean } | 0 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:50 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.saveSharedConfig | PUT '/ai-assistant/config' | body: JSON.stringify({ config }) | { success: boolean } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:113 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.testConnection | POST '/ai-assistant/test-connection' | body: JSON.stringify({ config }) | { success: boolean; message: string; detail?: string; latency_ms?: number } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:76 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.transcribe | POST '/ai-assistant/transcribe' | body: JSON.stringify({ audio_base64: audioBase64, language, model_size: modelSize }) | { success: boolean; text: string; error?: string; language?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:88 | 待逐项核对；局部已验证项见上表 |
| service:aiAssistantApi.truncateSession | POST &#96;/ai-assistant/sessions/${id}/truncate&#96; | body: JSON.stringify({ message_id: messageId }) | { success: boolean; messages: ChatMessage[] } | 1 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantApi.ts:57 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.chromiumStatus | GET '/browser/chromium-status' | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:299 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.close | POST '/browser/close' | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:304 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.getSelector | POST '/browser/get-selector' | body: JSON.stringify({ description }) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:308 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.getStatus | GET '/browser/status' | 未显式声明 | Result | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:289 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.getUrl | GET '/browser/url' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:307 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.launch | POST '/browser/launch' | body: JSON.stringify({ url }) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:302 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.navigate | POST '/browser/navigate' | body: JSON.stringify({ url }) | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:305 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.open | POST '/browser/open' | body: JSON.stringify({ url, browserConfig }) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:300 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.startPicker | POST '/element-picker/start' | body: JSON.stringify({}) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:310 | 待逐项核对；局部已验证项见上表 |
| service:browserApi.stopPicker | POST '/element-picker/stop' | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:311 | 待逐项核对；局部已验证项见上表 |
| service:browserScriptTestsApi.cancel |  | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api/browserScriptTests.ts:20 | 待逐项核对；局部已验证项见上表 |
| service:browserScriptTestsApi.get |  | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api/browserScriptTests.ts:19 | 待逐项核对；局部已验证项见上表 |
| service:browserScriptTestsApi.getContext | GET &#96;${endpoint}/context&#96; | 未显式声明 | BrowserScriptContext | 0 | apps/desktop/src/renderer/domains/workflows/api/browserScriptTests.ts:10 | 待逐项核对；局部已验证项见上表 |
| service:browserScriptTestsApi.start |  | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api/browserScriptTests.ts:15 | 待逐项核对；局部已验证项见上表 |
| service:credentialApi.delete | DELETE &#96;/credentials/${encodeURIComponent(name)}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:440 | 待逐项核对；局部已验证项见上表 |
| service:credentialApi.list | GET '/credentials' | 未显式声明 | { success: boolean; credentials: CredentialItem[] } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:428 | 待逐项核对；局部已验证项见上表 |
| service:credentialApi.names | GET '/credentials/names' | 未显式声明 | { success: boolean; names: string[] } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:429 | 待逐项核对；局部已验证项见上表 |
| service:credentialApi.rename | POST '/credentials/rename' | body: JSON.stringify({ old_name: oldName, new_name: newName }) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:435 | 待逐项核对；局部已验证项见上表 |
| service:credentialApi.upsert | POST '/credentials' | body: JSON.stringify({ name, fields, description: description &#124;&#124; '' }) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:430 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.create | POST '/custom-modules' | body: JSON.stringify(data) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:398 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.delete | DELETE &#96;/custom-modules/${id}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:402 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.duplicate | POST &#96;/custom-modules/${id}/duplicate&#96; | body: JSON.stringify(newName ? { new_name: newName } : {}) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:404 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.get | GET &#96;/custom-modules/${id}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:397 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.importModule | POST &#96;/custom-modules/import&#96; | body: JSON.stringify(data) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:409 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.incrementUsage | POST &#96;/custom-modules/${id}/increment-usage&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:414 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.list | GET &#96;/custom-modules${params ? &#96;?${new URLSearchParams(params as any).toString()}&#96; : ''}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:395 | 待逐项核对；局部已验证项见上表 |
| service:customModulesApi.update | PUT &#96;/custom-modules/${id}&#96; | body: JSON.stringify(data) | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:400 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.getResult | GET '/element-picker/result' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:327 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.getSelected | GET '/element-picker/selected' | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:328 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.getSimilar | GET '/element-picker/similar' | 未显式声明 | Result | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:329 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.getStatus | GET '/element-picker/status' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:346 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.start | POST '/element-picker/start' | body: JSON.stringify({ url: url &#124;&#124; null, browserConfig: browserConfig &#124;&#124; null }) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:321 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.stop | POST '/element-picker/stop' | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:326 | 待逐项核对；局部已验证项见上表 |
| service:elementPickerApi.testSelector | POST '/element-picker/test-selector' | body: JSON.stringify({ selector, hints: hints &#124;&#124; null, highlight }) | Result | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:348 | 待逐项核对；局部已验证项见上表 |
| service:executorApi.execute | POST '/executor/execute' | body: JSON.stringify(data) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:230 | 待逐项核对；局部已验证项见上表 |
| service:executorApi.getTypes | GET '/executor/types' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:232 | 待逐项核对；局部已验证项见上表 |
| service:featurePackApi.installFromPath | POST '/feature-packs/install-path' | body: JSON.stringify({ path }) | { success: boolean; id?: string; name?: string; installed_files?: number; warning?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:588 | 待逐项核对；局部已验证项见上表 |
| service:featurePackApi.installUpload | POST '/feature-packs/install' | body: formData | { success: boolean; id?: string; name?: string; installed_files?: number; warning?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:593 | 待逐项核对；局部已验证项见上表 |
| service:featurePackApi.list | GET '/feature-packs' | 未显式声明 | { success: boolean; packs: FeaturePackInfo[] } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:586 | 待逐项核对；局部已验证项见上表 |
| service:featurePackApi.moduleHint | GET &#96;/feature-packs/module-hint/${encodeURIComponent(moduleType)}&#96; | 未显式声明 | { success: boolean; pack: { id: string; name: string; installed: boolean } &#124; null } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:611 | 待逐项核对；局部已验证项见上表 |
| service:featurePackApi.preflight | POST '/feature-packs/preflight' | body: JSON.stringify({ module_types: moduleTypes }) | { success: boolean; ok: boolean; missing: Array&lt;{ alternatives: Array&lt;{ id: string; name: string; size_mb: number; download_url?: string }&gt;; module_types: string[] }&gt;; message: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:601 | 待逐项核对；局部已验证项见上表 |
| service:featurePackApi.uninstall | POST '/feature-packs/uninstall' | body: JSON.stringify({ id }) | { success: boolean; removed?: number } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:606 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.createFolder | POST '/image-assets/folders' | body: JSON.stringify({ name, parentPath }) | components['schemas']['StudioImageFolderCreated'] | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:247 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.delete | DELETE &#96;/image-assets/${id}&#96; | 未显式声明 | components['schemas']['StudioImageMutationResult'] | 3 | apps/desktop/src/renderer/domains/workflows/api.ts:246 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.deleteFolder | DELETE '/image-assets/folders' | body: JSON.stringify({ folderPath }) | components['schemas']['StudioImageFolderDeleted'] | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:251 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.get | GET &#96;/image-assets/${id}&#96; | 未显式声明 | components['schemas']['StudioImageAsset'] | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:239 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.list | GET '/image-assets' | 未显式声明 | components['schemas']['StudioImageAsset'][] | 9 | apps/desktop/src/renderer/domains/workflows/api.ts:237 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.listFolders | GET '/image-assets/folders' | 未显式声明 | string[] | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:238 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.moveAsset | PUT '/image-assets/move' | body: JSON.stringify({ assetId, targetFolder }) | components['schemas']['StudioImageMoved'] | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:255 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.rename | PUT &#96;/image-assets/${assetId}/rename?newName=${encodeURIComponent(newName)}&#96; | 未显式声明 | components['schemas']['StudioImageRenameResult'] | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:253 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.renameFolder | PUT '/image-assets/folders/rename' | body: JSON.stringify({ oldPath, newName }) | components['schemas']['StudioImageFolderRenamed'] | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:249 | 待逐项核对；局部已验证项见上表 |
| service:imageAssetApi.upload | POST '/image-assets/upload' | body: formData | components['schemas']['StudioImageUploadResult'] | 3 | apps/desktop/src/renderer/domains/workflows/api.ts:240 | 待逐项核对；局部已验证项见上表 |
| service:inputPromptApi.getState | GET &#96;/events/input-prompts/${encodeURIComponent(requestId)}&#96; | 未显式声明 | components['schemas']['StudioInputPromptState'] | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:618 | 待逐项核对；局部已验证项见上表 |
| service:jsScriptApi.getState |  | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:634 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.delete | DELETE &#96;/local-workflows/${id}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:203 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.export | GET &#96;/local-workflows/${id}/export&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:207 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.get | GET &#96;/local-workflows/load/${encodeURIComponent(filename)}&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:199 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.getActiveFolder | GET '/local-workflows/active-folder' | 未显式声明 | { folder: string; default: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:211 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.getDefaultFolder | GET '/local-workflows/default-folder' | 未显式声明 | 未显式声明 | 5 | apps/desktop/src/renderer/domains/workflows/api.ts:208 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.getSelfHeal | GET &#96;/local-workflows/self-heal/${encodeURIComponent(filename)}${folder ? &#96;?folder=${encodeURIComponent(folder)}&#96; : ''}&#96; | 未显式声明 | { success: boolean; enabled: boolean; selfHeal?: any; error?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:218 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.import | POST '/local-workflows/import' | body: JSON.stringify(data) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:205 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.list | POST '/local-workflows/list' | body: JSON.stringify({ folder }) | 未显式声明 | 4 | apps/desktop/src/renderer/domains/workflows/api.ts:189 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.save | POST '/local-workflows/save-to-folder' | body: JSON.stringify(data) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:201 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.setActiveFolder | POST '/local-workflows/active-folder' | body: JSON.stringify({ folder }) | { success: boolean; folder: string } | 3 | apps/desktop/src/renderer/domains/workflows/api.ts:212 | 待逐项核对；局部已验证项见上表 |
| service:localWorkflowApi.setSelfHeal | POST '/local-workflows/self-heal' | body: JSON.stringify({ filename, enabled, folder }) | { success: boolean; enabled: boolean; error?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:222 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.addReview | POST &#96;/plugins/${encodeURIComponent(pluginId)}/reviews&#96; | body: JSON.stringify({ rating, comment: comment &#124;&#124; '', user: user &#124;&#124; '匿名用户' }) | { success: boolean; review?: PluginReview; summary?: { count: number; average: number }; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:536 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.exportPackage | GET &#96;/plugins/${encodeURIComponent(pluginId)}/export&#96; | 未显式声明 | { success: boolean; package?: unknown; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:524 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.getMarketUrl | GET '/plugins/market-url' | 未显式声明 | { success: boolean; url: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:509 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.getReviews | GET &#96;/plugins/${encodeURIComponent(pluginId)}/reviews&#96; | 未显式声明 | { success: boolean; reviews: PluginReview[]; summary: { count: number; average: number } } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:532 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.installed | GET '/plugins/installed' | 未显式声明 | { success: boolean; plugins: PluginInfo[] } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:505 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.installFromMarket | POST &#96;/plugins/install-from-market/${encodeURIComponent(pluginId)}&#96; | 未显式声明 | { success: boolean; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:516 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.installPackage | POST '/plugins/install' | body: JSON.stringify({ package: pkg }) | { success: boolean; id?: string; moduleCount?: number; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:512 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.market | GET '/plugins/market' | 未显式声明 | { success: boolean; source?: string; plugins: PluginInfo[] } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:507 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.publish | POST &#96;/plugins/${encodeURIComponent(pluginId)}/publish&#96; | body: JSON.stringify({ hubUrl: hubUrl &#124;&#124; '' }) | { success: boolean; published?: boolean; package?: unknown; exportedPath?: string; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:528 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.setEnabled | POST &#96;/plugins/${encodeURIComponent(pluginId)}/enable&#96; | body: JSON.stringify({ enabled }) | { success: boolean; enabled?: boolean; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:518 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.setMarketUrl | POST '/plugins/market-url' | body: JSON.stringify({ url }) | { success: boolean } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:510 | 待逐项核对；局部已验证项见上表 |
| service:pluginApi.uninstall | DELETE &#96;/plugins/${encodeURIComponent(pluginId)}&#96; | 未显式声明 | { success: boolean; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:522 | 待逐项核对；局部已验证项见上表 |
| service:recorderApi.events | GET &#96;/recorder/events?afterSeq=${afterSeq}${sessionId ? &#96;&amp;sessionId=${encodeURIComponent(sessionId)}&#96; : ''}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:376 | 待逐项核对；局部已验证项见上表 |
| service:recorderApi.start | POST '/recorder/start' | body: JSON.stringify({ sessionId }) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:374 | 待逐项核对；局部已验证项见上表 |
| service:recorderApi.status | GET '/recorder/status' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:377 | 待逐项核对；局部已验证项见上表 |
| service:recorderApi.stop | POST '/recorder/stop' | body: JSON.stringify({ sessionId, afterSeq }) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:375 | 待逐项核对；局部已验证项见上表 |
| service:retentionApi.cleanup | POST '/retention/cleanup' | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:465 | 待逐项核对；局部已验证项见上表 |
| service:retentionApi.getConfig | GET '/retention/config' | 未显式声明 | { success: boolean; config: RetentionConfig; usage: RetentionUsage } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:458 | 待逐项核对；局部已验证项见上表 |
| service:retentionApi.setConfig | POST '/retention/config' | body: JSON.stringify(config) | { success: boolean; config: RetentionConfig } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:460 | 待逐项核对；局部已验证项见上表 |
| service:retentionApi.usage | GET '/retention/usage' | 未显式声明 | { success: boolean; usage: RetentionUsage } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:466 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.clearAllLogs | DELETE '/scheduled-tasks/logs/all' | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:281 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.clearTaskLogs | DELETE &#96;/scheduled-tasks/${id}/logs&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:279 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.create | POST '/scheduled-tasks' | body: JSON.stringify(data) | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:263 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.delete | DELETE &#96;/scheduled-tasks/${id}&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:267 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.execute | POST &#96;/scheduled-tasks/${id}/execute&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:271 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.get | GET &#96;/scheduled-tasks/${id}&#96; | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:262 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.getAllLogs | GET &#96;/scheduled-tasks/logs/all?limit=${limit}&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:277 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.getStatistics | GET '/scheduled-tasks/statistics/summary' | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:283 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.getTaskLogs | GET &#96;/scheduled-tasks/${id}/logs?limit=${limit}&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:275 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.list | GET '/scheduled-tasks/list' | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:261 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.stop | POST &#96;/scheduled-tasks/${id}/stop&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:273 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.toggle | POST &#96;/scheduled-tasks/${id}/toggle&#96; | body: JSON.stringify({ enabled }) | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:269 | 待逐项核对；局部已验证项见上表 |
| service:scheduledTaskApi.update | PUT &#96;/scheduled-tasks/${id}&#96; | body: JSON.stringify(data) | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:265 | 待逐项核对；局部已验证项见上表 |
| service:securityApi.regenerate | POST '/security/regenerate' | 未显式声明 | { success: boolean; token?: string; error?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:387 | 待逐项核对；局部已验证项见上表 |
| service:securityApi.status | GET '/security/status' | 未显式声明 | { enabled: boolean; isLocal: boolean; token: string &#124; null } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:382 | 待逐项核对；局部已验证项见上表 |
| service:securityApi.toggle | POST '/security/toggle' | body: JSON.stringify({ enabled }) | { success: boolean; enabled?: boolean; error?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:383 | 待逐项核对；局部已验证项见上表 |
| service:speechApi.getState |  | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:637 | 待逐项核对；局部已验证项见上表 |
| service:sponsorApi.list | GET '/sponsors/list' | 未显式声明 | { sponsors: SponsorItem[]; count: number } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:560 | 待逐项核对；局部已验证项见上表 |
| service:sponsorApi.qrUrl |  | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:564 | 待逐项核对；局部已验证项见上表 |
| service:sponsorApi.status | GET '/sponsors/status' | 未显式声明 | { wechat: boolean; alipay: boolean } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:562 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.getBrowserConfig | GET '/system/browser-config' | 未显式声明 | { success: boolean; config: Record&lt;string, unknown&gt; } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:110 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.getConfig | GET '/system/config' | 未显式声明 | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:108 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.getMousePosition | GET '/system/mouse-position' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:130 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.openUrl | POST '/system/open-url' | body: JSON.stringify({ url }) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:126 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.screenshotBase64 | POST '/system/screenshot-base64' | body: '{}' | { success: boolean; dataUrl?: string; width?: number; height?: number; error?: string } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:136 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.selectFile | POST '/system/select-file' | body: JSON.stringify({ title, initialDir, fileTypes }) | 未显式声明 | 6 | apps/desktop/src/renderer/domains/workflows/api.ts:121 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.selectFolder | POST '/system/select-folder' | body: JSON.stringify({ title, initialDir }) | 未显式声明 | 7 | apps/desktop/src/renderer/domains/workflows/api.ts:116 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.setBrowserConfig | POST '/system/browser-config' | body: JSON.stringify(cfg) | { success: boolean; config: Record&lt;string, unknown&gt; } | 3 | apps/desktop/src/renderer/domains/workflows/api.ts:111 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.setClipboard | POST '/system/set-clipboard' | body: JSON.stringify({ text }) | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:132 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.setCustomHotkeys | POST '/system/custom-hotkeys' | body: JSON.stringify({ shortcuts }) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:128 | 待逐项核对；局部已验证项见上表 |
| service:systemApi.takeScreenshot | POST '/system/screenshot' | body: JSON.stringify(params &#124;&#124; {}) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:134 | 待逐项核对；局部已验证项见上表 |
| service:variableTrackingApi.clear | DELETE &#96;/workflows/${encodeURIComponent(workflowId)}/variable-tracking&#96; | 未显式声明 | components['schemas']['StudioVariableTrackingCleared'] | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:656 | 待逐项核对；局部已验证项见上表 |
| service:variableTrackingApi.list | GET &#96;/workflows/${encodeURIComponent(workflowId)}/variable-tracking&#96; | 未显式声明 | components['schemas']['StudioVariableTrackingResult'] | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:643 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.create | POST '/workflows' | body: JSON.stringify(data) | 未显式声明 | 3 | apps/desktop/src/renderer/domains/workflows/api.ts:146 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.debugBreakpoints | POST &#96;/workflows/${id}/debug/breakpoints&#96; | body: JSON.stringify({ breakpoints }) | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:163 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.debugResume | POST &#96;/workflows/${id}/debug/resume&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:157 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.debugStep | POST &#96;/workflows/${id}/debug/step&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:160 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.delete | DELETE &#96;/workflows/${id}&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:150 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.execute | POST &#96;/workflows/${id}/execute&#96; | body: JSON.stringify(params &#124;&#124; {}) | 未显式声明 | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:152 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.exportScript | GET &#96;/workflows/${id}/export-script?target=${encodeURIComponent(target)}&#96; | 未显式声明 | { code: string; filename: string; target: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:176 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.get | GET &#96;/workflows/${id}&#96; | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:145 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.getFullData | GET &#96;/workflows/${id}/data/full&#96; | 未显式声明 | { rows: Record&lt;string, unknown&gt;[]; columns: string[]; total: number } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:166 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.getGlobalVariables | GET '/workflows/global-variables' | 未显式声明 | { variables: Record&lt;string, unknown&gt;; count: number } | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:181 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.getLatestFullData | GET &#96;/workflows/data-latest/full&#96; | 未显式声明 | { workflow_id: string; rows: Record&lt;string, unknown&gt;[]; columns: string[]; total: number } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:171 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.list | GET '/workflows' | 未显式声明 | 未显式声明 | 0 | apps/desktop/src/renderer/domains/workflows/api.ts:144 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.stop | POST &#96;/workflows/${id}/stop&#96; | 未显式声明 | 未显式声明 | 2 | apps/desktop/src/renderer/domains/workflows/api.ts:154 | 待逐项核对；局部已验证项见上表 |
| service:workflowApi.update | PUT &#96;/workflows/${id}&#96; | body: JSON.stringify(data) | 未显式声明 | 3 | apps/desktop/src/renderer/domains/workflows/api.ts:148 | 待逐项核对；局部已验证项见上表 |
| service:workflowBundleApi.export | POST '/workflow-bundle/export' | body: JSON.stringify({ name, content }) | { success: boolean; bundle?: unknown; error?: string } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:471 | 待逐项核对；局部已验证项见上表 |
| service:workflowBundleApi.import | POST '/workflow-bundle/import' | body: JSON.stringify({ bundle }) | {       success: boolean       name?: string       workflow?: { nodes: unknown[]; edges: unknown[]; variables: unknown[] }       restored?: { customModules: number; images: number }       error?: string     } | 1 | apps/desktop/src/renderer/domains/workflows/api.ts:476 | 待逐项核对；局部已验证项见上表 |

## 事件订阅与发送

| 事件 ID | 订阅位置 | 发送位置 | 状态 |
|---|---|---|---|
| event:ask_ai | apps/desktop/src/renderer/domains/workflows/components/assistant/AIAssistantPanel.tsx:450 | apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx:337; apps/desktop/src/renderer/domains/workflows/components/LogPanel.tsx:174 | 字段/关联身份/恢复语义仍需核对 |
| event:beforeunload | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:597; apps/desktop/src/renderer/app/StudioApp.tsx:19 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:build_progress | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:456; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:493; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:518 | 字段/关联身份/恢复语义仍需核对 |
| event:close_auto_browser | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:789 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1578 | 字段/关联身份/恢复语义仍需核对 |
| event:close_documentation | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:787 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1570 | 字段/关联身份/恢复语义仍需核对 |
| event:close_global_config | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:781 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1546 | 字段/关联身份/恢复语义仍需核对 |
| event:close_local_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:785 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1554 | 字段/关联身份/恢复语义仍需核对 |
| event:close_scheduled_tasks | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:783 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1562 | 字段/关联身份/恢复语义仍需核对 |
| event:close_variable_tracking | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:791 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1586 | 字段/关联身份/恢复语义仍需核对 |
| event:command_error | apps/desktop/src/renderer/domains/workflows/events.ts:291 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:connect | apps/desktop/src/renderer/domains/workflows/events.ts:299 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:disconnect | apps/desktop/src/renderer/domains/workflows/events.ts:319 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:download_data | apps/desktop/src/renderer/domains/workflows/components/LogPanel.tsx:330 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:994 | 字段/关联身份/恢复语义仍需核对 |
| event:editingModuleChanged | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:211 | apps/desktop/src/renderer/domains/workflows/lib/customModuleEditing.ts:50; apps/desktop/src/renderer/domains/workflows/lib/customModuleEditing.ts:100 | 字段/关联身份/恢复语义仍需核对 |
| event:editor_screenshot_captured | apps/desktop/src/renderer/domains/workflows/components/assistant/AIAssistantPanel.tsx:441 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1622 | 字段/关联身份/恢复语义仍需核对 |
| event:execution_stop | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/events.ts:826 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:completed | apps/desktop/src/renderer/domains/workflows/events.ts:563 | apps/desktop/src/renderer/domains/workflows/events.ts:618 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:data_row | apps/desktop/src/renderer/domains/workflows/events.ts:643 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:data_row_batch | apps/desktop/src/renderer/domains/workflows/events.ts:654 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:input_prompt | apps/desktop/src/renderer/domains/workflows/events.ts:520 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:js_script | apps/desktop/src/renderer/domains/workflows/events.ts:530 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:log | apps/desktop/src/renderer/domains/workflows/events.ts:451 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:log_batch | apps/desktop/src/renderer/domains/workflows/events.ts:487 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:node_complete | apps/desktop/src/renderer/domains/workflows/events.ts:363 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:node_start | apps/desktop/src/renderer/domains/workflows/events.ts:356 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:paused | apps/desktop/src/renderer/domains/workflows/events.ts:370 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:play_music | apps/desktop/src/renderer/domains/workflows/events.ts:535 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:play_video | apps/desktop/src/renderer/domains/workflows/events.ts:544 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:resumed | apps/desktop/src/renderer/domains/workflows/events.ts:375 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:started | apps/desktop/src/renderer/domains/workflows/events.ts:337 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:stopped | apps/desktop/src/renderer/domains/workflows/events.ts:665 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:tts_request | apps/desktop/src/renderer/domains/workflows/events.ts:525 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:execution:view_image | apps/desktop/src/renderer/domains/workflows/events.ts:553 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:export_logs | apps/desktop/src/renderer/domains/workflows/components/LogPanel.tsx:327 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:989 | 字段/关联身份/恢复语义仍需核对 |
| event:export_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:772 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:570; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:28 | 字段/关联身份/恢复语义仍需核对 |
| event:fit_view | apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:1074 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:516; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:684; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:853; apps/desktop/src/renderer/domains/workflows/components/RecorderPanel.tsx:379; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:526 | 字段/关联身份/恢复语义仍需核对 |
| event:focus_node | apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:1079 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:656 | 字段/关联身份/恢复语义仍需核对 |
| event:highlight-node | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/components/ModuleNode.tsx:92 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:custom_action | apps/desktop/src/renderer/domains/workflows/events.ts:716; apps/desktop/src/renderer/domains/workflows/hooks/useStudioIntegration.ts:76 | apps/desktop/src/renderer/domains/workflows/events.ts:718 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:macro_start | apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:1986; apps/desktop/src/renderer/domains/workflows/events.ts:695 | apps/desktop/src/renderer/domains/workflows/events.ts:697 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:macro_stop | apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:1987; apps/desktop/src/renderer/domains/workflows/events.ts:702 | apps/desktop/src/renderer/domains/workflows/events.ts:704 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:no_workflow | apps/desktop/src/renderer/domains/workflows/events.ts:690 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:run | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:733 | apps/desktop/src/renderer/domains/workflows/events.ts:678 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:run_workflow | apps/desktop/src/renderer/domains/workflows/events.ts:675 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:screenshot | apps/desktop/src/renderer/domains/workflows/components/ImageAssetsPanel.tsx:138; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:735; apps/desktop/src/renderer/domains/workflows/events.ts:709 | apps/desktop/src/renderer/domains/workflows/events.ts:711 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:stop | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:734 | apps/desktop/src/renderer/domains/workflows/events.ts:685 | 字段/关联身份/恢复语义仍需核对 |
| event:hotkey:stop_workflow | apps/desktop/src/renderer/domains/workflows/events.ts:683 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:keydown | apps/desktop/src/renderer/domains/workflows/components/InputPromptDialog.tsx:285; apps/desktop/src/renderer/domains/workflows/components/QuickModulePicker.tsx:69; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:582; apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:189; apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:1033; apps/desktop/src/renderer/domains/workflows/components/controls/confirm-dialog.tsx:45; apps/desktop/src/renderer/domains/workflows/components/scheduled-tasks/TaskCreateDialog.tsx:216; apps/desktop/src/renderer/domains/workflows/components/scheduled-tasks/TaskEditDialog.tsx:255; apps/desktop/src/renderer/domains/workflows/hooks/useStudioIntegration.ts:36 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:keyup | apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:1034 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:mousemove | apps/desktop/src/renderer/domains/workflows/components/assistant/AIAssistantPanel.tsx:205 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:mouseup | apps/desktop/src/renderer/domains/workflows/components/assistant/AIAssistantPanel.tsx:206 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:new_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:769 | apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:24 | 字段/关联身份/恢复语义仍需核对 |
| event:open_auto_browser | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:788 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1574 | 字段/关联身份/恢复语义仍需核对 |
| event:open_documentation | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:786 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1566 | 字段/关联身份/恢复语义仍需核对 |
| event:open_export_dialog | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:775 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1594 | 字段/关联身份/恢复语义仍需核对 |
| event:open_global_config | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:780 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1542 | 字段/关联身份/恢复语义仍需核对 |
| event:open_local_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:784 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1550; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:25 | 字段/关联身份/恢复语义仍需核对 |
| event:open_module_search | apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:195 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1598; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:26 | 字段/关联身份/恢复语义仍需核对 |
| event:open_scheduled_tasks | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:782 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1558 | 字段/关联身份/恢复语义仍需核对 |
| event:open_variable_tracking | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:790 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1582 | 字段/关联身份/恢复语义仍需核对 |
| event:play_music_result | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/events.ts:128 | 字段/关联身份/恢复语义仍需核对 |
| event:play_video_result | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/events.ts:135 | 字段/关联身份/恢复语义仍需核对 |
| event:refresh:image-assets | apps/desktop/src/renderer/domains/workflows/components/ImageAssetsPanel.tsx:83 | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:624; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:824; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:829; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:835; apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:847 | 字段/关联身份/恢复语义仍需核对 |
| event:resize | apps/desktop/src/renderer/domains/workflows/components/ConfigPanel.tsx:271; apps/desktop/src/renderer/domains/workflows/components/ModuleSidebar.tsx:1805; apps/desktop/src/renderer/domains/workflows/lib/globalTooltip.ts:251 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:run_single_node | apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:1092 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:860 | 字段/关联身份/恢复语义仍需核对 |
| event:run_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:755 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:549; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:554; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:20; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:21 | 字段/关联身份/恢复语义仍需核对 |
| event:run-from-node | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:396 | apps/desktop/src/renderer/domains/workflows/components/ModuleNode.tsx:165 | 字段/关联身份/恢复语义仍需核对 |
| event:save_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:752 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:544; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:23 | 字段/关联身份/恢复语义仍需核对 |
| event:scroll | apps/desktop/src/renderer/domains/workflows/lib/globalTooltip.ts:250 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:selector:healed | apps/desktop/src/renderer/domains/workflows/components/WorkflowEditor.tsx:1067 | apps/desktop/src/renderer/domains/workflows/events.ts:627 | 字段/关联身份/恢复语义仍需核对 |
| event:set_current_workflow | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/events.ts:314; apps/desktop/src/renderer/domains/workflows/events.ts:841 | 字段/关联身份/恢复语义仍需核对 |
| event:set_verbose_log | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/events.ts:310; apps/desktop/src/renderer/domains/workflows/events.ts:833 | 字段/关联身份/恢复语义仍需核对 |
| event:show_toast | apps/desktop/src/renderer/domains/workflows/components/assistant/AIAssistantPanel.tsx:428 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1454; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1527; apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1637 | 字段/关联身份/恢复语义仍需核对 |
| event:socket:reconnected | apps/desktop/src/renderer/domains/workflows/hooks/useStudioIntegration.ts:63 | apps/desktop/src/renderer/domains/workflows/events.ts:303 | 字段/关联身份/恢复语义仍需核对 |
| event:stop_workflow | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:764 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:563; apps/desktop/src/renderer/domains/workflows/lib/customShortcuts.ts:22 | 字段/关联身份/恢复语义仍需核对 |
| event:storage | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:208 | 无静态发送 | 字段/关联身份/恢复语义仍需核对 |
| event:studio:connection-error | apps/desktop/src/renderer/domains/workflows/components/StudioConnectionNotice.tsx:15 | apps/desktop/src/renderer/domains/workflows/api/transport.ts:32 | 字段/关联身份/恢复语义仍需核对 |
| event:studio:connection-restored | apps/desktop/src/renderer/domains/workflows/components/StudioConnectionNotice.tsx:16; apps/desktop/src/renderer/domains/workflows/lib/requiredFields.ts:70 | apps/desktop/src/renderer/domains/workflows/api/transport.ts:24; apps/desktop/src/renderer/domains/workflows/development/StudioMockTools.tsx:30 | 字段/关联身份/恢复语义仍需核对 |
| event:studio:transport-changed | apps/desktop/src/renderer/domains/workflows/lib/requiredFields.ts:69 | apps/desktop/src/renderer/domains/workflows/api/transport.ts:6 | 字段/关联身份/恢复语义仍需核对 |
| event:take_screenshot | apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:794 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:1602 | 字段/关联身份/恢复语义仍需核对 |
| event:upload_image | apps/desktop/src/renderer/domains/workflows/components/LogPanel.tsx:333 | apps/desktop/src/renderer/domains/workflows/api/aiAssistantSkills.ts:999 | 字段/关联身份/恢复语义仍需核对 |
| event:view_image_result | 无静态订阅 | apps/desktop/src/renderer/domains/workflows/events.ts:142 | 字段/关联身份/恢复语义仍需核对 |

## 直接网络消费入口

| 位置 | 方法与端点表达式 | 请求体 | 状态 |
|---|---|---|---|
| apps/desktop/src/renderer/domains/workflows/api/browserScriptTests.ts:5 | dynamic path | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/api/event-client.ts:42 | GET &#96;${this.baseUrl}/api/events/commands/${encodeURIComponent(commandId)}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/api/event-client.ts:53 | POST &#96;${this.baseUrl}/api/events/commands&#96; | body: JSON.stringify({ commandId, event, data }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/api/event-client.ts:102 | GET &#96;${this.baseUrl}/api/events/stream?afterSeq=${this.sequence}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/api/transport.ts:3 | dynamic input | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/api.ts:54 | dynamic url | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/api.ts:622 | GET &#96;${endpoint}/${encodeURIComponent(requestId)}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/AICodeAssistant.tsx:386 | POST globalConfig.ai.apiUrl | body: JSON.stringify(requestBody) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/GlobalConfigDialog.tsx:427 | GET &#96;${API_BASE}/api/local-workflows/default-folder&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/ImageAssetsPanel.tsx:92 | POST &#96;${getBackendBaseUrl()}/api/system/screenshot&#96; | body: JSON.stringify({ folder: currentPath &#124;&#124; undefined }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/LocalWorkflowDialog.tsx:52 | GET &#96;${API_BASE}/api/local-workflows/default-folder&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/LocalWorkflowDialog.tsx:67 | POST &#96;${API_BASE}/api/local-workflows/list&#96; | body: JSON.stringify({ folder }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/LocalWorkflowDialog.tsx:98 | GET &#96;${API_BASE}/api/local-workflows/load/${encodeURIComponent(workflow.filename)}?folder=${encodeURIComponent(currentFolder)}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/LocalWorkflowDialog.tsx:134 | POST &#96;${API_BASE}/api/local-workflows/delete?filename=${encodeURIComponent(workflow.filename)}&amp;folder=${encodeURIComponent(currentFolder)}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/LocalWorkflowDialog.tsx:161 | POST &#96;${API_BASE}/api/local-workflows/open-folder&#96; | body: JSON.stringify({ folder }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/MCPConfigPanel.tsx:80 | GET &#96;${base}/api/ai-assistant/mcp/config&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/MCPConfigPanel.tsx:81 | GET &#96;${base}/api/ai-assistant/mcp/status&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/MCPConfigPanel.tsx:102 | PUT &#96;${base}/api/ai-assistant/mcp/config&#96; | body: JSON.stringify({ config: next }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/MCPConfigPanel.tsx:124 | POST &#96;${base}/api/ai-assistant/mcp/reload&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:176 | GET &#96;${API_BASE}/api/local-workflows/default-folder&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:444 | POST &#96;${getBackendBaseUrl()}/api/local-workflows/check-exists&#96; | body: JSON.stringify({ filename, content: { _folder: currentFolder } }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:474 | POST &#96;${API_BASE}/api/local-workflows/save-to-folder&#96; | body: JSON.stringify({           filename,           content: { ...workflowData, _folder: currentFolder }         }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:614 | POST &#96;${API_BASE}/api/system/save-clipboard-image&#96; | body: JSON.stringify({ name }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:656 | POST &#96;${API_BASE}/api/system/screenshot-tool&#96; | body: JSON.stringify({ saveToAssets: true }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:816 | PUT &#96;${API_BASE}/api/image-assets/${screenshotAsset.id}/rename?newName=${encodeURIComponent(newName + '.png')}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/Toolbar.tsx:925 | GET &#96;${API_BASE}/api/workflows/${currentWorkflowId}/export-playwright&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/WebDAVSettings.tsx:30 | GET &#96;${getBackendBaseUrl()}/api/local-workflows/webdav-config&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/WebDAVSettings.tsx:42 | POST &#96;${getBackendBaseUrl()}/api/local-workflows/webdav-config&#96; | body: JSON.stringify(cfg) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/WebDAVSettings.tsx:54 | POST &#96;${getBackendBaseUrl()}/api/local-workflows/webdav-test&#96; | body: JSON.stringify(cfg) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:1998 | POST &#96;${getBackendUrl()}/api/system/macro/hotkey/start&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2003 | POST &#96;${getBackendUrl()}/api/system/macro/hotkey/stop&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2015 | GET &#96;${getBackendUrl()}/api/system/macro/data&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2053 | GET &#96;${getBackendUrl()}/api/system/mouse-position&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2075 | POST &#96;${getBackendUrl()}/api/system/macro/start&#96; | body: JSON.stringify({           recordMouseMove: recordOptions.recordMouseMove,           recordMouseClick: recordOptions.recordMouseClick,           recordKeyboard: recordOptions.recordKeyboard,           recordScroll: recordOptions.recordScroll,           mouseMoveInterval: recordOptions.mouseMoveInterval,         }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2095 | POST &#96;${getBackendUrl()}/api/system/macro/stop&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2635 | POST &#96;${getBackendUrl()}/api/system/pick-mouse-position&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/AdvancedModuleConfigs.tsx:2868 | POST &#96;${getBackendUrl()}/api/system/pick-mouse-position&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/TriggerModuleConfigs.tsx:1573 | GET &#96;${getBackendUrl()}/api/triggers/gesture/custom&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/TriggerModuleConfigs.tsx:1589 | GET &#96;${getBackendUrl()}/api/triggers/gesture/status&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/TriggerModuleConfigs.tsx:1637 | POST &#96;${getBackendUrl()}/api/triggers/gesture/record&#96; | body: JSON.stringify({           gesture_name: recordingGestureName,           timeout: 30         }) | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/config-panels/TriggerModuleConfigs.tsx:1680 | DELETE &#96;${getBackendUrl()}/api/triggers/gesture/custom/${deleteGestureName}&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/controls/coordinate-input.tsx:39 | POST &#96;${getBackendUrl()}/api/system/pick-mouse-position&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/controls/dual-coordinate-input.tsx:40 | POST &#96;${getBackendUrl()}/api/system/pick-mouse-position&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/controls/image-asset-preview.tsx:27 | GET source | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/components/controls/window-title-input.tsx:35 | GET &#96;${getBackendBaseUrl()}/api/desktop-picker/windows&#96; | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |
| apps/desktop/src/renderer/domains/workflows/lib/requiredFields.ts:40 | GET '/system/module-required-fields' | 未显式声明 | 需核对鉴权、取消、错误及资源读取 |

## 完整性边界

每个保留操作仍须登记必填字段、成功/空结果/拒绝示例、错误码、读写及幂等规则、分页上限、取消后的查询与清理，并关联 verified-cases.json 中的实际用例。上表的类型名不替代 schema 验证。

对象 Api 方法的静态扫描不能完整解析 class 方法、动态别名、运行时 URL、IPC 和资源标签请求。静态消费者数为 0 只表示本扫描未发现，不授权删除。共享 schema-only OpenAPI 已接通，不新增第二套 contracts 包。

当前扫描：151 个服务方法、82 个事件、46 个直接请求；AI 画布操作 105 项仍在 service-inventory.json 独立登记，不当作 HTTP 操作。
