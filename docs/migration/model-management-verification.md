# 模型管理实现与验收记录

- 日期：2026-09-12
- 状态：confirmed；独立分支实现完成，本机验收通过，尚未合并。
- 分支：`codex/model-management`，基点 `ad08bdb`；worktree：`/Users/zhangtiancheng/Documents/projects/autoflow-model-management`。
- 平台：macOS 26.4.1 / arm64；Python 3.11、Electron 41.10.3。
- 依据：[设计规格](../superpowers/specs/2026-09-12-model-management-design.md)、[API 契约](../references/model-management-api-contract.md)、[交互矩阵](../prototype/model-management/model-management-interactions.md)、[源码复用记录](model-management-source-map.md)。
- 置信度：本机实现和测试证据高；未验证平台及线上供应商状态未知。

## 已实现范围

实现供应商预设目录、三步接入、直接编辑、目录发现、连接测试、供应商启停/删除，以及本地模型的添加、编辑、标签、上下文、测试、启停和移除。页面采用已确认的暖灰/黏土棕主题、278px 供应商栏和 285px 左摘要模型编辑窗；反馈留在原位置，不新增 Toast 或关闭确认。

后端提供 14 条本地 HTTP 接口，按 adapter/application/domain/provider/infrastructure 分层。前端组件只消费 OpenAPI 生成类型；API Key 仅写系统凭据存储，读取 DTO/数据库只保存配置状态或随机引用。新增迁移 `0002_model_management`，不读取或迁移旧项目数据。

当前分支从健康页基线加入模型工作台，顶部导航仅注册本分支已实现的模型入口。浏览器、代理及其他线程的应用导航在后续合并时统一组合，不在此分支复制其他线程未提交的页面。

## 验证命令与结果

以下命令均在本隔离 worktree 执行；未在原运行目录安装依赖、构建或启动测试服务。

| 命令 | 结果 |
| --- | --- |
| `uv run --directory apps/backend pytest -q` | 214 passed；2 条既有 Starlette/httpx/anyio 弃用提示 |
| `uv run --directory apps/backend ruff check .` | 通过 |
| `uv run --directory apps/backend mypy src` | 通过，72 source files；未启用 strict，不称为严格模式检查 |
| `npm run openapi:check` | 通过；生成文件与真实 OpenAPI 一致 |
| `npm test` | 13 files / 76 tests passed |
| `npm run typecheck`、`npm run lint` | 通过 |
| `npm run test:structure` | 3 passed |
| `npm run test:scripts` | 7 passed，包含上述 3 个结构检查，不重复累计 |
| `npm run build` | Electron main/preload/renderer 构建通过 |
| `npm run smoke:sidecar` | 通过 |
| `npm run smoke:desktop` | 开发 Electron 启动、认证健康检查、桌面退出后 sidecar 退出通过 |
| `node scripts/smoke-model-management.mjs` | 真实 Electron + 本地 FastAPI + SQLite + 本地 HTTP fixture 全流程通过 |
| `npm run backend:build` | PyInstaller arm64 构建通过 |
| `npm run package:dir` | macOS arm64 安装目录包构建通过 |
| `node scripts/smoke-model-management.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow` | 打包应用同一完整 UI 流程通过，使用随包后端 |

本机以唯一 UUID 创建合成凭据，使用 `SystemCredentialStore` 完成 macOS Keychain 写入→读取→删除→确认不存在。只接触本次生成条目；没有读取现有账号凭据。此结果来自开发 Python 运行时，不宣称所有发行环境的凭据授权均已验证。

打包仍使用基线的默认 Electron 图标，package metadata 缺 description/author，未作 Developer ID 签名或公证。本次产物是本地验收用目录包，不是发布安装器。

## 功能与交互证据

