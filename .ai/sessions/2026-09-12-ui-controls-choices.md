# 控件统一 T5

- 日期：2026-09-12；状态：implemented，自动验证confirmed；人工平台矩阵pending。
- 输入：用户“好的继续”，按已批准计划T5执行；Superpowers executing-plans/systematic-debugging/test-driven-development/verification-before-completion，inline推进，无子代理。
- 工作区：autoflow-ui-controls-plan，codex/ui-controls-plan。主目录只读参考，未引入主线其他任务改动；未操作用户既有Electron。
- 本批：应用侧ChoiceProps、Select暂存入口、严格Combobox/Autocomplete、双轴ScrollArea；展示案例、RHF跨页签聚焦、碰撞安全空值映射与失效选项说明。
- G0：自动点击先滚动祖先造成popup提前关闭的复现路径，预置可见/渲染稳定后24轮原探针通过。正式控件另24轮通过。Dialog/OverlayHost没有修改；旧T3归因仍有不确定性。
- 修正：无匹配草稿Escape恢复label导致再展开，使用RAC公开menuTrigger区分真实编辑/程序恢复；SelectValue外包截断容器解决长label撑宽。
- 性能：先测得打开381.9ms/过滤284.7ms P95，CDP profile后使用已安装RAC Virtualizer/ListLayout，仅>100项启用并支持动态行高；最终20样本P95 35.5ms/25.5ms。DEV本机值，不外推Windows。
- 验证：npm test 60文件313测试；shared 22/79；typecheck/lint/build通过；tokens/structure 13/13；Electron15组通过，另G0 24轮；保护源码225哈希不变；生产无实验室标记。全部源文件与最终脚本验证后才提交。
- 产物：docs/design-system/verification/choice-controls.md，t5/机器结果/截图/性能与profile，t5-g0/前后复核与复现证据。
- 后续：T6浮层外框/菜单/Tooltip/Tabs、T7共享模式、G1再领域迁移；旧select.tsx原生入口尚未替换。UI-T4-01、实体IME、Windows、VoiceOver/NVDA和平台滚动条偏好矩阵仍待验收。
