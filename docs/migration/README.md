# AutoFlow 迁移路线

迁移以可运行垂直切片为单位，不做一次性“大搬家”。旧项目参考基线：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`。旧项目当前分支 `codex/reset-project-management` 处于项目域清理后的全局资源基线；项目、数据、自动化、运行方案和工作流代码不视为已迁移能力。

## 阶段 0：基线和工具链

交付：架构规格、代码许可清单、根级 lock 文件、Python 和 TypeScript lint/type/test 命令、Windows/macOS CI 骨架。

不迁移业务代码，不引入 WebRPA 源码。

## 阶段 1：可运行桌面骨架

交付：Electron main/preload、React renderer、FastAPI sidecar、随机端口、健康握手、关闭回收、应用数据路径服务和最小日志。

验收：Windows 和 macOS 均可开发模式启动，关闭窗口后 sidecar 不遗留进程。

## 阶段 2：全局资源垂直切片

顺序：设置与诊断 → 浏览器配置 → 代理 → 内核 → 模型提供商。

当前已按用户授权并行推进资源模块。浏览器内核属于浏览器配置表单中的管理弹窗，不设置独立导航页面。浏览器模块的实现与平台验收见 [验收记录](browser-management-validation.md)，实施中的边界判断见 [裁决记录](browser-management-decisions.md)。代理、模型、设置与总览的独立交付记录也保存在本目录。

每个切片同时迁移后端 domain/application/http、前端 domain、OpenAPI 类型、数据库迁移、单元测试和平台测试。新仓库只启用已经迁移并验证的实现；旧项目保持只读参考，不删除其入口或改动其工作区。

## 阶段 3：工作流核心

先实现 AutoFlow Workflow IR、节点 schema、执行器注册表、变量、条件、循环、HTTP、文件、Playwright、取消和事件日志。工作流编辑器从 React Flow 画布、节点目录、配置面板和调试面板组成。

## 阶段 4：WebRPA 能力迁移

按单能力迁移 WebRPA：

1. 变量和数据结构；
2. 浏览器导航和元素操作；
3. 文件、表格和 HTTP；
4. 子流程、调试和日志；
5. AI、OCR、媒体和文档；
6. Windows/macOS 桌面能力。

每个能力先做来源审查和 AutoFlow 测试，再移植最小代码。WebRPA 的 Windows-only 执行器不得进入跨平台核心包。

## 阶段 5：发布和持续质量

增加 Windows NSIS、macOS DMG、签名/notarization、sidecar 更新、崩溃日志和跨平台端到端冒烟测试。此阶段前不承诺完整的自动化模块数量，也不复制 WebRPA 的重量级依赖集合。


## Automation Studio 当前交付（2026-09-13）

上述阶段为总体迁移顺序；本轮用户确认的实际范围以 [M1 验收](automation-studio-m1-validation.md) 与 [M2 规格](../superpowers/specs/2026-09-13-automation-studio-m2-design.md) 为准。M2 实现六节点顺序运行、真实日志/结果与临时浏览器清理，见 [M2 验收](automation-studio-m2-validation.md)。条件/循环/子流程、调试和录制尚未实施；企业、Windows 控制、发布/版本管理不在当前复刻范围。


M3 已增加专用可见拾取会话、元素拾取/定位测试和 framePath 的真实执行；参见 [M3 验收记录](automation-studio-m3-validation.md)。这更新了上文“元素拾取尚未实施”的历史状态；完整录制、Debug 和复杂控制流仍未交付。
