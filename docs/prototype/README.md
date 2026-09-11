# AutoFlow 原型基准

这是 AutoFlow 功能迁移阶段的视觉与交互基准，不是生产代码。生产实现必须先复用 `packages/ui` 的共享组件，再按这里定义的行为实现页面。

## 使用方式

直接打开 [`prototype.html`](./prototype.html)。原型不依赖构建工具，支持点击顶部模块、列表项、按钮、弹窗、Toast、标签页和进度状态。

## 基准模块

| 模块 | 主要流程 | 设计说明 |
| --- | --- | --- |
| 总览 | 健康状态、指标、最近活动 | [dashboard.md](./modules/dashboard.md) |
| 浏览器配置 | 列表、编辑、复制、删除、批量操作 | [profiles.md](./modules/profiles.md) |
| 代理与代理池 | 列表、导入、健康检查、池成员 | [proxies.md](./modules/proxies.md) |
| 内核管理 | 版本、安装、下载进度、失败重试 | [kernels.md](./modules/kernels.md) |
| 模型管理 | 供应商、模型、连接测试、密钥脱敏 | [models.md](./modules/models.md) |
| 设置 | 服务状态、路径、主题、诊断 | [settings.md](./modules/settings.md) |

## 视觉令牌

- 页面底色：`#f1eee7`
- 表面：`#fbfaf7`
- 线条：`#d8d3c9`
- 主色：`#8d4e2f`
- 成功：`#71866b`
- 警告：`#b7793e`
- 错误：`#b85c4b`
- 圆角：8px（控件）、14px（面板）
- 动效：150ms ease-out；异步进度使用 300ms linear；禁止大幅位移

## 交互基准

1. 所有写操作都有成功 Toast；失败 Toast 必须包含下一步动作。
2. 删除、清空和重启使用 AlertDialog；危险操作默认聚焦取消按钮。
3. 加载显示 Skeleton，空数据显示 EmptyState，网络/sidecar 错误显示 ErrorState。
4. 表单离开前有未保存提示；保存按钮在提交期间显示 loading 并禁用重复提交。
5. 异步任务展示状态、进度、取消和重试，不用无限转圈替代真实状态。
6. 键盘可完成导航、打开 Dialog、关闭 Dialog 和提交表单。

## 交付关系

本目录先于实现计划作为产品和工程共同的行为基准。实现计划会把每个模块拆成：API 契约、后端用例、共享组件、领域组件、页面、测试和验收任务。
