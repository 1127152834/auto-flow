# T5 选择控件与滚动容器

日期：2026-09-12。状态：implemented，自动验收结果见下文；Windows、实体 IME 和辅助技术仍待人工验收。工作分支 `codex/ui-controls-plan`，独立 worktree；未改主项目、业务领域、后端、API、数据及 Electron main/preload。

## 组件与接入边界

路径均相对 `apps/desktop/src/renderer/`。

| 文件 | 本批能力与使用约束 |
|---|---|
| shared/components/ui/choice-types.ts | 应用侧 ChoiceOption/ChoiceProps；value、label、description、keywords、disabled。统一 null/空串编码，不向领域暴露 React Aria collection 类型 |
| shared/components/ui/select-radix.tsx | 正式短选项 Select 暂存入口；Radix Trigger/Value/Content/Viewport/Item/ItemText/Indicator/上下滚动按钮，弹出面板自绘；ref 指向按钮 |
| shared/components/ui/combobox.tsx | 严格 Combobox 与自由 Autocomplete 共用实现；React Aria 管理键盘、选项焦点与无障碍行为；ref 指向真实 input |
| shared/components/ui/scroll-area.tsx | Radix viewport/双轴 scrollbar/thumb/corner；溢出时常显；Root 接收 className/style 控制外尺寸，ref/ARIA/事件/tabIndex 接到可滚动 Viewport |
| styles/controls.css | 选择面板、选项/选中/禁用/焦点、只读和轨道滑块视觉；沿用暖灰/黏土棕令牌 |
| shared/ui-lab/ChoiceCases.tsx、ScrollCases.tsx | 正常/空/加载/错误重试、重复名称、失效值、长文、自由输入、双轴滚动与无溢出案例 |
| shared/ui-lab/FormFocusCase.tsx | RHF 验证、跨页签错误聚焦、dirty/touched、清空与 reset |
| shared/ui-lab/ChoiceOverlayCase.tsx、LabCombobox.tsx | 正式控件进入嵌套窗口；LabCombobox 仅转换本地 fixture，原独立交互实现已移除 |

`ui/select.tsx` 的旧原生入口仍保留，供后续领域切片迁移。没有把暂存入口当作全系统替换完成，也未新增不需要的 MultiSelect 或第三方依赖。`packages/ui` 未扩建。

## API 与状态约定

- Select/Combobox：`value: string | null`，`onValueChange` 只提交真实选项或显式清空的 null。`''` 是合法业务值，显示对应 label，且可以显式清除。`null → ''`、其他值 → `v:${value}`；表单 hidden input 提交原始业务值，不提交编码键。
- Combobox 查询草稿独立于已选 value；label/value/keywords 可搜索；同 label 的选项用 value 区分。Escape、blur 恢复选中 label。过滤排除当前值时，也不能把草稿或首项悄悄保存。
- Autocomplete 的 `onValueChange(string)` 保留任意文本；选项提交 value，另以 `onOptionSelect(option)` 通知调用方。composition 阶段 Enter 不提交选项或表单；实体输入法候选确认仍需人工验收。
- 缺失的当前选项保留原值，并显示/关联“当前选项不可用，请重新选择”；列表中的缺失项不可再次选中。只读不允许打开、更改或清空，仍可聚焦；disabled 禁用操作。加载时保留已有选项，错误可显示重试。
- id/name、aria-label/labelledby/describedby/invalid、onBlur 及 ref 通过统一 API 提供。错误说明与失效说明均接入 describedby；RHF onBlur 使用无参适配，实际 ref 指向可聚焦元素。
- 跨页签案例用 Tabs forceMount 保留字段注册，隐藏非活动内容；提交失败先切活动页签，React 提交后 setFocus。业务表单后续仍遵循各自 resolver 和注册策略，不能仅照抄隐藏字段而忽略校验。
- ScrollArea 操作轨道12px、滑块6px，无溢出不显示；默认 viewport 可 Tab 聚焦。沿用浏览器滚动能力，不自写滚轮或键盘滚动算法。全局 Chromium 滚动条与 Radix 面板 Viewport 使用同一令牌。
- 所有选择浮层挂到 OverlayHost。当前锁定 RAC 1.21.1 仍支持 `UNSTABLE_portalContainer`，但其类型已标记 deprecated；本批把使用限制在共享组件内，升级 RAC 时需复核 PortalProvider 迁移与 G0，不把过时 API 暴露给领域。

## G0 重新评估与调试证据

此前 T3 的 UI-G0-01 记录保留，不能用后来单次成功抹去它。本批先在原 LabCombobox 上执行独立复现：200% 下 Playwright click 为露出被裁切触发器而滚动祖先，紧接着打开 popup，排队中的 scroll 再由 React Aria useCloseOnScroll 关闭 popup；此后 Escape 关闭 Dialog，外观容易被误判为 Escape 同时关闭两层。

注入测试日志观察到 focus 被调用前祖先 scrollTop 已变化。移除 Dialog transition、pointer 阶段 preventScroll 聚焦、阻止 mousedown 三种试验均未解决，已全部撤回；Dialog 与 OverlayHost 没有因此修改。最终自动操作先 `scrollIntoViewIfNeeded`，等待真实渲染帧/有限动效结束，再点击。正确预置条件下 24 轮覆盖100/125/150/200%、展开后祖先滚动关闭/重新展开、连续三次 Escape 与焦点返回，通过原 G0；正式控件接入后同一脚本24轮再次通过，见 `stress-before.json` 与 `stress-results.json`。

