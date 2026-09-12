# Automation Studio M2 验收记录

- 日期：2026-09-13
- 依据：[批准规格](../superpowers/specs/2026-09-13-automation-studio-m2-design.md)、[实施计划](../superpowers/plans/2026-09-13-automation-studio-m2-implementation.md)。
- 参考：只读 `reference/WebRPA@5ccb900e8dcf1530aae66f676d87593c416c7ebb`。没有将旧 WebRPA 服务或前端作为正式运行依赖。
- 状态：M2实现完成；macOS arm64源码、开发URL、构建HTML、冻结后端与正式目录包均已实际验收。Windows尚未实机验收。
- 置信度：已记录的实际通过项为高；Windows 和未测试的配置组合为未知。

## 实际交付

正式 Studio 在原有编辑器上增加 Profile 选择、运行/停止、节点进度、可折叠日志/结果/历史区域。运行当前未保存草稿，不自动保存，运行期间编辑、撤销、手动保存保持可用；日志与结果始终来自启动快照。当前页、运行变量和临时浏览器均独立于编辑状态。

六节点通过真实 CloakBrowser 执行。SQLite 增量迁移 `0006_workflow_runs` 持久化运行快照、顺序事件和产物元数据；SSE 只是通知渠道，客户端从持久化序号补读并去重。完整 JSON/PNG 通过鉴权产物 API 按需读取，不进入大体积进程消息。运行没有队列、自动重试、条件、循环、Debug、录制或元素拾取。

## 实现边界与异常处理

| 边界 | 实现与验证依据 |
| --- | --- |
| 运行校验 | `domain/workflows/run_validation.py` 复用 M1 结构/字段诊断，再校验单链、变量初值依赖和执行前输出可用性。可选缺省补默认值，显式错误不覆盖。保存草稿门槛保持独立。 |
| 运行协调 | `application/workflows/runs.py` 冻结输入与非凭据 Profile 快照、幂等 runId、单活跃名额、资源锁、停止和异常补写。 |
| 清理与执行 | `infrastructure/process/workflow_worker.py` 管理一次运行一个 worker；六节点、统一超时、当前页语义在 `providers/browser/workflow_executor.py`。 |
| 原子事件 | 节点状态/结果引用和事件在一个 SQLite 事务提交，之后才唤醒 SSE。最后一次落库失败保留待补写责任，恢复后有界重试；停止本身不依赖日志写入成功。 |
| 文件 | `workflow_artifacts.py` 负责结果与 PNG、路径约束、独占创建、外部目标副本、登记产物读取及 symlink 校验。 |
| 前端 | `useWorkflowRun` 独立于编辑历史；命令世代屏蔽旧运行核实响应。无节点错误事件的 worker 失败也显示终态失败，不停留在执行中。 |
| 桌面 | 沿 M1 `prepareLeave` 先保存后停止，再进入 quiesce/sidecar 退出。取消保持运行；主窗口单独关闭不停止 Studio。普通连接恢复不重启服务。 |

## 场景与证据

真实网页由 `apps/backend/tests/fixtures/workflow-page.html` 提供，包含延迟/隐藏/移除元素、输入控件、弹窗、长页面、可核对值和大文本。脚本克隆已安装内核到自己拥有的临时工作区；不改变用户配置、凭据或登录态，不依赖第三方网页。

