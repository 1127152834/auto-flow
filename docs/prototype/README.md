# AutoFlow 高保真原型

当前已完成的原型模块：

- [浏览器管理](./browser-management/browser-management-overview.png)：浏览器配置与内嵌 CloakBrowser 内核管理。
- [代理管理](./proxy-management/proxy-management-overview.png)：ProxyPanel 代理舰队与 AutoFlow 本地代理组。

每个模块的交互、动效、弹窗、错误和空态规则位于对应的 `*-interactions.md`。原型图使用内置 imagegen 生成，后续实现必须先复用共享组件，再按原型和交互文档组装页面。

## 模型管理：布局探索，待选择

- [布局 1](./model-management/model-management-layout-01.png)
- [布局 2](./model-management/model-management-layout-02.png)
- [布局 3](./model-management/model-management-layout-03.png)
- [交互草案与待补画板](./model-management/model-management-interactions.md)
- [生成方式与完整提示词](./model-management/imagegen-prompts.md)

日期：2026-09-12。以上三图是主页面布局候选，尚未成为模块视觉基准。选择布局后再补齐弹窗和状态画板，然后整理正式规格、API 契约与实施计划。
