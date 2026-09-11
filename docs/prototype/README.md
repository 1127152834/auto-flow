# AutoFlow 高保真原型

当前已完成的原型模块：

- [浏览器管理](./browser-management/browser-management-overview.png)：浏览器配置与内嵌 CloakBrowser 内核管理。
- [代理管理](./proxy-management/proxy-management-overview.png)：ProxyPanel 代理舰队与 AutoFlow 本地代理组。
- [设置](./settings/README.md)：常规、工作区和关于；包含缩放、动效偏好与诊断导出三项能力，已授权实施；验证见 [设置与总览实施状态](../migration/settings-dashboard-status.md)。

每个模块的交互、动效、弹窗、错误和空态规则位于对应的 `*-interactions.md`。原型图使用内置 imagegen 生成，后续实现必须先复用共享组件，再按原型和交互文档组装页面。

## 模型管理：原型已确认，保留旧布局与交互

- [主页面](./model-management/model-management-overview.png)
- [供应商接入三步与编辑](./model-management/model-management-provider-flow.png)
- [模型添加、编辑、测试与删除确认](./model-management/model-management-model-flow.png)
- [交互规则与验收矩阵](./model-management/model-management-interactions.md)
- [旧页面现场取证](./model-management/reference/README.md)
- [本次生成记录与提示词](./model-management/imagegen-legacy-alignment-prompts.md)

日期：2026-09-12。用户已指定模型管理的布局和交互与旧项目相同；当前三张图属于同一设计，分别覆盖主页面与操作流程，不是三个待选方案。原 `model-management-layout-01/02/03.png` 和对应 `imagegen-prompts.md` 标记为 superseded，仅作历史记录，不用于实现。原型已确认；开发资料为[设计规格](../superpowers/specs/2026-09-12-model-management-design.md)、[API 契约](../references/model-management-api-contract.md)与[实施计划](../superpowers/plans/2026-09-12-model-management-implementation.md)。当前不代表模型功能已实现。
