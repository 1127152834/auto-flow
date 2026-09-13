# Studio 路线调整与 M6 检查点

日期：2026-09-13。状态：confirmed（已执行的保护/核对）；迁入实施待具体架构确认。

用户最新请求替代 M6 实施：以 WebRPA 原 UI、前端交互和后端逻辑为主体重新开发 Studio。已停止继续扩展 M6；没有删除 M1–M5 已实现版本或用户数据。

用户追加授权可以完全重构并弃用此前代码。规格已据此取消旧编辑器兼容和旧图转换要求；新实现以原 WebRPA 为唯一产品基线。归档不等于继续维护旧引擎，旧数据保全不等于承诺能在新引擎直接执行。

M6 未完成改动共 37 个文件保存于分支 `codex/m6-unfinished-checkpoint-20260913`，提交 `59ae8d4462b3384b321ba8c7ca8e913cbbb5774b`。使用独立 Git index 建树/提交，未切换用户当前分支；逐文件校验 checkpoint blob 等于工作树原字节后，只恢复自己修改的 25 个 tracked 文件及移出 12 个已归档新文件。175 个无关文件 SHA-256 前后未变，用户原 index 保持无 staged 更改。

M6 的实际试验未通过：本地页面可打开，但录制断言仅得到 navigate，未得到预期 input/check/click；所选工作流测试 29 failed / 120 passed。检查点不是交付，不能标为 M6 完成。相关临时测试进程已返回退出结果，不继续修复已被替代的路线。

移出未完成改动后，执行 `cd apps/backend && uv run pytest tests/unit/test_workflow* tests/contract/test_workflow* -q`，149 passed，2 个依赖弃用警告，16.56 秒。此为当前旧版回归验证；没有声称新 UI、浏览器迁入或打包通过。

文档检查：`npm run test:structure` 3 passed；`git diff --check` 通过；新规格/计划/决策中的 4 个 Markdown 文件链接均可解析。

新增正式 source-migration 设计和实施安排，历史 M6/里程碑/能力表增加替代说明。未修改原本 dirty 的 `.ai/memory/project-context.md`、模型管理决策、`docs/automation-studio/PLAN.md` 或其他无关 UI 文档。

下一步：按已产出的具体架构确认后，S0 核对依赖/源运行基准，S1 直接迁原编辑器和 Store、接真实保存及正式窗口。避免恢复六节点自定义重写路径。源提交固定 `5ccb900e8dcf1530aae66f676d87593c416c7ebb`，活跃数据库 head 仍为 `0008_workflow_debug`。
