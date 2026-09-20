# PM9 执行卡

- 日期：2026-09-20；状态：in_progress。
- 授权：用户要求先合并有效代码到 baseline，再创建分支完成 PM9；其他平台使用现有 GitHub Actions，缺少的实机证据保留待验收。
- 输入：PM0–PM8 总计划、coverage.json、生产 bootstrap / catalog / worker 和现有验收脚本。
- 基线：`codex/architecture-baseline@8e5564e0`；实施：`codex/project-management-pm9`。
- 代码归并：Studio checkpoint 真合并为 45c114ff，Android 已授权规划真合并为 29554d93；退役 M6 / Studio 历史快照依 2026-09-17 ADR 不恢复。

## 任务与验证

1. 更新过时 PM1 冒烟为当前生产 HTTP 管理链；新增真实 Electron/打包桌面入口，共用同一断言。覆盖项目/表/字段/记录、修订冲突、原键恢复、归档恢复、隔离删除与重启持久化。`node --test scripts/smoke-project-management.test.mjs`；`node scripts/smoke-project-management.mjs`；`node scripts/smoke-project-management-desktop.mjs`。
2. 现有 CI 三平台分别运行源码、sidecar 和 Electron 打包相同验收，上传报告与安装产物。运行 lint/typecheck/build/openapi、pytest、前端和脚本测试；本机 `backend:build` / `package:dir` 后重复两份冒烟。记录真实 Actions 状态，不把 YAML 当平台通过。
3. 全覆盖核对、真实核心链探测与退出报告。复用已有万行测量/恢复测试并记录当次结果；明确四节点生产边界与未验收功能，给出核心接入设计后再按项目架构审批规则实施。

## 范围判定与预检

当前包是有界验收基础设施改动，不增加产品端点、测试后门或第二执行器；所有写操作只在本次创建的临时工作区。来源 OAuth 凭据及用户数据不进入报告。安装/原生输入/凭据实机未执行时保持未验收。

Ruling: 当前 `domain/workflows/catalog.py` 只开放四节点，`run_validation.py` 仅编译线性链。PM4–PM8 测试执行器不能抵扣 PM9 的数据节点、End 和人工完整生产闭环。先交付可真实运行的验收入口，并将跨运行时接入作为架构设计提交审查；若误判，会延后 PM9 退出，但不会伪报发行通过。

## 执行账本

- 合并检查：原定向 52 项中旧 checkpoint 的 position 必需测试失败；代码与文档均明确布局/语义分离，改为 data 必需且无 position 合法。29 项模块/差分测试、ruff、mypy 392 文件、typecheck、OpenAPI 通过；迁移冲突保留 pm08_project_sync。
- 合并快照全量后端 3155 passed / 15 skipped；前端 5445 passed / 404 文件。修复后的全量后端 3159 passed / 15 skipped，脚本测试 94 passed。
- Task 1：源码和打包 sidecar / Electron 管理链均通过；六页真实状态、原生 200% zoom 与 Studio 双窗口认证通过。
- Task 2：本机 sidecar/.app/DMG 构建通过；三平台 CI 已扩展，Actions 已启动，最新运行 35507610003（10dc916c）尚未完成，不能记作三平台通过。
- Task 3：251 条历史覆盖逐项核对，不升级状态；万行导入/分页/导出通过，完整生产接入见独立 proposed 规格。
- Final review: 独立审查发现等号 executable 参数会误跑源码及 QA 环境可混入生产验收；已规范化 cliArgs 并拒绝 QA 环境，新增入口失败检查通过。PM1 历史输出保护保留。
