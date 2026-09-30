# 参数批次并发与数据独占分配

日期：2026-09-26；状态：confirmed；实施、针对性验证与最终审查修复完成。
来源：用户明确批准并发方案，并补充“一条数据不要分配给两个工作流任务”；规格及计划见同日 parameter-batch-concurrency 文档。

## 行为

- 参数型和数据型自动化均可手填 1–100 并发/最大活动实例，启动请求保留保存值。移除数据输入不再偷偷重置并发；非法输入保持草稿并阻止保存。
- 参数任务仍原子预建队列，现有 scheduler 在请求、自动化并发、跨批次实例和 core 容量内派发。当前生产 core 上限仍为 2，不承诺填写 100 就同时运行 100。
- 统一容量计数：参数 queued 不占执行名额；数据 queued 已持有输入租约，保留名额。消除参数长队列阻塞数据领取；等待人工与归属核验继续占用。
- 数据分配沿用 BEGIN IMMEDIATE 内重新校验、原子提交 Task/Run/输入快照/租约，以及 held/reconciling lease_key 唯一索引。双线程争抢同组只成功一个，无半组任务。真实 worker 两个活动任务分别持有完整的两条输入，四个租约 key 不重复；释放后补位不抢占仍活跃任务的记录。
- 默认失败后继续来自上一提交。关闭时只取消尚未派发任务，已运行的同批任务收尾；主动停止取消全部。各任务实例独立，同任务同配置共用浏览器语义不变。

## 验证

- 初始后端 RED 13 失败 / 45 通过；实现后规则、调度、领取与环境回收回归 159 通过（1 第三方警告）。包括新 14 个并发场景、两个真实 worker 进程的 PID/持久事件/输入占用验证。
- HTTP 自动化/启动/事件契约 36 通过（1 第三方警告）。
- 前端 RED 7 失败 / 289 通过；GREEN 37 文件 / 296 通过。完整前端在实现提交 2aaf9be8 上执行：445 文件通过 / 2 失败，5875 项通过 / 2 失败；失败仍为上一轮已在 baseline 复现的 module-scope 213/216、moduleColors 216/219 数量断言。
- worker、真实浏览器初始化、共享 Sheets 来源租约集合：93 通过 / 3 平台跳过 / 1 失败；test_windows_cleanup_confirms_exit_after_kill_access_denied 的测试替身缺少 proxy_requests，原 baseline 同样复现。此测试与本轮生产修改无关，未扩范围修改。
- Ruff、3 个修改文件 mypy、TypeScript、eslint、构建、OpenAPI 一致性通过。构建保留第三方注释警告。
- 新增同模板双浏览器独立实例及取消专项 2 项通过（25.08 秒）：两个实例 ID/目录不同、同一模板未变、取消一方另一方继续并读出 signed-in；初始化回复未确认按既有中断保护处理，正常取消明确为 cancelled。原始初始化取消失败保留于 native.log；并非以重跑抹去，而是用正常取消与结果不明两个明确契约分别断言。

## 最终审查与修复

- 一次独立审查未发现新增后端调度、容量或租约问题；接受并修复两个前端遗漏：常驻但未打开的启动弹窗未跟随保存后的并发值，启动摘要仍写按顺序执行。
- 未手动覆盖时只同步启动草稿的并发值；手动覆盖后保留用户选择，切换自动化重置。摘要展示保存的配置并发上限。
- 审查修复 RED 2 失败 / 21 通过；修复后相关前端 37 文件 / 299 通过。最终补丁的 TypeScript、eslint、构建通过。未无意义重复完整前端；完整套件结果对应 2aaf9be8，最后两处界面修复由相关域回归覆盖。
- Studio 数量断言、Windows 清理测试替身、提高 core 容量及三平台打包均未扩入本轮。
- 审查日志：/tmp/af-concurrency-review-{red,green,typecheck,lint,build}.log。

## 核验边界

测试在初始化能力响应尚未确认时取消，该进程退出触发现有结果不明保护：先核验再记 interrupted。不能为界面显示取消而放宽；新增正常初始化后取消的独立断言。此前“必须 cancelled”的测试期待已更正，原失败日志保留。

本地分支基于 baseline b1ad5cb3，未改主工作区。远端 baseline 的既有落后不在本轮擅自归并。未合并、未重启用户应用、未发布；未执行三平台打包，releaseAccepted=false。
日志：/tmp/af-concurrency-{red,backend,regression,real,workers,native,native-final,contract,ui-red,ui,ui-final,frontend-full,typecheck,lint,build,ruff,mypy,openapi,worker-baseline}.log。


## 用户复查后的两项补漏（2026-09-26）

状态：confirmed（代码与针对性回归）；来源：用户要求 review 后明确授权修复。

此前“关闭失败继续则取消所有排队任务”的行为描述在数据批次分支并不完整，现已补齐；两个问题都能在原 baseline 复现，不是新并发代码引入的回归。

- 数据批次先领取两组，在第一次 dispatch 持久化后崩溃，重启会留下 interrupted + queued。原实现只关领取门，仍会派发 queued；现复用 `_stop_active_runs(stopping=False)` 取消尚未运行任务，保留运行中任务。新测试验证失败继续开关两侧、批次终态及租约释放；原运行中同伴收尾测试保持通过。
- 持续挂载的启动弹窗原来只同步保存后的并发，保存任务数 10→2 后仍用最新版本提交 10。现分别跟踪任务数与并发的手动覆盖，未覆盖值跟随保存；显式覆盖（包括非法空草稿、不限次数）保留，切换自动化重置。本轮不改变参数默认值草稿的既有规则。
- RED：后端 1 失败 / 1 通过；前端修正新增测试的按钮名称后 1 失败 / 17 通过。GREEN：后端并发/数据调度/数据领取/任务派发 78 通过、2 原生浏览器专项未选择（包含真实双 worker）；前端自动化与运行域 302 通过 / 37 文件。
- Ruff 和 scheduler mypy、TypeScript、eslint、构建通过（34.01 秒；保留既有第三方注释和混合导入警告）。未重复全量套件、三平台打包或流水线；此前完整回归的 Studio 数量断言和 Windows 替身问题仍未纳入修复，不能宣称全量绿色。
- 工作仍在 codex/automation-run-policy 独立工作区，未修改主目录 Studio，未合并、推送、发布；releaseAccepted=false。
- 复现与回归日志：/tmp/af-review-fix-{backend-red,backend-green,ui-red,ui-red-final,ui-green}.log。首轮前端除真实反例外的按钮名称错误及首次 Ruff 导入格式错误均已修正，未改业务断言。
