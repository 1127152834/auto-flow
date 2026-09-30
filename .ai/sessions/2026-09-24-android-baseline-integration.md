# Android 合入 baseline

日期：2026-09-24。状态：confirmed；来源：用户明确要求本地合并，合并后实际命令输出。

- 输入：baseline `c6e02427`（包含 PM9），Android `746c9c5b`；真实共同祖先 `31bfbb514bb2dc56cf9a4213448c06bc0ef74400`。
- 独立集成分支：`codex/android-baseline-integration`。原安卓工作区三份未提交 Studio 台账按 SHA256 检查未改变；主工作区不写入。
- 34 个文本冲突逐项合并；保留 PM9 取消/并行/项目数据与安卓隔离栈、控制、镜像、数据维护。新增 `0020_merge_android_pm9` 汇合 `am01_management_operations` 与 `pm10_shared_sheet_cursors`，不改已应用迁移。
- 现有测试观察到并行 fork 对 ContextVar 栈 deepcopy 的 9 个失败；改为复制当前帧列表，52 项图运行/迁移定向通过。两侧旧 head 的真实 SQLite 升级与重复升级保留原数据。
- OpenAPI 与 Studio 派生台账从合并代码重新生成；保留 213 源节点与 3 个 PM9 扩展，不恢复退休通知节点。
- 同时存在 Studio 集成任务，已协调采用串行 `--ff-only` 更新 baseline；本任务不推送。
- 合并树完整回归：后端4466 passed/103 skipped/2 warnings（1174.05s），前端429文件/5725 passed（212.80s）；类型、lint、OpenAPI、构建、脚本104、结构4通过，独立复审无未解决Critical/Important。测试变量字段基线的独立增量14+1+1=16已修正并完整重跑。
- 验证细节和最终状态见 `docs/qa/android-management/2026-09-24-baseline-integration.md`。原 Android 与 PM9 的真实验收阻塞保留，本地代码合并不意味着 releaseAccepted。
