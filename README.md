# AutoFlow

AutoFlow 是面向 Windows 和 macOS 的本地桌面自动化工作台。

基础骨架已包含 Electron 桌面壳、React 健康与恢复界面、FastAPI sidecar、OpenAPI 类型生成、跨平台 CI 和打包配置。工作流 Studio 按领域迁入 WebRPA 原组件和业务实现，宿主边界沿用 AutoFlow。

2026-09-13：现有 Studio 已清除，当前保留总览中的独立空窗口；主应用与浏览器管理保留，旧流程数据未删除。已按用户要求修订 [WebRPA 迁入设计](docs/superpowers/specs/2026-09-13-studio-webrpa-source-migration-design.md)及[实施安排](docs/superpowers/plans/2026-09-13-studio-webrpa-source-migration-implementation.md)，尚未开始迁入代码。清除基线见[记录](docs/migration/studio-removal.md)。

- [系统架构规格](docs/architecture/README.md)
- [基础骨架实现计划](docs/superpowers/plans/2026-09-11-autoflow-foundation.md)
- [迁移路线](docs/migration/README.md)
- [外部源码与能力参考](docs/references/README.md)

旧项目参考源：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`
## Development

```bash
uv sync --directory apps/backend --locked
npm ci
npm run dev
npm run test:structure
npm test
npm run typecheck
npm run lint
npm run openapi:check
npm run smoke:sidecar
npm run build
npm run smoke:desktop
```

开发环境使用 Node.js 22.12 以上的 22.x、Python 3.11 和 uv。桌面启动器通过 uv 使用后端虚拟环境。`npm run backend:build` 和 `npm run package:dir` 生成本平台内部测试产物。
