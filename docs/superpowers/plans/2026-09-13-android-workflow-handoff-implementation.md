# 安卓工作流与原生窗口交接实施计划

- 日期：2026-09-13；状态：**proposed，待用户确认实施**。
- 规格：[安卓工作流与原生窗口交接](../specs/2026-09-13-android-workflow-handoff-design.md)。
- 交付目标：Mac 上一个真实安卓工作流完成“自动执行 → 人工原生窗口处理 → 自动继续 → 释放设备”。
- 本轮仅设计与计划，所有下面的实施任务尚未完成。采用 Ponytail 的现有能力优先原则，不建设设备池或另一个工作流引擎。

## 0. 实施前固定基线

- [ ] 等待本计划确认；核对 M3 已合入版本及工作区变更。当前设计读取的工作区存在其他任务未提交改动，不把这些改动一起提交。
- [ ] 读取最新 AGENTS、架构、M2/M3 决策与测试；确认单活跃运行、离开协议、进程清理新版本。
- [ ] 记录 source commit、Mac/VM/Android/客户端版本和实际镜像 digest；现有三台 Demo 设备与数据作为保留清单。
- [ ] 准备专用集成测试工作区和独立 Android container/volume；不导入旧设备，不覆盖 Notes。

## 1. 设备登记、归属与选择

后端契约/实现：

- [ ] 新增 android 设备模型、repository/provider 端口和 application 控制服务；增量迁移设备归属、占用、会话恢复记录。迁移挂实施时实际 head，不改既有迁移。
- [ ] 提供专用设备准备命令：创建新设备、校验归属、记录稳定 ID、独立卷、镜像与 workspace 归属；创建部分失败准确列出保留资源，不删除不属于本次的对象。
- [ ] Mac 平台适配器检查 Lima/ADB/scrcpy，读取真实动态 Docker 映射和 sys.boot_completed；正式进程不调用旧 Demo HTTP API。
- [ ] 运行环境独占锁、设备归属校验、统一路径来源；安装级锁目录跨工作区稳定，不能简单复用随工作区变化的缓存目录。重复控制器明确失败。
- [ ] 实现 environment/devices 列表和详情 OpenAPI。准备命令为首版部署入口，完整设备创建页面不属于本切片。

前端组件/页面：

- [ ] 生成类型后先做环境提示、设备状态卡、DeviceSelect 及组件测试，再组合简版设备页；使用真实 API。
- [ ] 工作区切换后的旧设备响应不能覆盖新列表；运行环境失联显示未知/不可达，不能显示空闲。

完成条件：真实新设备可见且可选择；旧 Demo 的 label 筛选拒绝该设备，正式接口拒绝旧 Demo 设备；缺环境与 Windows 返回明确不可用，正式应用仍正常启动。

## 2. 安卓单设备自动运行

- [ ] RunStart 增加 target union，保留旧 profileId 请求；RunRead/RunSummary 补 target 与可空旧 Profile 字段，旧历史读取兼容。
- [ ] 请求归一化保持浏览器旧哈希语义；同编号重试不重复执行，换设备重用编号冲突。
- [ ] 节点目录/category/runtime 和配置校验支持 launch_app/tap/key/screenshot；禁止混合浏览器与安卓图，错误定位节点。
- [ ] 将现有 worker 启动边界按已知两种 runtime 分派；浏览器 provider 原有执行路径保持。安卓 worker 不获得 ADB 连接，经固定 JSONL 命令调用父进程控制服务。
- [ ] 父进程限制同设备一条未完成命令、命令/消息大小与预算；设备从接受到清理一直占用。动作超时不盲重试。
- [ ] 接入现有 PNG 产物、变量、事件/SSE、run history 和停止协议；日志改为匹配实际运行资源，不对安卓说“浏览器已关闭”。
- [ ] 前端先补节点表单与测试，再接顶栏运行资源选择、截图结果与执行状态；Android 节点不依赖浏览器 Profile。

完成条件：真实“打开设置 → 自动按键/坐标点击 → 截图”运行成功；停止后 Android 与卷保留；浏览器六节点和 M3 拾取互斥回归通过。首版仍一工作区一条运行，无新排队器。

## 3. 人工节点和原生窗口交接

