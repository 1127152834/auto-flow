# 浏览器管理实施计划索引

- 日期：2026-09-12
- 状态：proposed（原型方向已确认，实施计划待用户审查，尚未执行）
- 来源：用户本轮 writing-plans 请求；浏览器模块原型及旧项目 ProfilesPage/ProfileActionDialog/KernelPage、现有源码和目录基准。
- 计划：`docs/superpowers/plans/2026-09-12-browser-management.md`。
- 核心决策：内核管理从配置表单打开；无独立内核页面；组件先于页面；领域 API 和前端同一切片交付；不迁移旧数据。
- 范围：12 个可测试任务，含新存储、配置 CRUD、真实 CloakBrowser、取消任务、嵌套弹窗与三平台验证；代理只提供引用查询和校验。
- 路径：沿用 apps/backend 和 renderer/domains，目录占位与 UI 草稿不算已完成实现。
- 原型裁决：图中公开版 Preview、同时登录/退出、安装次数和表单侧栏不作为行为契约；详见计划第0节。
- 验证：只做来源核对、计划覆盖/路径/任务依赖/占位符静态检查；本轮未运行或宣称业务实现测试通过。
