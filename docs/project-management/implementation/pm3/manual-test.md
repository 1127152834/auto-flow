# PM3 自动化与运行管理手动验收

日期：2026-09-15。范围：自动化管理、参数批次、批次与任务目录、日志、输入输出、异常证据、普通停止、强制停止和结果恢复。Studio demo 不在本次验收范围；工作流文档和浏览器配置只作为明确标注的测试资料。用户执行状态初始均为“未执行”。

## 启动隔离版本

```bash
cd /Users/zhangtiancheng/Documents/projects/autoflow-project-management-pm3
npm run build
node scripts/qa-project-management-pm3.mjs --manual --scenario success
```

工具创建带 `.pm3-project-management-qa.json` 标记的临时所有者目录和独立工作区，复制本机已安装的公开版 CloakBrowser 内核，并启动真实 Electron、FastAPI 和 SQLite。项目与自动化必须由界面创建；工作流由 `WorkflowService`、浏览器配置由真实 Profile API 准备，结果文件会分别标记这两项夹具。终端输出 `evidence` 是本轮截图与结果目录；输入 `s` 保存当前截图，输入 `q` 退出。

若自动查找不到内核，显式传入已安装的版本目录：

```bash
node scripts/qa-project-management-pm3.mjs --manual --scenario success \
  --kernel-directory "$HOME/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2"
```

## 正常链

| 编号 | 操作步骤 | 预期业务结果 | 用户结果 |
|---|---|---|---|
| PM3-U01 | 顶部“项目”→新建项目“PM3 手测”→打开→自动化→新建自动化；选择测试工作流，填写名称与用途，依次检查基本信息、输入与参数、资源与环境、运行设置，最后统一保存 | 只有一次保存；返回目录后名称、用途、参数和资源摘要均为真实持久值；页面不显示内部 UUID | 未执行 |
| PM3-U02 | 打开该自动化→“启动运行”→固定参数输入“手测输入”→任务数 2、并发 1→确认启动 | 只创建一个批次与两个任务；按钮保存期间禁止重复提交；进入批次详情 | 未执行 |
| PM3-U03 | 在批次详情核对概览和任务表→打开任务 1 | 表格显示任务、输入标识、状态、结束节点、结束时间；不重复显示批次内部标识；任务页显示冻结自动化名和批次开始时间 | 未执行 |
| PM3-U04 | 在任务页依次打开“日志”“输入与输出”“异常与证据” | 日志按节点和持久序号显示；搜索只在 Enter/搜索按钮后执行；输入参数保留 `0`、`false`、`null`；最终业务输出、节点中间输出、证据附件分区明确 | 未执行 |
| PM3-U05 | 返回运行记录→切换批次/任务目录→搜索自动化名称、任务编号和输入值→翻页后返回 | 查询只显示匹配事实；返回保留当前目录、筛选和页码；没有内部 UUID 暴露 | 未执行 |

## 失败、停止与恢复

每个场景使用新的隔离工作区运行，避免相互污染：

```bash
node scripts/qa-project-management-pm3.mjs --scenario failure
node scripts/qa-project-management-pm3.mjs --scenario stop
node scripts/qa-project-management-pm3.mjs --scenario recovery
node scripts/qa-project-management-pm3.mjs --scenario restart
node scripts/qa-project-management-pm3.mjs --scenario isolation
# 强停需要真实不响应 worker；专项工具在隔离 Electron 后代树中受控暂停唯一 worker
node scripts/qa-project-uuid-flow.mjs --scenario runs
```

| 编号 | 操作与检查 | 预期业务结果 | 用户结果 |
|---|---|---|---|
| PM3-U06 | `failure`：进入失败任务“异常与证据”，点击内联失败截图，再点“定位对应日志” | 显示安全的具体错误、失败节点、尝试次数和真实 PNG；放大弹窗只用于查看；定位后进入对应节点日志；加载失败不显示“没有证据” | 未执行 |
| PM3-U07 | `stop`：慢页面运行中点击普通停止并确认 | 停止命令只提交一次；已接受后持续查询；全部任务进入正确终态，停止后没有新网页动作，临时浏览器目录被清理 | 未执行 |
| PM3-U08 | 运行 `qa-project-uuid-flow.mjs --scenario runs` 自动链，并只读核对输出的 `result.json`、`08-stop-dialog.png`、`09-force-stop-dialog.png`；该工具只暂停当前隔离 Electron 后代树中唯一且命令匹配的 workflow worker | 30 秒宽限前不出现强停；随后 UI 输入固定短语并提交真实强停；报告的 `synthetic-os-process-pause.processExitConfirmed=true`，旧执行代次撤权，任务与批次终态一致，浏览器和临时目录清理；这条自动故障注入不能填写为用户人工通过 | 未执行 |
| PM3-U09 | `recovery`：按工具完成启动响应及首次查询丢失注入 | 页面明确显示结果尚未确认并保留原命令身份；恢复查询只得到一个批次，不换键、不重复创建 | 未执行 |
| PM3-U10 | `restart`：终态后关闭并重启应用和服务，再打开原批次 | 持久批次、任务、日志和输出仍可读取；终态网页动作没有重放；读取失败不显示为已确认空数据 | 未执行 |
| PM3-U11 | `isolation`：核对两个隔离工作区的项目、自动化和批次 | 两个工作区身份和数据完全隔离；旧工作区/旧服务实例迟到响应不能污染当前页面 | 未执行 |

## 视觉、键盘与边界

| 编号 | 操作 | 预期 | 用户结果 |
|---|---|---|---|
| PM3-U12 | 以 1440×1024、100% 缩放逐页对照 gallery 的运行记录 004–007 | 保留顶部全局导航；主体层级、信息顺序和动作位置与画板一致；表格为统一细网格，小圆角 | 未执行 |
| PM3-U13 | 调到 200%，使用长自动化名和长日志；展开所有 Select/Popover | 应用宽度不变化；卡片和正文可换行；只有表格容器允许横向滚动；浮层不越出视口 | 未执行 |
| PM3-U14 | 全程只用 Tab、Shift+Tab、Enter、Escape；在嵌套浮层及停止确认框中操作 | 焦点顺序可预测；Escape 先关内层；危险确认默认焦点在取消；提交进行中不能关闭 | 未执行 |
| PM3-U15 | 运行时断开服务后继续停留任务页，再恢复服务 | 页面保留旧事实并提示实时更新中断；恢复后按事件序号补读，不丢日志、不重复事件、不跳到其他任务 | 未执行 |

## 证据与清理

自动场景的 `result.json` 必须记录源码哈希、构建哈希、项目/批次事实、浏览器请求和截图路径。`prepare-only` 只证明环境准备，不能记为端到端通过。API/服务夹具、CDP 故障注入、OS 进程暂停和 UI 操作分别标注，不能互相冒充。自然慢页面通常在宽限期前完成普通停止，因此不能用它要求强停入口出现。

反馈格式：`用例编号｜通过/失败/未执行｜实际操作｜实际结果｜截图绝对路径｜与预期的差异`。

退出测试应用后，只可清理终端输出的 `autoflow-pm3-run-qa-*` 目录，并先确认其父目录含专用 `.pm3-project-management-qa.json` 标记。保留仓库内 `qa-runs/run-*` 结果作为验收证据，不删除用户工作区。Windows、其他架构、打包版本和本表用户手测在未实际执行前保持“未执行”。
