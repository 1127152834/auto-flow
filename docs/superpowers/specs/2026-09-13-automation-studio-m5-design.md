# M5 调试与运行诊断

日期：2026-09-13；状态：confirmed，用户批准实施。

## 产品契约

正式 Studio 增加从头调试、顶层节点直接起跑、从头运行至嵌套节点。调试冻结草稿和启动参数，使用可见独立临时浏览器，不接管拾取或测试浏览器。单工作区资源互斥、保存和离开协议继续适用。普通运行行为不变。

暂停发生在节点调度前，参数解析/超时计时在继续后开始。暂停请求等待当前动作结束，停止立即取消。一次单步是一条调度（包含条件、循环头、终点和break/continue），不是整个块。断点每轮命中，当前放行不重复暂停。页面本身不冻结。

正常暂停允许原子新增/替换流程级变量，有限JSON、字面量处理，不执行表达式；局部只读，不与循环绑定冲突。不提供删除/重命名。运行修改不回写草稿；继续前提交有效字段。请求绑定pauseId/controlRevision防止迟到写入。失败暂停只读、只能检查与停止；停止后终态failed保留原错误。正常停止cancelled。

顶层起跑全图结构须有效，仅执行后缀检查配置/变量；声明初值解析后由字面量调试输入覆盖。缺失输入明确定位，控制终点及块内节点禁止直接起跑。运行至此执行真实前置路径，其他断点仍生效，首次目标命中解除；路径未到达则正常结束并提示。

## 架构与持久化

沿用application结构化调度与独立worker，在调度入口加入debug gate；有限命令通道只有一个stdin读取方。暂停2秒心跳/10秒失联监护，不延长动作预算。pausing/paused/failed_paused均活跃，普通重连不重启，sidecar退出不重放。

RunStart增加mode/debug；GET运行返回debug上下文；debug/commands提交稳定commandId、expectedRevision和必要pauseId，GET同ID读取原状态；同ID异内容409。确认来自worker，前端不乐观推进执行状态。stop优先。

检查点（启动/暂停/失败/结束）与变量变化写工作区诊断文件，事件只传引用。追加记录增量，局部进入退出有scope记录。既有产物索引增加purpose和独立序号，结果计数排除诊断；增量迁移增加命令记录。旧记录不伪造变量历史。

日志服务端级别/关键词/节点/执行过滤，与SSE游标分开。日志JSONL、结果ZIP清单、诊断JSON导出固定截止序号，分块传输，只读已登记文件。大值按需读取、UI有界渲染。断点为可选layout配置、手动保存、schemaVersion2不变。

## 验收

真实受控多origin页面完成嵌套断点、变量修改、单步网页动作、失败现场检查、停止清理与重启历史读取。包括局部起跑、目标未达、命令去重/过期/停止竞态、暂停超过节点预算、1000轮与大于64KiB值、导出、M1–M4回归。pytest/Ruff/mypy、前端交互/TS/ESLint、OpenAPI/迁移/目录/脚本、renderer/main/preload、PyInstaller、正式Electron包。平台实测分开记录。

子流程、异常分支、重试、录制、双视图、分组和剩余动作仍未交付。

## 落地接口与恢复约束

| 接口 | 契约 |
| --- | --- |
| `POST /api/v1/workflows/runs`、`/runs/validate` | `mode=run/debug`；debug包含start(entry/node/until)、targetNodeId、breakpoints、values；同一预检逻辑，普通模式拒绝调试参数 |
| `GET /runs/{id}` | 原运行加debug状态、pauseReason/pauseId/controlRevision、pendingNodeId/pendingExecutionId、loopPath、checkpointId、pauseDurationMs；启动debugOptions保持不变 |
| `POST /runs/{id}/debug/commands` | 稳定commandId、expectedRevision、必要pauseId；action为pause/resume/step/breakpoints/variables/page/pages；202只表示接收，应用以worker确认事件为准 |
| `GET /runs/{id}/debug/commands/{commandId}` | accepted/applied/rejected/interrupted及原响应；同ID异请求409，断线不自动重发 |
| `GET /runs/{id}/debug/variables` | checkpointId、offset/limit变量分页及after诊断索引分页；文件完整值沿原artifact接口读取 |
| `GET /runs/{id}/logs` | level/q/nodeId/executionId，afterSeq/throughSeq，tail仅用于最新窗口；与SSE连续游标分离 |
| `GET /runs/{id}/export` | kind=logs/results/diagnostics，固定throughSeq；日志可传同组筛选；结果只包含登记结果及清单，诊断单独导出 |

命令串行应用，页面操作上限10秒；停止和父进程断开优先解除等待，不经过调试命令队列。新建、打开、关闭、退出和换区仍先处理草稿，保存失败/取消都保留调试，清理成功才离开。单独关闭主窗口不结束Studio运行，活跃调试阻止显式重启服务。

实时日志缓存最多1000条，完整记录通过服务端分页读取；筛选面板最多400条，变量/诊断面板最多200项，JSON展示最多64KiB。完整值可按需读取和导出，限制展示不截断持久化文件。原生导出复核登记窗口、工作区与sidecar身份，完整流写入临时文件后才替换所选文件。
