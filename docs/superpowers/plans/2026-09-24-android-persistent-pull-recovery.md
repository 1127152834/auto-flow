# Android 持久拉取恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 页面重建后仍能分页发现本工作区未知拉取，用户以原编号核实，不以新请求绕过未知结果。

**Architecture:** 复用现有 Operation 表、workspace 隔离、分页和 verify API；GET operations 增加可选 action/state 筛选，count 与 cursor 同范围校验。ImageManager 展示未知拉取列表，读取失败或尚有未知项时阻止新拉取，原请求重试继续可用；不自动重放或核实。

**Tech Stack:** FastAPI/SQLAlchemy，现有 React Query/原生列表与按钮；无新依赖、无 schema 变更。

## 校准与冲突（2026-09-24 confirmed）

- 基线 `30ffd12f`；唯一迁移 head `am01_management_operations`。三份已有 Studio 脏文件保留原字节，不纳入提交。
- AM-R04 缺口经只读调用链审查确证；本任务是已授权规格的有界补全，无新架构。
- ImageManager 与上一切片顺序实施，前一完整前端门禁已通过并提交；不并行写同文件。
- 另一个 Important：AM-R12 创建/拉取/备份缺空间预检，登记为下一任务；现有 ENOSPC 清理不能替代准入。需区分 VM Docker 和宿主备份文件系统，未知估计明确阻塞或原请求确认，不用固定阈值冒充估计。
- 真实桌面目前 Mac 锁屏 blocked；组件/HTTP 证据不得冒充实机。历史步骤数不因新增测试虚增。

## Task 1：持久查询契约与恢复入口

- [x] RED：在 `apps/backend/tests/contract/test_android_management_operations.py` 写数据库重建后跨 action/state/workspace 分页筛选，total、外部 cursor 拒绝与原编号 verify；运行并保存真实失败。
- [x] GREEN：修改 `apps/backend/src/autoflow/infrastructure/database/android_operations.py` 的 page/count 和 `adapters/http/android_management.py` 的只读查询参数；保持原调用默认语义，生成 OpenAPI 类型。
- [x] RED：`ImageManager.test.tsx` 增加卸载/重建、较旧记录下一页、原编号核实不重放、查询错误禁止新 pull、工作区切换不展示旧历史；运行观察失败。
- [x] GREEN：`ImageManager.tsx` 接现有 operations/verify，原生分页列表，查询 key 含 instanceId；`AndroidPage.tsx` 传入并以 instanceId 重建镜像组件。未知当前请求不能编辑清空，先核实再新拉取。
- [x] 验证：后端 operation 合同/集成；Android 前端全部、typecheck/lint/OpenAPI/build；独立增量审查，修复 C/I；保存 RED/GREEN 实际输出和源码范围。
- [x] 文档/阶段记录/提交：说明 completed、软件待办、真实 blocked。实际数据模型未变，无需空迁移。

## 验证命令

```sh
uv run --project apps/backend pytest apps/backend/tests/contract/test_android_management_operations.py apps/backend/tests/integration/test_android_management_operations.py -q
npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:generate && npm test -w @autoflow/desktop -- src/renderer/domains/android && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
```