| 场景 | 验证方式与结果 |
| --- | --- |
| 六节点、未保存运行 | Source 与冻结后端真实完成打开→输入→点击→等待→提取→PNG；接口确认工作流列表仍为空，相同 runId 不重复执行。通过。 |
| 顺序、变量、预检 | 领域/契约测试覆盖节点数组重排、单链、分支/回环/孤立、非法初值、循环依赖、前向输出、Unicode 标识符、替换一次、输出覆盖；真实页面使用中文变量并核对提取结果。通过。 |
| 输入/选择器 | 真实替换、追加、空文本、容器内控件、contenteditable、多匹配首个、CSS 与 XPath。通过。 |
| 等待/标签页 | 真实四种等待状态；跟随开启/关闭、无弹窗、单击/双击/右键。通过。 |
| 提取 | 真实 textContent（含隐藏子文本）、HTML、value、原始 href/src、缺失属性 null、属性字典；240,000 字节中文提取值完整读取。通过。 |
| 截图 | 真实整页/视口/元素 PNG，默认/相对目录/绝对 `.PNG`、工作区副本、同名拒绝、相对目录越界拒绝。通过。 |
| 超时与停止 | 真实正小数超时、失败后不执行后续动作；长等待停止后无后续点击且浏览器退出。启动时暂停真实Chromium、挂起HTTP导航、真实字体阻塞截图期间停止均通过，清理无残留。 |
| 日志恢复 | 真实分页大小 2、连续序号无重复、SSE 指定 afterSeq 重放；服务重启后记录和产物仍可读且页面动作不重放。前端测试验证断流、重连、去重与原请求恢复。通过。 |
| Profile/会话 | 真实 `ja-JP`/`Asia/Tokyo`；每轮 cookie 为空、localStorage 无继承；配置起始网址从未访问；所用 Profile/内核删除返回409，第二轮同时启动返回409。通过。 |
| 草稿隔离 | Electron 真实鼠标配置/连线六节点并运行；运行时改名保持草稿，运行名仍为启动值，差异提示出现；真实读取 JSON 和图片。通过。 |
| 离开 | Electron 原生 close/app.quit/工作区确认的取消均保持运行；放弃并停止后原生窗口才关闭。前端交互测试覆盖新建/打开/保存并停止、保存失败不停止、取消不停止、锁定期间不启动。通过。 |
| M1 回归 | 同一 M1 Electron 脚本通过13个检查点：保存往返、拖动/历史/剪贴板、单窗口、工作区切换与真实失败回滚、主窗独立关闭、退出重启、未完成稿和真实 revision 冲突另存。见 [机器记录](automation-studio-m2-qa/m1-regression/built-html.json)。 |
| 当前页关闭与进程异常 | 真实弹窗中的关闭按钮执行window.close后，下一节点返回workflow_page_closed，不切到仍存活的opener；SIGKILL worker、SIGKILL sidecar并暂停浏览器后，已捕获PID/组及本轮内核进程均归零。重启同一工作区原运行变interrupted，未产生新浏览器或页面请求。见[7项机器证据](automation-studio-m2-qa/worker.json)。 |
| 数据库失败 | 故障注入覆盖停止日志写失败仍取消、终态写失败多入口补写、持续失败503、提交确认丢失不重复、shutdown 读写全失败仍清理；清理失败另覆盖保留资源锁/名额、非终态查询、HTTP停止重试和shutdown重试；独立二次审查通过。 |

基础 API 机器证据：[源码](automation-studio-m2-qa/source.json)、[冻结后端](automation-studio-m2-qa/frozen.json)。Studio：[构建 HTML](automation-studio-m2-qa/built-studio.json)、[开发 URL](automation-studio-m2-qa/dev-studio.json)、[正式目录包](automation-studio-m2-qa/packaged-studio.json)。

## 与 WebRPA 的行为对应和有意修正

