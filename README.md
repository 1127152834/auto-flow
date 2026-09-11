# AutoFlow

AutoFlow 是面向 Windows 和 macOS 的本地桌面自动化工作台。

架构规格已经批准，基础骨架实现计划已经编写。实施顺序是建立最小可运行骨架，按领域迁移旧项目能力，再从 WebRPA 中选择可维护的源码和能力进行重写或移植。

- [系统架构规格](docs/architecture/README.md)
- [基础骨架实现计划](docs/superpowers/plans/2026-09-11-autoflow-foundation.md)
- [迁移路线](docs/migration/README.md)
- [外部源码与能力参考](docs/references/README.md)

旧项目参考源：`/Users/zhangtiancheng/Documents/projects/browser-automation/autoflow-desktop`
## Development

```bash
npm install
npm run dev
npm run test:structure
npm test
npm run typecheck
npm run lint
uv --directory apps/backend lock
```
