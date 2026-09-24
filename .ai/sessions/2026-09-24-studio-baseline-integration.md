# Studio 合入 baseline

日期：2026-09-24。状态：confirmed（集成验证完成）。依据：用户明确要求“代码合并到 baseline 分支”。

- 源：`codex/project-management-pm9@82d2659761d03b0f62b29b5a4c4d36e146e4c92e`。
- 集成起点：`codex/architecture-baseline@c6e024270c0a264bc49785fa4952a9cbf4804ccc`，已包含另一任务合入的 PM9 runtime。
- 在独立 `codex/studio-baseline-integration` 工作区处理 68 个文件冲突；主目录未提交改动、来源分支及其他任务工作区保留。
- 保留 PM9 并发 owner、人工处理/End、Windows Job、资源锁、安全产物边界；接入 Studio 的节点、项目归属、模型、凭据及交互请求。单读取命令分发兼容 capability_result 与 Studio 控制消息。
- 迁移采用新增 `0022_merge_studio_pm10` 汇合两个旧 head；不改写旧迁移、不操作用户数据库。字段元数据生成同时保留可冻结 JSON 与 Python 产物，实际接口读取包内 JSON。
- 批准范围仍为 213 个 WebRPA 节点，14 个通知节点继续排除；PM9 的 3 个项目原生节点单独计数。节点验收仍为 204 已验收、9 项待实机验收；本次合并不将待验收标为通过。
- PM9 原有 `releaseAccepted=false`、Actions 35935288512 失败及各平台外部验收缺口保留；本次不发布或推送。

## 验证

初始检查点（已被下方结果替代）：后端 pytest、前端 Vitest 及合并边界回归进行中。已完成：执行器专项 240 项、后端 507 源文件 mypy、TypeScript、OpenAPI 一致性、目录检查、renderer/main/preload 构建。最终结果以本记录后续核销为准。

上述初始进度已被下方结果替代。

## Android baseline 增量整合

- 第一次冲突整合保存为 `f0952ab8`（父提交 `c6e02427` 和 `82d26597`）。
- 合并期间，另一个已授权任务将 Android 管理合入 baseline `a274c978`。本次继续纳入该提交，保留 Android 管理、设备、备份、资源、操作及其生命周期；不覆盖或回退 baseline。
- 再增补空操作合并迁移 `0023_merge_studio_android`，父 head 为 `0022_merge_studio_pm10` 与 `0020_merge_android_pm9`。两个旧 head 的数据保留升级均已验证；用户数据库未操作。
- Android/Studio 冲突保留：录制文档归属与稳定停止命令 ID、AI 提示词变量与主模型选择、子流程与循环作用域、PM9 调度与清理语义。主目录工作差分和状态与合并前备份逐字比较一致。

## 实际验证

- Studio/PM9 检查点：前端 431 文件 / 5650 测试通过；后端合同 728 通过；单位/差分/集成分批覆盖（初始 2973 通过、77 跳过、10 失败，剩余 804 通过、47 跳过、8 失败），18 项失败修复后分别 10/10、8/8 复测通过。原始失败记录保留，没有伪称一次全绿；单次 worker 导出失败新进程复测及连续三次重试通过，初次原因未知。
- 合并 Android 后：相关后端 541 通过；24 个冲突及迁移相关文件 196 通过；进程/无浏览器流程 54 通过、3 项 Windows 测试跳过；前端受影响组件专项 1458 通过。
- 最终 Ruff、TypeScript、ESLint、OpenAPI 一致性、目录检查及 renderer/main/preload 构建通过。
- 全量 mypy **不是通过**：Android 基线原有 65 项错误（11 文件），对照 `a274c978` 后错误路径、内容、类型和数量完全一致，合并新增 0。保留原错误，不在合并任务扩展修改无关模块。证据 `mypy-parity.json`。
- 本次为代码合并验证；未新增正式 Electron UI、打包及跨平台实机验收，不改变既有节点和发布验收状态。无推送、无发布，来源分支保留。
- 证据入口：`docs/migration/studio-backend-migration/evidence/baseline-integration-2026-09-24/`。

- Android 合并后全量前端最终结果：442 文件 / 5842 测试通过，202.39 秒；见 `combined-frontend-final.log`。集成提交将通过 `--ff-only` 更新 `codex/architecture-baseline`，不推送远端。