- 复现与证据：`t5-g0/failure-trace.json`、`before-failure-aria.txt`。当时Playwright截图为空，已舍弃，不作为视觉证据；最终截图使用Electron capturePage。
- 可复跑脚本：`node scripts/verify-choice-overlays.mjs`，只操作自己的临时 Electron/userData。测试注入 focus/scroll 日志，不进入产品构建。
- **结论置信度：高**——本次可复现路径属于自动点击前滚动与 popup scroll-dismiss 的时序；原始 T3 没有完整事件序列，不能证明是完全相同根因，原记录的归因置信度仍为中。G0 允许进入 T5，手动并发滚动、实体键盘与辅助技术复核保留。

T5 另发现真实控件问题：过滤后选中项不在当前 collection，Escape 恢复 label 又触发 RAC 的自动展开。新增失败测试后，通过公开 `menuTrigger` 区分真实文本编辑与程序性 label 恢复，仍由 RAC 处理键盘和焦点；回归同时断言文本恢复、listbox 关闭和下次输入可再次展开。这是本批正式组件修正，不混同旧 UI-G0-01。

最终审查补充只读 Select 的字母 typeahead 回归：Radix 在列表未展开时也会尝试变更值，故应用回调同时检查 readOnly/disabled；该失败测试修正后通过，并由 Electron 输入字母检查业务值未变。

长 label 实测还暴露 SelectValue 不接受 className/style 布局的 Radix 行为。把截断容器放在 Value 外层后复核页面横向溢出；未用缩短业务文本规避问题。

## 性能取舍

首次500项实测打开 P95 381.9ms、过滤284.7ms，未达到200/100ms目标。另用 CDP CPU Profiler 记录热点（`t5/choice-profile-before.json`）：React createElement/jsxDEV、RAC collection DOMElement、DOM渲染与GC占据较多采样。于是使用**已经安装**的 RAC Virtualizer/ListLayout，超过100项时启用，estimatedRowSize=40且观察实际行高，支持长文本，不把行强行截成固定高度。

性能口径是捕获 pointerdown/input 到出现可见选项后的下一次 requestAnimationFrame，排除 Playwright IPC/定位等待。虚拟化前要求500个DOM选项，虚拟化后要求第一批可见选项；后者仍保留完整500项语义集合，并检查 End/Home 到达第501个长文本条目及 aria-posinset/setsize。20次样本包含首次打开，DEV本机结果不可外推到低配Windows。结果不是纯过滤函数微基准，也不是跨平台性能承诺。

## 验收

| 验证 | 结果 |
|---|---|
| npm test | 60文件 / 313测试通过；相对T4增加17条 |
| shared定向测试 | 22文件 / 79测试通过 |
| npm run typecheck / lint / build | 通过；构建保留原有Zod PURE注释警告 |
| node --test scripts/ui-tokens.test.mjs scripts/structure.test.mjs | 13/13通过 |
| npm run smoke:ui-controls | 15组通过；嵌套Select/Combobox、RHF跨页签、End/Home虚拟末项、200%缩放、滚轮/拖动和真实页面回归 |
| 500项，20次事件到下一帧采样 | 打开P95 35.5ms，过滤P95 25.5ms；目标200/100ms |
| node scripts/verify-choice-overlays.mjs | 正式控件24轮通过，四种缩放、祖先滚动关闭与三层焦点返回；原探针另24轮证据保留 |
| 保护边界 | 225个源码SHA-256与T0一致；业务领域/后端/API/main/preload未改 |
| 生产隔离 | 生产JS没有实验室/ChoiceCases/ScrollCases标记；令牌与结构检查通过 |

平台：macOS 26.4.1 arm64 / Electron 41.10.3 / Chromium 146.0.7680.216。实际环境、缩放样本和错误数组见 [机器结果](t5/results.json)，延迟原始样本见 [性能结果](t5/choice-performance.json)。截图已查看：选择字段长文截断、不撑宽页面；滚动轨道、滑块及焦点环可辨识。图像：[选择状态](t5/10-choices.png)、[嵌套选择](t5/02-nested-choice.png)、[双轴滚动](t5/11-scroll-area.png)、[200%选择字段](t5/12-choice-zoom-200.png)。

TDD记录：最初9项因缺实现失败；跨页签错误聚焦案例先因无页签失败；失效值说明和Escape关闭分别新增失败断言再实现修正。未把jsdom的键盘/尺寸模拟写成真实平台验收。

## 剩余边界

- T6 浮层外框/菜单/Tooltip/Tabs 与 T7 其余共享模式尚未实施，G1 未完成，领域批量迁移未开始。
- Windows、VoiceOver/NVDA、实体 IME、系统滚动条偏好矩阵仍未运行。forced-colors 媒体模拟不能替代 Windows。
- UI-T4-01 的 Radix radio 极快合成 keyup/异步焦点竞态仍保留；T5没有修复它。
- 真实浏览器表单和设置诊断仍作为共享样式回归，不能代表新选择控件已经在全部真实页面验收。
