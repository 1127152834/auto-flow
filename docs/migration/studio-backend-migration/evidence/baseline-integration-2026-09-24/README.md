# baseline 合并验证（2026-09-24）

唯一会话记录：[Studio 合入 baseline](../../../../../.ai/sessions/2026-09-24-studio-baseline-integration.md)。

合并输入：Studio `82d26597`、PM9 `c6e02427`、Android baseline `a274c978`。测试采用独立集成工作区与临时数据库，不操作用户数据库；主仓库未提交修改保持原样。

| 验证 | 证据 |
| --- | --- |
| Studio 前端全量 5650 通过 | frontend-final.log（初始失败保留在 frontend-initial.log） |
| Studio 后端合同 728 通过 | contracts-final.log |
| 后端分批覆盖及失败修复 | backend-initial.log、backend-retries.log、backend-tail-initial.log、backend-tail-retries.log |
| Android 合并后全量前端 442 文件 / 5842 项通过 | combined-frontend-final.log |
| Android 合并后 541 项通过 | android-backend.log |
| 迁移及冲突边界 196 项通过 | android-merge-boundaries.log |
| 进程/无浏览器 54 通过、3 项 Windows 跳过 | combined-worker-runtime.log |
| 前端冲突边界 1458 项通过 | combined-frontend-boundaries.log |
| Ruff、TypeScript、ESLint、OpenAPI、目录、构建 | combined-*.log |
| 全量 mypy 的原有 65 项错误，无合并新增 | mypy-parity.json、baseline-mypy.log、combined-mypy.log |

`backend-initial`/`backend-tail-initial` 记录实际失败；其失败项已在后续复测关闭，不能把初始批次描述为一次性全部通过。worker 导出最初的单次失败未能复现，复测及连续三次重复通过，原因未知。

历史节点验收仍为 204 已验收、9 待实机；本合并没有将待实机项目或发布状态改成通过。现有 releaseAccepted=false 与跨平台缺口保持不变。此处构建证据仅为 renderer/main/preload，不是 Electron 正式包或原生端到端验收。
