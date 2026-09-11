# AutoFlow 项目结构

本文档描述仓库目录职责。新增目录或改变边界时必须同步更新本文档，并在 `.ai/decisions/` 记录影响较大的取舍。

```text
.
├── apps/
│   ├── backend/              # Python FastAPI 本地服务：领域、应用、适配器、基础设施
│   └── desktop/              # Electron 主进程、预加载脚本、React 渲染器
├── packages/                 # 可复用的跨应用包（类型、API 客户端、设计系统，按需建立）
├── reference/                # 外部参考实现和只读资料，不直接作为运行时依赖
├── scripts/                  # 构建、代码生成、验证和冒烟脚本
├── docs/
│   ├── architecture/         # 系统架构、边界、运行时和跨平台约束
│   ├── migration/            # 从旧项目迁移的能力矩阵、映射和阶段记录
│   ├── automation-studio/    # 自动化编排能力的研究与规划
│   ├── references/           # 参考项目的调研材料
│   └── superpowers/          # 设计、计划和验证产物
├── .ai/                      # agent 持续维护的项目记忆、知识、决策和协作记录
├── .github/                  # CI/CD 工作流和仓库自动化
└── AGENTS.md                 # agent 工作规范和人机协同规则
```

## 分层原则

- `apps/backend` 的业务规则不依赖 FastAPI、SQLite 或操作系统；外部系统通过端口和适配器接入。
- `apps/desktop` 的主进程负责窗口、生命周期和本地服务监管；渲染器只通过受控 API 与后端通信。
- `packages` 只放跨应用复用且边界稳定的代码，避免提前抽象。
- `reference` 永远只读；复制能力时先提炼行为和契约，再用本项目技术栈重写。
- 页面依赖共享组件和 feature API，不在页面内重复实现基础控件、数据访问或平台判断。
