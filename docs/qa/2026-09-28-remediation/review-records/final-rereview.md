# 最终修复限定复审：e49144f2..c2367a17

日期：2026-09-28。状态：confirmed。置信度：高，限本次生产 diff 与证据的明确范围。

基线：`e49144f2458a5024ef2ef06d5f8bba75f67c0557`。
修复：`c2367a17a094d4737fcd17adeedc6730f0db2e95`。

本次是唯一一次 final fix scoped rereview，仅判断初审两个 Important 及本次 diff 新增影响。已读 final-fix-brief、final-review-findings、final-fix-report，并将 1418 行完整 diff（含原始日志）分四段读完；核对两处生产文件没有相对审查提交的额外工作区差异。没有重复全分支审计、运行测试、修改源码、提交或派生子代理。按授权只写本文件及 final-review.md；未接管或调用 AOCI。

## 逐项结论

### I-1 静态 End recordTargets 显示与清空：ADDRESSED

位置：`apps/desktop/src/renderer/domains/workflows/components/config-panels/ProjectEndConfig.tsx:11`、第 31–34 行（c2367a17 行号）。

**Spec：PASS。** 非空数组进入只读 JSON 文本框，可准确看到保存中的完整值；“清空记录目标”明确写入 `[]`。空数组及动态变量引用继续使用原输入控件，不把静态 JSON 转成后端不接受的字符串。符合初审明确允许的“准确展示加清空入口”方案。

**Quality：PASS，附一个非阻断测试 Minor（见下）。** 生产修改仅增加数组分支，数据读写继续使用既有 ConfigPanel/store 边界。没有修改后端契约，没有拍平 nested 数据，也没有改写未知字段。新增集成用例验证真实 ConfigPanel/store 中无关编辑保留原数组、外层旧值保持、清空写回内层数组；组件用例同时验证清空回调不传字符串。

### I-2 子流程选择器读取有效配置：ADDRESSED

位置：`apps/desktop/src/renderer/domains/workflows/components/config-panels/ControlModuleConfigs.tsx:478`、第 486–488、510–511 行（c2367a17 行号）。

**Spec：PASS。** 分组资格、option 名称、选中后写入名称三处均使用 getNodeConfigData。有效 nested isSubflow 能列出，外层陈旧 true 不会覆盖 nested false，子流程头也读取 nested 名称；label 继续由共享边界保留外层身份。

**Quality：PASS。** 复用现有 helper，没有平行配置解释器、契约或文档迁移。新增实际 ConfigPanel/select/store 交互覆盖冲突外层字段、nested 分组/函数头展示和选择写回；断言外层旧字段和未知 nested 字段保持。原有 flat 选择用例继续保留。原选择器的两次字段回调及既有历史机制没有被本次修改。

## 新增 Issues

Critical：0。Important：0。

Minor：1，**两个新增静态目标测试使用了非生产 RecordRef 形状。**

- 位置：`apps/desktop/src/renderer/domains/workflows/components/config-panels/ProjectEndConfig.test.tsx:30`；`apps/desktop/src/renderer/domains/workflows/tests/node-config-shape.test.tsx:89`。
- 触发：将该夹具作为合法静态 End 配置使用。测试值是 `{recordRef: {projectId, tableId, recordId}, expectedLinkRevision?}`；生产 `application/project_runs/end.py:222-223` 要求列表元素直接为 `{projectId, tableId, datasetGeneration, recordKey}`。expectedLinkRevision 由宿主从 cursor 构造，不是这里的 RecordRef 字段。
- 影响：这些测试仍有效证明“不透明数组的回显、保留、清空和 namespace 形状”，但不能作为“合法生产 RecordRef 的端到端验收”证据，且容易误导后续夹具使用者。新生产 UI 对数组元素透明，没有由此发现运行行为缺陷，因此不阻断 I-1 关闭。
- 最小修复：把这两处目标夹具改成直接的合法 RecordRef 字典；保留现有回显、保留、清空断言。外层 stale 字段可继续用明确无效哨兵检验 nested 优先级。
- 本复审没有代为改测试，也没有为该非阻断建议重启审查循环。初审聊天示例的对应字段勘误已在 final-review.md 明示。

## 核对的证据

- `../final-review-fix/red-targeted.log`：3 文件失败，准确命中 3 个新增回归；66 个既有测试通过。
- `../final-review-fix/green-targeted.log`：3 文件、69 测试通过。
- `../final-review-fix/related-tests.log`：5 文件、133 测试通过。与前项重叠，不相加。
- `../final-review-fix/commands.md` 记录精确 cwd/命令/exit；lint、typecheck 均 exit 0，原始 stdout 分别在 lint.log、typecheck.log。
- 既有 Node localStorage ExperimentalWarning 在原始日志中保留，仍属已有 deferred Minor，不与新增夹具问题混计。

以上是审查已执行日志及源代码所得，不是本 reviewer 重新运行了测试。

## 实证限制及版本边界

已读 root 的 `../native-session-LCCIyR/README.md`：旧 SQLite 工作流 revision 3→4，分别修改 outer 备注和 nested 环境名称；Studio 重开、整个应用重启后值一致；Task `87a4d6f5-08d8-48c9-883c-9e028bdcddfe` / Run `c9645a83-df96-4a05-9cb1-53e3ea70316d` 真实 End 成功，创建环境名称与 UI 一致，forbidden 后继无事件。该原生证据明确属于 **e49144f2**，不覆盖本轮两个新修复组合；本 reviewer 的静态结论不替代 root 的实际操作及原始 PNG/SQLite 证据。

本复审形成时，c2367a17 的最终全量/构建/打包与同版原生验证由 root 待完成，本报告不预判通过。此前人工持久恢复、平台/外部服务、物理故障覆盖限制继续有效。

## Declined to judge

- 静态 RecordRef 的新增逐项编辑器：初审明确允许只读展示加清空方案；此轮不要求额外产品能力。
- 既有子流程选择动作的双字段回调/撤销细节：本 diff 未改变历史机制，不在唯一一次限定复审中扩展成新审计。
- 原生 README 的 UI-04 保存时间显示差异：尚待独立核对，且本 diff 未改时间序列化或展示；不当作本轮已修复或新引入。
- 初审范围中已排除的人工重启语义、早前受阻安全审查、平台/外部服务及 AOCI 治理：本轮均未改变，不重新审计。
- c2367a17 最终原生验收与全量门禁：root 执行责任，未完成结果不能用 e49144f2 的通过替代。

## Assessment

**两个 Important 均 ADDRESSED；Spec PASS；Quality 可接受，新增 Critical 0、Important 0、Minor 1。** 本限定修复可进入 root 最终门禁与同版原生验收。测试夹具建议不改变生产修复成立的结论；不将当前 scoped approval 扩写为完整生产验收通过。