| 参考位置/行为 | AutoFlow M2 |
| --- | --- |
| `backend/app/executors/basic.py` 的点击/输入多处 `timeout` 默认30，等待另用 `waitTimeout` | 全部采用 M1 唯一 `timeoutSeconds=60`，正小数有效；节点内所有阶段共享总预算。 |
| `basic.py:765–832` 中输入 `clearBefore=false` 最后仍可能走 fill，未知目标存在 keyboard 降级 | 明确追加与替换，限定可编辑目标；没有明确目标即失败。逐字输入不在 M2。 |
| 旧执行器调用 `switch_to_latest_page`，并含选择器提示自愈 | 跟随只针对本次点击产生的新页；当前页关闭即明确失败；M2 不偷偷切页、自愈或重试动作。 |
| 提取 text/HTML/属性等动作 | 保留六项已确认模式，textContent 语义、href/src 原始值、缺失 null；完整结果文件化。 |
| M1 元素截图选择器与截图路径配置 | 元素模式严格要求 selector；整页/视口不使用隐藏 selector；PNG 独占写入、自定义路径保留工作区副本，不覆盖同名文件。 |
| 旧全局运行上下文与表达式能力 | 普通变量引用保留，不执行表达式；每轮复制初值与输出，顺序覆盖不回写文档。 |
| 旧产品的管理/复杂编排能力 | 本次不迁移企业、Windows 控制、发布和版本管理；控制流、录制、Debug 按后续阶段单独实现。 |

macOS CloakBrowser 145 的显式语言配置补充原生 `--accept-lang`；真实页面已证实必要性。相关上游记录：[CloakBrowser discussion 376](https://github.com/CloakHQ/CloakBrowser/discussions/376)。没有通过注入 JS 修改 navigator 的方式掩盖启动参数错误。

## 工程检查与复验

| 检查 | 当前结果 |
| --- | --- |
| 桌面 Vitest | 61文件、400项通过。 |
| 后端 pytest | 516项通过，两个既有依赖弃用提示。 |
| TypeScript / ESLint | 通过。 |
| Ruff / mypy | 全量通过；144源文件类型通过。 |
| OpenAPI / structure / scripts | 通过；结构3项，脚本集合12项（包含结构用例）。 |
| 构建 | renderer/main/preload、PyInstaller冻结后端、macOS arm64目录包通过；已重新冻结并用最终包完成真实六节点及离开保护。 |

```sh
npm test
npm run typecheck
npm run lint
npm run openapi:check
npm run test:structure
npm run test:scripts
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check src tests
uv run --directory apps/backend mypy src
npm run build
npm run backend:build
npm run package:dir
npm run smoke:runs
npm run smoke:runs -- --executable apps/backend/dist/autoflow-backend/autoflow-backend
npm run smoke:studio:runs
npm run smoke:studio:runs -- --dev
npm run smoke:studio:runs -- --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow
npm run smoke:studio -- --qa-directory docs/migration/automation-studio-m2-qa/m1-regression
uv run --directory apps/backend python ../../scripts/smoke-workflow-worker.py --kernel-directory /absolute/path/to/chromium-version
```

脚本可用 `--kernel-directory` 显式指定现有内核；两个 M2 Node 脚本默认从当前 macOS 已安装目录查找。Windows 复验需在真实 Windows 主机提供对应内核及打包路径。

## 实测平台边界

macOS arm64已运行实际CloakBrowser 145.0.7632.109.2、Electron开发URL、构建HTML、源码及冻结sidecar，并完成正式`.app`的运行/结果/关闭保护。Windows 有分支测试，不计作 Windows 实机通过。当前目录包用于本地验收，未签名、未发布。浏览器当前页关闭用真实页面按钮触发window.close，未点击操作系统的浏览器红色关闭按钮；工作台自身原生关闭/退出已实际验证。

本次真实运行使用公共内核、无头、本地直连、显式语言/时区；付费内核 License、真实代理服务、扩展与动态 GeoIP 组合沿用已有参数路径和隔离测试，尚未逐组合实机验收。不将这些配置组合声称为本轮已验证。M2 没有增加未保存草稿的崩溃恢复；已持久化运行的崩溃状态不会触发自动重放。


正式包截图：[六节点与真实日志](automation-studio-m2-qa/packaged-logs.png)、[真实截图预览](automation-studio-m2-qa/packaged-results.png)、[运行中离开确认](automation-studio-m2-qa/packaged-leave.png)。所有独立复审发现均已闭合；最后git差异与暂存范围检查通过。
