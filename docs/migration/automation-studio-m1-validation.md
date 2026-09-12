# Automation Studio M1 验收记录

- 日期：2026-09-13
- 状态：实现完成；macOS arm64 已执行源代码、开发 URL 和打包入口验收。Windows 实机尚未验收。
- 依据：[已批准设计](../superpowers/specs/2026-09-13-automation-studio-m1-design.md)、[实施清单](../superpowers/plans/2026-09-13-automation-studio-m1-implementation.md)。
- 参考：只读 `reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`；正式应用不导入或启动该参考项目。
- 置信度：下列已执行的功能与测试结果为高；未测试平台不作通过结论。

## 已交付结果

总览打开正式独立 Studio 窗口，同一个 renderer 构建产物通过 `?view=automation-studio` 选择入口。两个窗口共用一个本地 sidecar，分别持有 UI 状态。初次进入是空流程。

六类节点、真实画布连线与位置编辑、专用属性表单、五类变量、普通引用插入与重命名、复制剪切粘贴、撤销重做、新建/搜索打开、手动保存及快捷键均连接真实文档。SQLite 增量迁移 `0005_workflow_documents` 保存文档和布局，revision 仅用于并发控制。节点配置与默认值通过后端目录取得。

当前没有运行、录制、Debug 或模拟执行结果。截图节点仅保存配置，M1 不创建运行截图。研究目录里的旧原型不属于正式入口。

## 路径与边界

| 层 | 正式位置与职责 |
| --- | --- |
| 领域 | `apps/backend/src/autoflow/domain/workflows/`：文档、节点目录、结构校验、草稿诊断 |
| 用例 | `application/workflows/service.py`：仓储端口及创建、查询、更新用例 |
| 存储 | `infrastructure/database/workflows.py`：同表事务、稳定 ID 幂等与原子 revision 比较更新 |
| HTTP | `adapters/http/workflows.py`、`workflow_schemas.py`：现有鉴权、停写门控和错误包 |
| 前端契约 | `renderer/shared/api/generated.ts`：由 OpenAPI 生成；领域 `api.ts` 只包装真实 HTTP |
| 前端组件 | `renderer/domains/workflows/components/`：NodeCatalog、WorkflowCanvas、NodeInspector、VariablePanel |
| 编辑与页面 | `workflows/hooks/useWorkflowEditor.ts`、`workflows/pages/StudioPage.tsx`；七个测试文件集中于 `workflows/tests/` |
| 桌面生命周期 | `main/ipc/automation-studio.ts`、main/index、preload、shared/runtime；只接受登记窗口的主 frame |
| 共享连接 | `renderer/app/useDesktopSession.ts`：实例身份核验、服务恢复、工作区切换与过期响应隔离 |

## 字段映射与有意差异

| 项目 | 参考实现与 M1 决定 |
| --- | --- |
| 节点身份 | 保留六类类型名：`open_page`、`click_element`、`input_text`、`wait_element`、`get_element_info`、`screenshot`；自有文档使用 `node.type`，不持久化 React Flow 内部节点对象。 |
| 通用超时 | WebRPA `ConfigPanel.tsx:2525` 展示 `timeout`（秒），总执行器 `workflow_executor.py:1002` 也按秒读取；部分具体执行器还会转成毫秒。M1 只维护正数 `timeoutSeconds`，默认 60 秒，不再保存两套超时字段。 |
| 等待元素超时 | WebRPA `BasicModuleConfigs.tsx:354` 的 `waitTimeout` UI 默认 60；`backend/app/executors/basic.py:1036` 默认 30，再乘 1000。M1 将这项配置语义归入 `timeoutSeconds=60`，消除 UI/执行器默认值冲突。未来执行器只在浏览器适配边界转换单位。 |
| 打开网页 | `url`、`openMode=new_tab`、`waitUntil=load`；不复制旧浏览器启动参数，未来使用 AutoFlow 浏览器配置。 |
| 点击/输入 | `clickType=single`、`followNewTab=false`；`text=''` 合法，`clearBefore=true`。 |
| 等待/提取 | `waitCondition=visible`；提取 `attribute=text/innerHTML/value/href/src/attributes`，`variableName=element_value`。 |
| 截图 | `screenshotType=fullpage/viewport/element`，默认 fullpage；元素截图缺 selector 仍保持 element，并标为待完成；空 savePath 代表未来默认产物目录；输出默认 screenshot_path。 |
| 普通引用 | 保留 `{name}` 和 `${name}`，支持中文标识；重命名同步可识别引用和同名输出绑定。JSON 字面量不当作变量，复杂表达式不求值。 |
| 输出重名 | 提示问题，保留用户配置；不自动改名。 |
| 结构与草稿 | 重复 ID、悬空边、回环等拒绝；参数缺失、未连通、变量初值未完成以 issues 保存。位置和视口独立于执行图。 |

这些是新文档契约的显式裁定，M1 没有导入旧 WebRPA 文件的兼容转换器。

## 场景验收

