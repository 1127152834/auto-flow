# M2 实施与验收计划

规格：../specs/2026-09-13-automation-studio-m2-design.md（用户确认）。

## 批次

- [x] A：运行契约、迁移、独立 worker、真实 open_page、停止与持久化日志贯通。
- [x] B：六节点、顺序/变量校验、统一预算、截图与结果产物。
- [x] C：可补读 SSE、日志/结果/最近运行、>64KiB结果。
- [x] D：运行快照编辑隔离、资源占用、关闭/退出/换区、重连和崩溃恢复。
- [x] E：受控网页、开发/构建/冻结/打包验证，工程检查及证据记录。

## 分工及预检

| 任务 | 产出与消费 | 检查/裁决 |
|---|---|---|
| 纯规则 | PreparedWorkflow/prepare_run/resolve_node_config → 服务与 worker | 根任务维护唯一定义，文档快照与补全后的执行文档分开 |
| worker | execute/stop/shutdown → 运行服务 | 最终返回必须已经清理，事件先结果引用后DB提交，不直接确认终态 |
| 服务/API | OpenAPI DTO → 前端生成类型 | 先固定规格里的字段；后端生成后前端只引用生成类型 |
| UI/主进程 | prepareLeave → 保存、停止、quiesce | 组件归前端任务，主进程顺序归根任务，避免重叠修改 |
| A/B/C/D | 用户行为共同依赖 | 平行实现独立文件，按批次联调验收；不并行编辑共享文件 |

## 执行规则

复用现有依赖与正式目录；不引入通用任务框架。不触碰无关 dirty 文件或 reference 代码。先局部测试再整体检查。最终提交仅包含 M2 相关修改。验收事实与剩余平台边界写 docs/migration/automation-studio-m2-validation.md。


## 批次证据索引

| 批次 | 已执行验证 | 完成依据 |
| --- | --- | --- |
| A | 源码与冻结后端实际运行未保存草稿、同编号幂等、独立浏览器清理，SQLite重读 | `automation-studio-m2-qa/source.json`、`frozen.json` |
| B | 六节点/参数分支/变量/超时/标签页/240 KB结果/真实PNG | 同上及纯规则/worker测试 |
| C | events分页、SSE按序号续读、重新打开后读取结果；hook去重、产物按需读取 | API脚本、run-api与组件/hook测试 |
| D | Electron真实关闭/退出/换区取消，放弃停止后关窗；数据库瞬时失败注入；独立进程组异常清理 | Studio脚本、运行集成、进程补充验收 |
| E | 全量工程检查、M1原完整13项Electron回归、开发和打包入口 | `docs/migration/automation-studio-m2-validation.md` |

复审发现的持久化停止失败、隐藏截图selector误校验、旧响应覆盖新运行、worker异常后节点标记错误均修复并有针对性测试。真实Chromium独立进程组的兜底清理已通过7项真实进程验收及二次复审；D/E完成。后端516项、桌面400项，最终冻结后端8组真实API场景与正式目录包3组UI场景通过。Windows实机及未测试配置组合明确记录在验收报告中。
