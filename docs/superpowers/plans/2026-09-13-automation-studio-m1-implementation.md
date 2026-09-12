# M1 正式工作流编辑器实现计划

> 面向 AI 代理的工作者：按 subagent-driven-development 分工执行，主任务统一接口、集成与审查；用户已明确要求实施，无需再选择执行方式。

**目标：** 在正式应用创建、编辑、可靠保存工作流，重启后继续编辑。
**架构：** workflows 领域、现有 SQLite/OpenAPI、独立 StudioApp、共享 sidecar 与受控生命周期。文档、布局、编辑会话分离。
**技术栈：** React、@xyflow/react 12.10、现有 shared UI、FastAPI、SQLAlchemy、Alembic。
**规格：** [已批准设计](../specs/2026-09-13-automation-studio-m1-design.md)。

## 全局约束

- 沿用 apps/backend/src/autoflow 与 apps/desktop/src，不运行或导入 reference/WebRPA。
- 六节点；timeoutSeconds 默认 60；手动保存；单文档；未完成可保存；无执行或假运行。
- 保留其它任务的未提交修改，只提交本任务文件。

## A/B：契约与持久化

- [x] 在后端 domain/application/workflows、HTTP workflow schemas/router、database/workflows 与增量 migration 实现文档、图结构和节点目录。
- [x] 契约测试检查六类默认配置、未完成问题定位、坏图拒绝、POST 幂等、PUT revision 冲突及原子布局保存。
- [x] 使用真实临时 SQLite 测试保存关闭重开；运行相关 pytest、mypy、Ruff，再生成 OpenAPI。

```text
POST document.id=A → revision=1
同内容再次 POST A → 同一文档，无重复记录
PUT expectedRevision=1 → revision=2
不同内容 PUT expectedRevision=1 → 409，旧数据不覆盖
```

## C：窗口与会话保护

- [x] main/ipc/automation-studio、settings/controller、preload、shared 运行上下文与离开协议；renderer/app/useDesktopSession 提取已有连接逻辑并回归 App。
- [x] 测试 close/quit/workspace 的保存/放弃/取消、sender/frame 权限、单窗口、工作区回滚以及先保存后 shutdown。
- [x] StudioApp 稳定外层注册离开处理，按 workspaceKey 隔离文档，服务重连不重置本地编辑。

## D：编辑与页面集成

- [x] workflows/types/api 只消费生成契约；editor-model/history 提供文档变换和纯状态测试。
- [x] NodeCatalog/NodeInspector/VariablePanel 先完成独立组件与测试，再接 WorkflowCanvas 和 StudioPage。
- [x] 覆盖节点位置历史合并、剪贴板新 ID、变量引用改名/删除、输入框快捷键、配置草稿与条件字段。
- [x] useWorkflowEditor 处理保存快照、重复创建恢复、409 另存/重读、未保存离开及工作区切换锁定。

```text
开始保存 snapshot S → 用户继续编辑 T → S 保存响应
结果：revision 更新，但当前文档仍是 T，dirty 为 true
```

## E：验收与审查

- [x] npm test / typecheck / lint / build / openapi:check；后端完整 pytest 和本次范围静态检查。
- [x] 实际 Electron 创建六节点并保存，重启读取；检查开发/打包入口、主窗口关闭与服务恢复。
- [x] 独立审查数据丢失、权限、配置差异及未实现占位；修复后执行对应回归。
- [x] 写入 docs/migration 的验收证据和 .ai session，针对本任务提交。

验收结果：[M1 验收记录](../../migration/automation-studio-m1-validation.md)。macOS 开发与打包入口已实测；Windows 实机未测试，不能据模拟平台分支测试视为通过。
