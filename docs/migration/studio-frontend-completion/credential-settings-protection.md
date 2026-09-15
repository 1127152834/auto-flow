# 凭据设置读取及提交保护

2026-09-14，confirmed，有界F2/F5实现。

独立CredentialSettings从GlobalConfigDialog提取，保留正式全局配置入口及控件。列表验证success和打码元数据结构，读取失败可重试且不冒充空库；未确认列表前禁止写操作。保存要求明确success=true，失败保留表单；空字段名和重复修剪后的字段名阻止保存；Object.fromEntries构建字段字典。保存/删除串行，提交字段在等待期间锁定；删除失败不静默刷新。

读取及提交按连接修订/挂载状态检查。服务变化保留原编辑内容但不发送到新服务，用户可取消原编辑后刷新新服务列表；这不等于完整工作区切换前的草稿协调。Mock说明准确反映仅保存打码元数据，未声称已经加密或验证凭据。

新13项及原有保存失败用例共14项通过；初始9项失败并有1个未处理错误。TypeScript、ESLint、49脚本及构建通过。全量269文件3123项通过，470.41秒，涵盖此前录制/资源批次。证据evidence/f5-credential-settings。实际浏览器UI覆盖重复字段阻止、修正保存、刷新与打码回显；没有真实密码或后端加密验收，详见browser-validation.md。

仍待完成：凭据改名和已有字段删除语义、名称引用语法、完整生成合同/并发修订、全局配置标签/关窗离开保护。具体来源和后续要求见credential-contract-gaps.md。本批不能代表F2或F5整体关闭。

## 2026-09-15：独立改名与引用提示专项

本节覆盖 F5.3 的凭据改名 UI 和引用命名提示，不关闭已有字段删除/改名能力。

冻结 `reference/WebRPA/frontend/src/components/workflow/GlobalConfigDialog.tsx:182` 将编辑后名称直接交给 upsert；冻结 `backend/app/api/credentials.py:52` 和 `services/credential_manager.py:191` 已有独立 rename。当前 CredentialSettings 使用已迁入 credentialApi.rename 单请求改名，内容编辑锁定原名称，不以另建记录冒充改名，不串接 upsert/delete。保留原布局、打码列表、空值保留及设置离开保护。改名时隐藏字段值，明确保留字段和值、已有工作流引用需手动更新。

引用提示依据冻结 `executors/base.py:654–673`：按第一个点分隔名称与字段；无字段时使用 value；解析器去除两端空格、引用内部不接受花括号。提示凭据名不要含点/花括号、字段名不要含花括号、两端不要留空格；不自动修改或禁止加载历史名称。

字段服务仍只合并：省略不删除、空值保留；现有 credential-protocol.test.ts 已锁定该语义。因此暂时锁定已有字段名及删除按钮，新增未保存字段仍可修改或移除，显示服务限制。这是防止误导的过渡保护，不代表已批准字段删除/改名缺口完成。后续须独立原子字段变更合同，不能要求前端读取明文或删除重建整个凭据。

新增 `apps/desktop/src/renderer/domains/workflows/tests/credential-rename-entry.test.tsx` 5 项，全部通过真实 GlobalConfigDialog → 凭据库 → CredentialSettings/API/Mock：

- 单次 rename，保存后切标签重新进入，原字段/说明/创建时间保留、旧名称消失；编辑不读取原值，Mock 不存测试明文。
- 直接取消不写；改名草稿切标签触发既有离开保护，取消保留输入。
- 服务失败保留原记录和新名称输入，关闭错误提示后可重试；无 upsert/delete 重放。
- 目标名称冲突展示错误，两条原凭据不变。
- 含点历史名称保留、解析提示可见；已有字段不能假删除/改名，新草稿字段可增删，保存保留原字段。

验证命令：`npm --workspace @autoflow/desktop test -- src/renderer/domains/workflows/tests/credential-rename-entry.test.tsx src/renderer/domains/workflows/tests/credential-settings-protection.test.tsx src/renderer/domains/workflows/tests/credential-save-failure.test.tsx src/renderer/domains/workflows/tests/settings-leave-protection.test.tsx`。输出：4 files passed，53 tests passed，5.17 秒。两改动 TSX 文件 ESLint 通过。本次桌面 typecheck 被并行 common-advanced-config.test.tsx 的类型错误阻断，本切片无诊断；不记作全项目类型通过。

边界：JSDOM 组件交互及现有 Mock 元数据持久化，不是 Electron 原生 UI、真实加密落盘、运行时秘密注入或原子字段变更验收。未修改共享 Store/API/协议/Mock/主实施台账。

### 后续完成：字段管理入口（2026-09-15）

上一节的「已有字段只能暂时锁定、字段操作待合同」结论现已被此切片取代：列表增加「管理字段」，从打码元数据批量改名/删除并独立原子保存；普通内容编辑锁定旧字段是为了不与 upsert 合并混淆，用户可以在管理字段入口完成操作。冲突/取消/最后字段保护、提交后响应丢失以同 ID 恢复均通过真实组件入口测试。字段专用表单只显示打码值，不索取秘密值。完整命令和边界见 credential-protocol-contract.md 的「原子字段变更合同与消费闭环」。F5.3 凭据前端/Mock 字段缺口可关闭，真实后端安全持久化继续按明确交接处理。
