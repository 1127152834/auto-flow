# AutoFlow

AutoFlow 是面向 Windows 和 macOS 的本地桌面自动化工作台。

基础骨架已包含 Electron 桌面壳、React 健康与恢复界面、FastAPI sidecar、OpenAPI 类型生成、跨平台 CI 和打包配置。下一阶段按领域迁移旧项目能力，再从 WebRPA 中选择可维护的源码和能力进行重写或移植。

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
