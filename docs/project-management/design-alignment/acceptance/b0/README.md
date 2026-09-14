# B0 视觉基准交付

- 日期：2026-09-13；状态：五组图稿已完成规格及工程审查，等待用户验收。
- 基线 `205fa64`，分支 `codex/project-management-implementation`，工作区 `autoflow-project-management-implementation`。
- 本包只包含五组高保真PNG、来源映射、交互规范与验收资料，没有新的应用构建。

## 审阅入口

| 顺序 | 图稿 | 重点 |
|---|---|---|
| 1 | [项目与数据目录](../../prototypes/r1-directory-overview.png) | 顶部导航、最近/全部入口、数据卡片、三个查询面板 |
| 2 | [记录完整页面](../../prototypes/r2-record-pages.png) | 详情/新增/编辑整页、独立业务状态操作 |
| 3 | [记录异常与恢复](../../prototypes/r2-record-states.png) | 校验、未保存、冲突、未知结果、删除、只读 |
| 4 | [字段整体草稿](../../prototypes/r3-schema-draft.png) | 抽屉应用到草稿、统一保存、影响确认、原子预算 |
| 5 | [文件与批量状态](../../prototypes/r3-file-and-batch-states.png) | Excel导入/重导入/导出、核验、批状态部分完成 |

按[手动测试方案](manual-test.md)的B0-M01–M07逐图审阅。每项包含具体位置、可见预期、反馈模板；真实交互单列到R阶段。无需启动应用、后端或准备业务数据。在实施工作区执行 `open docs/project-management/design-alignment/prototypes/r1-directory-overview.png` 可打开首图，其余图使用上表链接。

[图稿简报](../../prototype-briefs.md)记录原PMUI ID与旧代码复用来源，[交互说明](../../prototype-interactions.md)记录精确规则。[manifest](../../prototypes/manifest.json)记录实际像素尺寸与hash；图为多画板总览，不是1440×1024运行截图。R2图实际为1983×793，其他图尺寸见manifest，均可单独放大阅读。

## 核验范围

使用Superpowers的subagent-driven-development完成文档分工与独立规格审查，再做工程质量审查；交付按verification-before-completion执行新鲜核验。B0的验证对象是实际图稿和资料，未跑产品pytest/Vitest/build，也没有新的Electron截图。Windows、其他架构、打包与200%应用缩放均未执行。

执行：

```bash
python3 docs/project-management/design-alignment/acceptance/b0/verify-assets.py
git diff --check
```

脚本只读核对112份原图hash、5PNG完整性/来源ID、22个不重复画板编号、18项未来任务仍未开始、JSON和本包链接；不覆盖原PM0/PM1/PM2或原图库核验报告。保存报告时先捕获脚本完整输出再写文件，不能直接重定向到正在参与检查的同名JSON。结果见[verification.json](verification.json)，审查记录见[review-resolution.md](review-resolution.md)。

## 已知边界

- 图中计数、文件和日期均为合成示例，各状态画板不是同一时刻的连续数据快照。R1目录使用较简字段示例，R2/R3展示记录/字段编辑样例；后续真实对照测试必须统一fixture。
- 总览中的小号辅助文字存在生成字形误差；产品术语以交互说明为准。关键保存/取消、未接入、身份、限额和部分结果已逐图审阅。实际组件用真实字体与精确文案。
- R2-G、R3-D/H等是多个备选状态示例；核验中不能同时出现同一操作成功，只有查到已完成事实后显示成功。
- 静态图不能证明焦点、动效、滚动、CAS、原子事务或恢复。R1–R3各自交付后须真实应用验收。
- 主项目和旧仓只读；主线持续有其他任务提交，不要求其HEAD或工作树与开工时完全相同。本任务未向这些目录写入。

停在B0用户验收点；用户确认后进入R1。R1、R2、R3每次交付都要提供自己的启动方式、隔离数据、异常复现工具和手动测试方案，不自动进入下一里程碑。
