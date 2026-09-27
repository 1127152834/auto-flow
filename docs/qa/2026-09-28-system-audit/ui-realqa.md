# 当前桌面应用真实 QA

- 日期：2026-09-28（Asia/Shanghai）；状态：confirmed。
- 代码：`33ae3aa49600840b1700c83723408c494dc201a8`，macOS arm64；审计前未提交的工作区状态另见总报告。
- 来源：当前编译 Electron + 生产 Python sidecar + 真正 SQLite；另用当前源码构建的 `AutoFlow.app` 完成原生补验。没有 fake provider/executor、UI store 注入或文件选择器替身。
- 场景数据：仓库 README、package.json、pyproject.toml、PROJECT_STRUCTURE.md、AGENTS.md 的实际路径、字节数和 SHA-256。独立临时工作区，未访问既有业务数据库。

## 结果

| 场景 | 实际结果 | 证据 |
|---|---|---|
| 应用启动、实际 HTTP 认证 | 正常；无 token 请求返回 401 | `ui/result.json` UI-01 |
| 通过界面创建项目 | 已创建并从 API 读回 | UI-02、`ui/02-created-project.png` |
| 真实文件元数据入库、幂等重放 | 5 条数据完整；重复请求不增加记录 | UI-03、`ui/source-manifest.json` |
| 记录详情、界面编辑 | 将真实 README 相对路径改为实际绝对路径，重新读取持久值一致 | UI-04、UI-04b |
| 6 个项目页面、5 个数据表页签、7 个全局页面 | 都可在真实服务连接状态打开；未将空态导航等同于每个功能已验收 | UI-project / UI-table / UI-global、各 PNG/JSON |
| 200% 原生缩放 | 被测页面无整页横向溢出；没有据此声称完整无障碍达标 | UI-05、`ui/05-zoom-200.png` |
| Studio 独立窗口、同服务实例 | 实际窗口正常，实例 ID 一致 | UI-06、`ui/06-studio.png` |
| 服务重启、整个应用重启 | 两者均重连成功；原 5 条数据和编辑内容仍存在 | UI-07、UI-08 |
| 打包应用原生 Excel 导出 | 实际 macOS 保存对话框，导出 XLSX；独立 openpyxl 读取 5 行，路径/字节数/哈希全部匹配 | `ui/native-export.json`、`ui/真实源码清单-原生导出.xlsx` |
| 打包应用原生 Excel 导入 | 实际 macOS 打开对话框、工作表选择、字段映射、提交；创建新表并显示 5 行，SQLite 逐值核对原表，integrity=ok/FK=0 | `ui/native-import.json` |
| 原生编辑器真实 JavaScript 工作流 | 从模块库拖入节点、编辑并保存代码，正式运行经过生产 worker 与 Electron JS 交互，再读持久结果，UA/语言/时区与实际运行环境完全一致；1 节点成功、0 失败 | `ui/native-js-result.json`、`ui/native-js-completed.png` |
| 打包应用正常退出 | 原生 Cmd+Q 后桌面 PID 消失、生产 sidecar 不再可达，启动脚本自然退出 0 | `ui/native-quit.json` |

自动 UI 批次原始结果保留为 **27 passed + 1 harness failure**，不篡改原始失败。失败是驱动的 End/Enter 没有选中 macOS 原生浏览器配置下拉框；后续原生 UI 实际选中配置，并完成同一生产 JavaScript 执行链。另有 4 个原生成功场景（导出、导入、JS、正常退出），不同口径不与 Vitest 或后端 pytest 相加。

## 校准记录与设计观察

1. 第一轮字段新增返回 200、幂等重放返回 200，驱动初版误用 201 断言，已校准。它们不是产品故障。
2. 首次重启尝试紧接内核探测，短暂处于 `api_mutation_in_progress/kernel_process_active`，等待真实空闲后成功；最终批次阻塞项为空。不作为永久无法重启问题。
3. 测试初版 API 构造工作流时误用 `type: custom` 配合 `data.moduleType: js_script`。Studio 导入层会按普通节点 `type` 恢复 moduleType，导致运行时变成 custom 并被正确拒绝。审计脚本已改 `type: js_script`；后续直接通过原生编辑器创建的工作流成功。没有将这一 422 计为 JS 执行器缺失。
4. 原 Excel 字节数字段是**文本**。原生导入首轮误映射为 number，后端正确返回 `INVALID_PROJECT_DATA`，详细指出第 2 行、第 2 列 `bytes` 必须为有限 JSON 数字。改回 string 后成功。失败导入只保留 unpublished、0 记录的 staging 表，没有发布半成品，没有污染原表。界面只显示“填写内容有误，请检查后重试”，未呈现具体定位信息；此项是错误可解释性不足，详见节点报告的追加审查。
5. Studio 页面出现 `1 '行' · '点击打开编辑器'` 等多余单引号；属于低优先级文案质量观察，没有凭截图认定功能故障。

## 边界与复现

- `node docs/qa/2026-09-28-system-audit/ui-realqa.mjs`：自动批次，依赖当前编译产物及已有公开 CloakBrowser 内核。macOS 原生 select 驱动限制仍应结合手工步骤核对，不能只看脚本退出码。
- `native-session.mjs`：启动同一 QA 工作区的当前打包应用；原生对话框、拖拽、输入、运行和 Cmd+Q 均由真实桌面操作完成。
- `native-verify.mjs`：仅在原生运行完成后只读核验 API 结果与截图，不替代执行。
- 开发构建与打包补验共用的是 **QA 创建的隔离工作区**；测试数据与数据库保留以便复核，进程已退出。
- 没有实测真实 Google Sheets 账户、付费模型、邮件收发、Telegram、生产代理、Windows/Intel 安装升级、24 小时稳定性或完整读屏键盘无障碍。

## 取样时点说明

原生导入/导出的 5 条源码清单代表取样时的真实文件大小和 SHA-256。收尾期间另一任务修改 AGENTS.md 和目录文档；本轮逐值校验针对已保存的真实样本与导出/导入结果，不代表这些文件在后续修改后仍具有相同摘要。
