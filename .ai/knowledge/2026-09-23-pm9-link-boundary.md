# PM9 环境关联跨项目身份与整组原子性

日期：2026-09-23。状态：confirmed（本机 HTTP/SQLite 与真实浏览器既有关联竞争子场景）；新生产候选三平台/打包复验 pending。来源：`apps/backend/tests/contract/test_project_environments.py`、`test_real_project_batch_http[data-link-race]`、`docs/project-management/implementation/pm9/link-boundary-follow-through.json`。

DATA-LINK-02 原台账仅有同环境重复关联与未授权替换规则测试，缺跨项目身份与整组断言。本次反例先证明：修复请求可把本地记录的 `recordRef.projectId` 伪造成另一个项目，同时保留本地 table/generation/key；仓库只核对实际行归属，因而旧实现错误完成关联。共享 `load_bind_targets` 与 `bind_records` 均核对引用项目和权威项目一致，拒绝不一致及缺失身份，失败不改变同组记录链接版本。

两项目实例和固定环境 ID 的隔离、保存后混合目标失败保留唯一环境、伪造身份修复拒绝、正确修复仅关联，以及提交前并发版本冲突组回滚已直接测试。33 项契约/规则、真实 browser worker 的 data-link-race 1 项、Ruff 和 mypy407 通过。此证据只使 DATA-LINK-02 partial；跨项目伪造目标的真实 worker End、当前新源码打包/三平台仍待复验，`releaseAccepted=false`。历史 dadb24a1 三平台 CI 和 ARM 隔离 DMG 不覆盖新 guard。
