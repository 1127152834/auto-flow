# 浏览器管理模块高保真原型

本目录只包含 AutoFlow 的浏览器配置管理模块原型。内核管理已经收进浏览器配置表单，通过“管理内核”按钮打开 CloakBrowser 内核管理弹窗，不再作为独立页面。

## 视觉基准

- [浏览器管理总览图](./browser-management/browser-management-overview.png)
- [交互与状态基准](./browser-management/browser-management-interactions.md)

原型根据旧项目 `ProfilesPage.tsx`、`ProfileActionDialog.tsx`、`KernelPage.tsx` 和实际运行页面整理。图片使用内置 imagegen 生成，仅作为后续组件和页面实现的视觉基准。

## 约束

- 只展示浏览器配置管理相关内容。
- 不增加模块内部侧栏或资源侧栏。
- 不出现独立内核页面。
- CloakBrowser 是唯一内核品牌。
- 不加入 Firefox、Safari、通用浏览器市场或项目管理内容。