| 基准场景 | 实际证据与结果 |
| --- | --- |
| 供应商选择、搜索不清详情、切换保留模型筛选 | `ModelManagementPage.test.tsx`，通过 |
| 页头/侧栏同一添加入口，五列表格 | 页面测试；实际 Electron 工作台截图 |
| 首次加载、空列表、首次错误重试 | 页面条件分支、空/错误组件测试，Electron 从空数据启动 |
| 已有数据背景刷新失败 | 页面测试验证旧详情保留，并显示“重试刷新” |
| 新增目录→连接→模型三步 | `ProviderWizard.test.tsx` 与真实 Electron 点击闭环 |
| 编辑保留步骤指示、metadata直接保存/连接变更测试保存 | Wizard 测试，省略 Key 保留、空串清除按预设执行 |
| 零模型接入、选择全部包含被搜索隐藏项 | Wizard 测试；后端 connect 零模型契约测试 |
| 第三步已知/未知上下文、最终保存失败重试 | Wizard 测试，保留发现结果与选择，显示行内错误 |
| 请求中编辑字段不能重置锁或重复提交 | Wizard deferred 测试与 disabled 控件；Modal Escape/遮罩/busy 测试 |
| 目录失败仍可手输，普通添加缓存30秒，同步添加清缓存 | Editor 与页面测试；预置 fresh cache 后验证同步重拉 |
| 手动添加、编辑只读ID、复制成功/失败反馈 | Editor 测试；真实 Electron 手动添加→编辑持久结果 |
| 正安全整数/空上下文，候选无上下文保留当前输入 | schema/Editor 测试；不猜测远端未提供的长度 |
| 标签逗号、中文逗号、去重、Enter/失焦/保存、IME | Editor 测试与源码检查；真实中文输入法候选窗未人工遍历 |
| 运行默认值仅说明与description | Editor 组件核对、真实编辑窗截图；无新增采样参数 |
| 模型测试pending仍能保存并关闭 | deferred测试真实执行测试与保存双请求；保存期间锁窗并禁移除 |
| 模型ID A→B→A、关闭重开、供应商切换/被外部删除 | generation/epoch 回归，迟到测试结果不进入新上下文 |
| 嵌套移除取消与成功、焦点逐层返回 | Editor/Modal/Dialog 组件测试；真实 Electron 行级移除 |
| 连接失败后成功保存刷新反馈 | 页面测试；清旧失败反馈，使用新服务端状态 |
| 404/409 冲突保留草稿并刷新当前实例 | Wizard/Editor 用真实 ApiClientError 回归；DeleteDialog/hook 共用窄错误码 helper |
| 启停保留管理列表，options要求供应商和模型同时enabled | 后端契约/仓储测试；前端测试验证options失效 |
| 供应商删除级联本地模型，204无正文 | 后端契约及仓储断言；真实 Electron 删除后直接查 API total=0 |
| 无密钥回显、缺失/保持/替换/清空策略 | DTO、服务、协议和契约测试；合成凭据，不使用真实账号 |
| intent补偿、失败恢复、存活引用保护 | 服务故障注入测试；新Key写后CAS失败保留intent，旧配置/Key保留 |
| 原子CAS、并发删除404、成功/失败测试迟到写入 | SQL条件UPDATE/DELETE与rowcount；真实事务竞争及服务可控时序测试 |
| 协议、URL query保真、超时/大小/预览上限 | httpx MockTransport 单元测试、数据库round-trip；不等同线上协议实测 |
| Sidecar认证401、实例变化、禁止POST重放 | App 测试包括模型测试 POST 只调用一次；缓存按实例+握手代次重建 |
| 桌面启动失败/退出清理 | 常规smoke、完整smoke；独立审查额外注入失败CDP并确认子进程已退出 |

## 真实桌面流程与视觉检查

测试启动 OS 分配端口的 localhost HTTP fixture，只提供合成目录和短生成响应。空 Key 自定义兼容供应商发现两个模型，选择一个保存；调用返回合成 OK；再手动添加模型、修改名称、删除模型、删除供应商。脚本核对 API 持久结果、目录/生成确有请求、空 Key 没有 Authorization，以及 Electron 退出后 sidecar 停止。数据库和用户数据目录在 finally 清除，fixture 关闭。

主代理查看实际 Electron 截图：1440×1024 工作台、模型编辑窗、800×600 内容视口。窄视口供应商栏移到上方、页面纵向滚动，表格保持自身横向滚动。视口由 CDP Emulation 设置，不将它称为 Windows 或实际硬件屏幕验收。默认原生窗口为1440×1024，最小800×600。

- [工作台实际截图](model-management-evidence/workspace.png)
- [模型编辑实际截图](model-management-evidence/model-editor.png)
- [窄视口实际截图](model-management-evidence/workspace-small.png)

原型图片保持不变；这些截图是实现证据，不代替已确认设计资产。

## 独立审查与实施取舍

有界实现由 gpt-5.6-sol 并行承担，根代理串行处理共享文件、生成类型、集成和提交。组件与后端均经过独立复核；最后由 gpt-6-astra 完成跨组件集成审查。发现并修复了非原子CAS、URL query误裁剪、pending reset解除锁、A→B→A迟到结果、保存/删除竞态、第三步错误丢失、同步缓存未刷新、认证恢复缓存残留、外部删除导致反馈串位等问题。最终无剩余代码阻塞发现。

直接复用现有desktop shared控件，未把空的packages/ui升级为新npm包；旧品牌图标以原字节data URL集中保存。新增查询库和同族菜单primitive，不增加供应商SDK。纯URL/连接验证放在domain供用例和协议适配器共用。后端以原子SQL条件写实现CAS，没有把网络等待放入写事务。

## 未验证与后续合并

未验证 Windows x64 实机、macOS x64、Windows Credential Manager、真实中文输入法候选窗的完整人工操作、真实线上供应商目录/生成、发布签名与公证。预设保留旧项目能力与地址，不保证供应商今日开放所有旧端点或接受任意模型测试参数。

代码留在独立分支，未合并、未推送、未发布。原checkout与proxy分支仍可独立工作。后续合并须协调 `App` 导航、bootstrap装配、ORM metadata、Alembic唯一迁移head、依赖锁文件和生成DTO；不要覆盖其他线程的改动。合并后重新生成OpenAPI并运行集成回归。
