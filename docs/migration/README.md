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

每个切片同时迁移后端 domain/application/http、前端 domain、OpenAPI 类型、数据库迁移、单元测试和平台测试。迁移完成一个切片后再删除旧代码对应的入口，禁止旧新两套逻辑长期并行。

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
