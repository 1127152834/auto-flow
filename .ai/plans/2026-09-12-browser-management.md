# 浏览器管理实施计划索引

- 日期：2026-09-12
- 状态：confirmed（任务 1–12、最终修复及独立定向复审完成；本机 macOS arm64 验收通过）
- 来源：用户本轮 writing-plans 请求；浏览器模块原型及旧项目 ProfilesPage/ProfileActionDialog/KernelPage、现有源码和目录基准。
- 计划：`docs/superpowers/plans/2026-09-12-browser-management.md`。
- 核心决策：内核管理从配置表单打开；无独立内核页面；组件先于页面；领域 API 和前端同一切片交付；不迁移旧数据。
- 范围：12 个可测试任务，含新存储、配置 CRUD、真实 CloakBrowser、取消任务、嵌套弹窗与三平台 CI；本模块只消费代理引用查询和校验，代理管理由用户授权的并行任务交付。
- 路径：沿用 apps/backend 和 renderer/domains，目录占位与 UI 草稿不算已完成实现。
- 原型裁决：图中公开版 Preview、同时登录/退出、安装次数和表单侧栏不作为行为契约；详见计划第0节。
- 验证：实际结果见 `docs/migration/browser-management-validation.md`；人工 Electron 截图见 `.ai/sessions/2026-09-12-browser-management-ui-validation.md`。Windows/macOS Intel 尚无本轮执行结果，License 实测未验证。
- 实施裁决：`docs/migration/browser-management-decisions.md`。
- 最终修复：`3df5609`；审查归档：`.ai/sessions/browser-management-review/README.md`。
