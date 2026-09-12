# 统一控件 T4

- 日期：2026-09-12；状态：implemented / confirmed（人工与跨平台验证除外）。
- 授权：用户在T3报告后回复“继续”；仅推进T4，不做领域迁移。
- 工作位置：autoflow-ui-controls-plan / codex/ui-controls-plan，起点985eb3d；只读核对主目录72a6157，未合并其他任务。
- 使用Superpowers executing-plans、test-driven-development、systematic-debugging、verification-before-completion；内联执行。
- 完成Checkbox三态图形、RadioGroup、Switch状态视觉和Disclosure；ToggleCases、RHF错误聚焦/reset、样式与真实Electron证据。
- 验证：56文件296测试；shared18文件62测试；typecheck/lint/build通过；token/structure13通过；Electron12组通过；61生产CSS令牌完整、无lab标记；225保护哈希一致。
- 截图复核修复选中覆盖错误边框、高对比度Thumb颜色，并使用渲染/动画条件等待保证截图是稳定状态。
- UI-G0-01仍须T5前专门排查；UI-T4-01保留Radix零间隔keyup早于异步焦点的竞态，正常顺序自动测试通过不等于实体键盘/读屏通过。
- 源码和完整证据：docs/design-system/verification/toggle-controls.md；docs/design-system/verification/t4/results.json。
- 没有修改后端/接口/领域代码/main/preload，没有写主目录或真实用户数据；独立测试目录由脚本清理。
- 下一步T5前复核G0，再开发正式Select/Combobox/滚动容器；Windows、IME、实体键盘、读屏及全系统回归仍待后续验收。
