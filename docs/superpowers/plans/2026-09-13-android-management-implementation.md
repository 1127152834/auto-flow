# 安卓管理实施计划

日期：2026-09-13；状态：confirmed / implementation validated; mainline integration deferred。来源：本轮用户授权和 android-management-design.md。

1. 汇合 M4 和 Android 历史，逐处检查静默语义冲突；迁移唯一 head，生成契约。
2. 安卓 worker 复用 M4 调度，允许通用控制图、校验 runtime，按 executionId 存结果；补充真实循环交接验证。
3. 先完成设备生命周期用例/持久化/provider/HTTP及关键失败测试，再生成客户端类型。
4. 按原型完成状态卡片、创建表单、操作确认、详情及结果组件测试，组装页面并接通真实 API。
5. 执行 Python pytest/Ruff/mypy、React Vitest/tsc/ESLint、OpenAPI、结构检查、桌面构建；进行 Mac 两设备隔离和清理实测及视觉对照。
6. 更新验证记录、.ai 索引和目录说明，提交并交付可运行 Mac 应用。验证通过后安全接回主线，保留主工作树其他未提交工作。

验证：见 `docs/migration/android-management-validation.md`（仓库根目录相对路径）；Mac本期验收通过，其他平台和并行调度仍待后续实施。

集成状态（2026-09-13）：已在 `codex/android-workflow-handoff` 汇合M4并验收。最终检查发现主工作区新增尚未提交的M5调试修改，且与本轮文件重叠；未改动、stash或覆盖这些工作。主线合入待M5提交后完成，当前打包应用可独立使用。