| 场景 | 证据与结果 |
| --- | --- |
| 六节点编辑往返 | 真正点击动作库、拖动端口形成五条连线、编辑 URL/选择器/文本/变量；真实拖动节点可一次撤销、重做；手动保存后 API 和 SQLite 返回完整文档。原生关窗、应用退出再重启，通过打开列表恢复参数、变量、节点、边、位置和视口。通过。 |
| 未完成流程 | Electron 中新添空 URL 且未连接的节点，保存成功；返回问题含该 nodeId 和 URL 字段路径。单元/契约测试还覆盖条件截图缺选择器、空输出变量和不完整 JSON。通过。 |
| 历史与剪贴板 | 真正键盘删除节点及两条关联边后撤销恢复；多选复制粘贴生成六个新 ID 并保留内部五条边；参数和变量重命名的原子撤销由页面/状态测试覆盖。通过。 |
| 输入保护 | 输入框 Backspace 不删除画布节点；页面测试确认复制、剪切、粘贴、选择、撤销不拦截输入默认行为。聚焦变量名称时 Ctrl/Cmd+S 和关窗先提交合法名称。通过。 |
| 保存失败/竞态 | 真实外部 PUT 制造 revision 冲突，UI 保留当前草稿，另存后两份文档均存在。页面/状态测试覆盖离线、写入失败、丢创建响应重试、保存途中继续编辑、保存中撤销回原基线再关闭。通过。 |
| 离开保护 | 新建/打开/关闭/退出/换目录均注册相同保存、放弃、取消协议；保存失败不离开。页面测试与真实 Electron 覆盖相应入口；原生关闭和退出均实际验证取消及先保存。通过。 |
| 单窗口/主窗关闭 | 重复打开只保留一个 Studio；主窗关闭后 Studio 仍能重启服务和保存；主窗重新打开后权限仍可用。通过。 |
| 工作区隔离 | 使用两个独立临时目录：取消切换保留草稿，放弃后切换到空列表，再切回读取原流程。通过。 |
| 失败回滚 | 将已停止的空测试工作区 SQLite 改为损坏文件，触发真实目标后端启动失败；恢复原工作区后，原草稿和撤销记录保留。最小化 Studio 会先恢复显示保存问题。通过。 |
| 服务重连 | 同工作区 sidecar 实际重启，编辑组件和历史仍在，新连接可保存；迟到轮询及旧健康检查由连接 hook 回归测试覆盖。通过。 |
| 退出顺序 | 真实退出取消保留进程；保存并退出后进程正常结束、sidecar health 不可达，再启动能读取退出前保存的名称与内容。通过。 |
| 刷新保护 | Studio 拦截普通/强制刷新快捷键，聚焦时临时禁用原有刷新菜单，切回主窗口恢复。实机 Cmd+R 保留当前文档，菜单和组合键规则有单元测试。通过。 |

正常关窗验收由测试通过 Node inspector 调用实际 `BrowserWindow.close()`，没有新增测试专用 IPC。编辑由 CDP 鼠标/键盘驱动真实 DOM，网络、数据库、sidecar、目录切换与失败回滚均为真实实现。所有测试数据处于独立临时目录；退出清理不会处理用户工作区。

## 工程门禁与复验命令

```sh
npm test
npm run typecheck
npm run lint
npm run openapi:check
npm run test:structure
npm run test:scripts
npm run build
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check src tests
uv run --directory apps/backend mypy src
npm run backend:build
npm run package:dir
npm run smoke:studio
npm run smoke:studio -- --dev
npm run smoke:studio -- --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow
```

最终复验结果：

| 检查 | 结果 |
| --- | --- |
| 桌面 Vitest | 58 个文件，373 项通过；其中工作流领域 7 个文件、59 项。 |
| 后端 pytest | 438 项通过；存在两个既有测试依赖弃用提示。 |
| TypeScript / ESLint | 通过。 |
| 后端 Ruff / mypy | 全量 src/tests Ruff 通过；mypy 129 个源文件通过。 |
| OpenAPI 一致性 | 通过，生成客户端与当前 HTTP 契约一致。 |
| 结构 / 脚本测试 | 结构 3 项通过；脚本集合 12 项通过（包含结构用例，不重复计数）。 |
| 构建与打包 | renderer/main/preload 构建、PyInstaller 后端构建、macOS arm64 目录包通过。 |
| Electron 开发 URL / 正式包 | 均通过同一脚本的完整交互、保存重启、失败回滚和冲突另存用例。正式包 [机器可读结果](automation-studio-m1-qa/packaged.json)。 |
| 差异检查 | git diff --check 通过。 |

本次顺手修正两个既有后端测试的 import 分组空行，以通过完整 Ruff 门禁，没有改变其业务行为。

## 平台和产物

- macOS arm64：真实 Electron 41.10.3、开发 Vite URL、构建 HTML、打包 `.app` 与内置冻结后端均已实际运行；当前平台验收通过。
- Windows：有分支逻辑与模拟生命周期测试，尚未实际启动 Windows 应用，不计为 Windows 实机通过。
- 当前 `.app` 未做 Developer ID 签名，构建产物用于本地验收；本任务未发布安装包。
- 不增加未保存草稿的崩溃恢复；强制结束进程不属于此次正常离开保护。

正式打包入口截图：[六节点工作流](automation-studio-m1-qa/packaged-saved.png)、[离开确认](automation-studio-m1-qa/packaged-leave-confirmation.png)、[未完成配置](automation-studio-m1-qa/packaged-incomplete.png)、[并发冲突](automation-studio-m1-qa/packaged-conflict.png)。
