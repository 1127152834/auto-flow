# WebRPA 画布布局 × AutoFlow 配色：静态原型

- 日期：2026-09-13；状态：用户主题要求 confirmed，图像为 proposed 静态视觉稿。
- 用户要求：绘制最终工作流画布原型，样式与布局贴合 WebRPA，风格配色沿用 AutoFlow。
- 最终预览：[canvas-autoflow.png](canvas-autoflow.png)，1710 × 920 像素。
- 制作方式：内置 image_gen；以真实源截图为参考生成一张原型，再校正底部日志比例。[完整提示词](image-prompt.md)。正式业务代码未修改；不计里程碑已完成。

## 来源与映射

- 布局参考：[冻结版 WebRPA 展示图1](../../../../reference/WebRPA/png/展示图1.png)，源 commit `5ccb900e8dcf1530aae66f676d87593c416c7ebb`。
- 配色参考：[AutoFlow 浏览器配置实测截图](../../../migration/browser-management-screenshots/profiles.png)及[正式主题](../../../../apps/desktop/src/renderer/styles/index.css)。
- 右侧配置字段参考：[GetElementInfoConfig](../../../../reference/WebRPA/frontend/src/components/workflow/config-panels/BasicModuleConfigs.tsx)与[ConfigPanel](../../../../reference/WebRPA/frontend/src/components/workflow/ConfigPanel.tsx)。示例值不是新默认值。
- 保留顶部工具栏、左侧模块库、中间点阵画布、右属性、全宽底部日志的分区；缩放、缩略图、搜索及流程图/模块条切换保持原相对位置。原蓝色强调改为黏土棕，成功/运行使用低饱和绿色，暖灰与米白作为基础表面。
- canvas `#f1eee7`；surface `#fbfaf7`；line `#d8d3c9`；ink `#34322e`；muted `#625e57`；clay `#8d4e2f`；sage `#71866b`。这些是实现时精确 token，生成图像本身不作为逐像素色值依据。

## 原型内容与核验边界

- 示例“商品信息采集”包含9个模块，展示原式紧凑节点、分组、便签、分支与已选提取节点。图中的数量、参数和日志是视觉样例，不是运行结果或最终模块清单。
- 按此前已排除范围移除工作流仓库/版本入口；未确认纳入的 Excel/AI 专项不借本图宣称完成。
- 已目视检查全图、中文主要字段、九个模块、配置区、缩略图、视图切换和日志层级。首版日志区过矮，第二版已加高；最终图保留完整分区和可滚动侧栏。
- 本图供布局与配色审查；生成稿的精确面板尺寸、连接路径和像素级颜色不构成原版1:1验收。正式实现仍使用原组件、布局尺寸及 AutoFlow token，通过 R2 的固定视口对照验证。
- 未创建交互网页、后端或录制/运行功能；日志明确显示流程尚未运行。
