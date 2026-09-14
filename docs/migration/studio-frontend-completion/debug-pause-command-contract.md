# 调试暂停身份与单步命令确认

2026-09-14；本批验证通过，F1/F3 有界批次。基于已有 DebugBar、debugStore、HTTP debug 路由及 events/commands 确认记录。

## 目标与合同

- 暂停事件新增服务端 pauseId 和 controlRevision；每次暂停生成新的全局唯一 pauseId，重复暂停事件不能当成新一轮来解除在途命令。
- resume/step 请求携带稳定 commandId、pauseId、controlRevision。服务只允许当前暂停上下文执行，过期请求 409，字段无效 422。未知动作和错误方法继续为 404/405。
- 复用 /api/events/commands/{commandId} 查询结果，不新增第二套命令历史；响应回显 workflowId、action 和暂停上下文。相同 ID 相同内容返回原确认，不再调度；相同 ID 不同内容 409。并发重送也必须共享首次处理结果。
- HTTP 响应丢失、5xx 或身份不匹配时仅查询原 commandId，不发送第二次单步；未确认时保留等待状态，停止仍可用。SSE 才能确认暂停/继续状态，HTTP 成功不直接清除暂停。
- 无服务端暂停身份的旧事件可展示，但不允许以本地计数冒充服务端身份发送继续/单步；停止保持可用。旧事件历史不改写。

## 范围边界

本批覆盖继续与单步，复用既有停止；断点更新、变量修改、独立 runId、完整服务重启/跨工作区恢复仍需后续。commandId 查询记录本阶段由 Mock 服务内存维护，不能声称后端持久化或真实浏览器执行已经完成。保留原 HTTP 路径，前端及 Mock 以新增契约为准，旧空请求不再作为可安全执行的命令。

## 验收

内存与真实 HTTP/SSE：同 ID 并发重送、跨单条/重试边界、不同 payload 冲突、旧 pauseId、错误 controlRevision、执行期间重复新命令、响应丢失后查询、下一轮同节点暂停、停止竞争、清理后的旧确认查询。组件：无身份禁用控制、重复暂停不解锁、请求待确认不自动重发、下一次真实暂停解锁、迟到错误不污染新上下文。保留既有 404/405/断点校验/停止失败用例；更新前置数据以携带真实暂停身份，不删除或放宽断言。

## 2026-09-14 验证记录

- 专项 9 文件 90 项通过；补强停止后旧确认及迟到 resumed 断言后，2 文件 14 项再次通过。
- 全量前端 257 文件、2,922 项通过（450.53 秒）。该快照不含随后新增的代码编辑器动态补全用例。
- 后端仅生成契约 DTO，13 项测试通过；Ruff、mypy（202 文件）、TypeScript、ESLint、OpenAPI 一致性、49 项脚本检查及 renderer/main/preload 构建通过。
- IAB 实际按钮完成断点→一次单步→下一暂停→停止→保存；见 evidence/f3-debug-pause/browser-ui.md。未通过 Store 注入来替代 UI 操作。
- 39 条逐项台账写入 verified-cases.json，前缀 DEBUG.pause-contract。自动化日志位于 evidence/f3-debug-pause。
- 测试命令曾误用 workspace 外路径而未找到文件，已改为 workspace 内路径运行；没有把该次无用例执行记为通过。
- F0–F6 整批未完成。正式 Electron、真实执行后端、跨工作区与服务重启仍待验收。