- [ ] 新增 android_manual 节点及 waiting_manual/resuming 活跃态；全量检查 active state 判断、数据库 active_slot、按钮、离开/quiesce blocker 和恢复路径。
- [ ] 实现 handoffId/generation/requestId 及持久化回执；每轮交接串行判定，拒绝过期节点/窗口/请求；进入人工等待前确认自动命令已结束。
- [ ] 实现 open/continue API 和固定 JSONL 控制响应；窗口打开失败可在同节点重试；关窗仍等待，继续要先持久化决定并确认窗口/连接清理。
- [ ] 从 reference 迁移已验证的固定版启动、PTY 出画面判断、专用 SSH/ADB 清理和进程身份记录，使用正式路径与生命周期，不引用 reference 运行时文件。
- [ ] 核查正式 Python 3.11 与 Demo Python 3.14 的差异，特别是下载解压和进程 API；不原样复制仅新版本支持的参数。不升级正式 Python 来迁就 Demo。
- [ ] scrcpy 用固定官方包与 server 配对，校验 SHA-256；明确由准备命令安装到受管缓存，页面不接受任意下载 URL。记录 Apache-2.0 与便携依赖许可，正式打包梳理 NOTICE。
- [ ] 人工预算、通信心跳和断连处理；超时关闭连接并失败，不推进下一节点。
- [ ] 先实现 ManualHandoffPanel、节点表单和组件测试，再接 Studio；显示提示、剩余时间、窗口状态、继续/停止与失败重试。

完成条件：完成系统设置验收流程并人工确认窗口操作；关窗不继续，点击“完成并继续”后自动 BACK/截图真实执行；期间自动命令计数为零，重复继续只推进一次。

## 4. 故障清理与重启核验

- [ ] 取消覆盖启动中、执行中、等待人工、原生连接建立中、正在继续五个阶段；并发停止优先，不被迟到 open/resume 回调逆转。
- [ ] 原生进程/SSH 由身份精确回收；不使用全局 kill-server，不处理其他用户窗口；清理失败保留占用与重试责任。
- [ ] 对 ADB 超时后 Android 动作是否结束给明确结果；无法确认时 recovery_required，不能因为本机进程没了就释放设备，也不自动停止 Android。
- [ ] sidecar 重启将运行标 interrupted；设备在遗留进程与命令核验完成前继续隔离，不重放节点。UI 刷新仅查询，不启动新任务。
- [ ] 数据库提交失败、网络响应丢失时重复原 requestId 查询/重试；不存在“后台已继续但前端重复创建窗口”。
- [ ] 离开、工作区切换、服务重启、Studio 关闭复用现有统一协议；清理确认前不退出资源门控。

完成条件：故障矩阵全通过；不能确认释放时 UI 确实显示恢复中/清理失败，第二次运行被拒绝。

## 5. 自动检查与真实验收

新增测试按行为命名并落对应目录；测试替身只验证状态和竞态，真实 Android 证据另记，不能互相替代。

| 层 | 必测分支 |
| --- | --- |
| domain/application | 两次占用竞争；waiting_manual 占活跃名额；输入门控；停止/继续竞争；旧 handoff 与 generation 拒绝；预算耗尽 |
| HTTP/数据库 | 新旧 RunStart 和历史兼容；旧 browser 哈希；同 ID 幂等；控制回执持久化；写库失败不派发；token/归属校验 |
| provider/进程 | 动态端口；启动失败；窗口退出；SSH 断线；PID 复用；EOF；超时隔离；清理重试；错误对象不含秘密 |
| React | 设备选择、不可用、忙、开窗失败、关窗仍等待、继续中禁用、倒计时、断线补读、草稿/运行标记、离开保护 |
| 真实 Mac | 新设备完整流程、人工操作、截图内容、关闭连接后数据保留、停止/重启恢复；旧三台设备仍可用 |

实现阶段运行的已存在检查入口（以下不是本轮已通过结果）：

```bash
uv run --directory apps/backend pytest -q
uv run --directory apps/backend ruff check src tests
uv run --directory apps/backend mypy src
npm test
npm run typecheck
npm run lint
npm run openapi:check
npm run test:structure
npm run test:scripts
npm run build
npm run backend:build
npm run package:dir
```

每个切片先运行相关测试；最终跑完整门槛一次。新增 `scripts/smoke-android-handoff.py` 与 Electron 冒烟入口，具体参数随实现确定，不提前提供不可运行命令。实际验证 source、冻结 sidecar、打包 Mac 三种入口；原有 browser run/inspection 冒烟按 M3 合入后的入口回归。

证据保存到 `docs/migration/android-workflow-handoff-validation.md` 与同名证据目录：版本、设备 ID、状态时间线、截图 A/B、操作次数、清理结果、人工反馈、测试命令及未测项。不录入用户在人工窗口中输入的密码、剪贴板或其他敏感文本。

## 6. 提交与退出条件

- 每个垂直切片单独清晰提交，API/生成类型/组件/测试/文档同步；不提交其他工作流任务的文件改动。
- `.ai/decisions` 记录确认后的取舍，`docs/PROJECT_STRUCTURE.md` 只在实际新增目录后更新，计划路径不冒充现有模块。
- 新设备准备失败就准确报告；不会为了赶验收转为 mock，也不会把现有 Demo 私自迁移成正式设备。
- 全部完成后交付正式入口、准备/启动说明、示例工作流、截图和恢复验证。批量、混合图、Windows 实测另行设计。

建议实施顺序：1 → 2 → 3 → 4 → 5。每一切片的测试和故障处理随该切片完成，第 4 步补跨切片故障验收，不把基本清理延期到最后。
