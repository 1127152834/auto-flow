# 全系统基础控件统一

- 日期：2026-09-12；状态：approved，T0–T7 implemented；T8–T13 in progress（人工IME/平台待验收）。
- 来源：用户在设计和计划交付后回复“好的 开始吧”；本次按此前约定执行首批 T0–T2。
- 原设计阶段 proposed / 全部未勾选状态已 superseded；源码静态盘点保留原快照，不伪装成当前运行清单。
- 工作位置：`/Users/zhangtiancheng/Documents/projects/autoflow-ui-controls-plan`，分支 `codex/ui-controls-plan`。
- 基线：合入已提交 main a1f3925，形成 dff8860；保留语言/时区/UA 最新目录接线、代理协议、品牌资源。后续主线推进不在本批重复合入。
- 正式计划：`docs/superpowers/plans/2026-09-12-unified-ui-controls.md`；规格同名位于 specs，盘点在 docs/design-system。
- 本批：tokens、Chromium scrollbar、DEV lab、RHF 与嵌套 Radix/React Aria G0；报告 `docs/design-system/verification/choice-overlay-gate.md`。
- 不扩建 packages/ui，不改业务接口/后端/数据，不操作主目录或共享 Electron；保护清单相对 T0 复核。
- 下个动作：T6 浮层外框/菜单/Tooltip/Tabs；G1后再迁移领域。UI-G0-01本批已复核，原T3归因的不确定性与人工矩阵保留。
- T3：共享文字控件和状态矩阵落地；验收与偶发浮层记录见 docs/design-system/verification/text-controls.md。
- 尚未完成：全套组件状态、真实页面迁移/回归、Windows、VoiceOver/NVDA、平台滚动条设置矩阵。G0 不能替代这些验收。

- T4：统一Checkbox/RadioGroup/Switch/Disclosure及ToggleCases；56文件296测试、12组Electron检查，真实浏览器Switch/设置Checkbox通过。报告 docs/design-system/verification/toggle-controls.md。
- UI-T4-01：零间隔合成keyup可先于Radix异步焦点，导致只移动焦点未改变值；实体键盘与读屏待验收，领域Radio迁移前复核。不得将正常按下/抬起顺序的自动检查写成此项已修复。

- T5：Select/Combobox/Autocomplete/ScrollArea、RHF跨页签和选择展示落地。500项先profile后启用已有RAC虚拟化；60文件313测试、15组Electron检查通过。报告 docs/design-system/verification/choice-controls.md。

- 2026-09-12追加授权：用户要求连续完成全部控件/组件，不逐阶段汇报；继续同一独立worktree，按既定边界完成领域接入与可执行验收，未运行的平台检查保留pending。T6–T7报告shared-patterns.md。
