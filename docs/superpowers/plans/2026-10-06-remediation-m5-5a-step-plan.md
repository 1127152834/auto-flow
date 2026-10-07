# M5 5A 必要基础：步骤级计划

- 日期：2026-10-06；状态：confirmed（决定由实施方按用户授权作出，见 [决定记录](../../../.ai/decisions/2026-10-06-m5-5a-decisions.md)）
- 规格：[M5 规格](../specs/2026-09-30-remediation-m5-experience.md)；任务级计划：[M5 计划](2026-09-30-remediation-m5-experience.md)（5A Task 1–10）
- 依据：2026-10-06 对 Studio 布局、节点视觉、配置面板、令牌/调色/图标、术语、模块条/动效六个区域的只读源码调研（工作区外产物，结论已并入本文）与一次完整性评审
- 分支：codex/architecture-baseline（切片各自提交，不改写历史）

## 1. 范围与验收口径

5A 只交付"关键编辑路径可用、键盘可达"的必要基础，不要求全应用先迁完。口径：

| 验收 | 5A 口径 | 备注 |
|---|---|---|
| AC5-01 | **不新增**调色类与第二套图标库（`node scripts/ratchets.mjs` 的 `paletteClasses` ≤ 2008、`secondIconLibraryFiles` ≤ 81），触及文件顺手迁移；归零与转 lint 规则在 5D | 现状 2008 / 81 |
| AC5-02 | 以 Electron 实测为准：1440×900、空闲、未选中节点、右栏收起、底部一行状态条时画布 ≥ 60%；选中节点态与运行态只记录数字；vitest 只守纯函数 | jsdom 无真实布局 |
| AC5-04 | 术语检查接入 CI 并通过 | 先 report-only，清完现有命中后转阻断 |
| AC5-07 | 动效三档（完整/减少/关闭）在 Electron 里用 computed style 证明减少/关闭下无循环动画 | |
| AC5-09 | 5A 提供组件、契约与真实入口验证；共享库不引入 workflow store；旧 `variable-input` 仍有消费者，不删 | R5-12、AC5-03 的页面部分属 5B |

与 5A 无关、留在后续段：R5-12/13/14（数据面板、标签输入框、数据标签）= 5B；R5-19 全局导航 = 5D（与已记录的用户决定冲突，见决定记录 D12）；"批量运行"按钮 = 5C（Studio 嵌入项目工作区后才有入口）。

## 2. 事实（来自调研，已核对源码）

- `Toolbar.tsx` 约 1740 行，`flex-wrap` 可换行；无撤销/重做、无命令面板；`useStudioIntegration.ts:89` 把 Ctrl/Cmd+K 绑给 AI 小助手；视图切换在画布底部浮层。
- 布局宽高已由 `hooks/stores/layoutStore.ts`（zustand persist，键 `autoflow.studio.mock.editor.layout`，version 1）记忆；折叠态是各面板本地 `useState`；小地图 `canvasWidgets.minimap` 默认 true 且 persist 合并保留旧值；渲染层没有任何功能开关基础设施。
- 当前 1440×900 画布约 37%（左 256 + 右 320 + 底 256 + 工具栏），需新布局才可能达标。
- `ModuleNode.tsx`：标题 14px、摘要 12px，类别色整块着色；运行中 `animate-pulse` 整体闪烁；无节点级校验，仅 `staticNumberIssues` 一个纯函数。
- `QuickModulePicker`：双击（300ms 手动检测）与右键可唤出，但没有"/"键、没有最近/常用 12、没有连线拖到空白处（`onConnectEnd` 未设）。
- `ConfigPanel`：只有尾部通用"高级配置"；必填校验只在顶部汇总；`test-selector` 后端已返回匹配数且支持不高亮，前端 API 已有。
- 动效偏好已有三态且跨窗口同步，但取值是 system/reduce/full，不是规格的"完整/减少/关闭"；explicit reduce 只覆盖 spinner 与弹层，不压制 `animate-pulse` 与 webrpa.css 关键帧。
- `blockFlowModel` 完全忽略错误句柄；后端 `graph.py:134` 有"无起始节点"校验，但 `validate_workflow_scope`/预检没有。
- 术语：渲染层面向用户字符串中的内部术语命中约 14 处/8 个文件；`safeProjectError` 约 60 条错误码映射，少数含内部说法。
- `source-manifest.json` 的哈希描述**原始源文件**，适配后的目标文件可以修改（已有大量修改），不构成冻结约束。

## 3. 切片与顺序

`W` 表示可并行（文件互不重叠）；`S` 表示串行（共享文件，一个文件一个所有者）。每个切片独立提交，提交前跑与范围匹配的测试、类型检查、lint、`node scripts/ratchets.mjs`。

### 第一批（并行，彼此不碰同一文件）

| 切片 | 内容 | 主要文件 | 测试 |
|---|---|---|---|
| W1 快速添加 | `moduleStatsStore` 增 `getQuickList`（最近与常用，上限 12，去重，兼容旧 localStorage 数据）；`QuickModulePicker` 空搜索置顶"最近与常用"，双击不再只显示收藏；"/"键在画布聚焦且不在 input/textarea/contenteditable/代码编辑器时唤出 | `hooks/stores/moduleStatsStore*`、`QuickModulePicker.tsx`、`WorkflowEditor.tsx`（仅快捷键钩子） | store 单测（排序/去重/上限/旧数据）、picker 组件测试、键盘守卫测试 |
| W2 术语 | `apps/desktop/src/shared/copy/glossary.json`（禁用词→推荐词、`allowedIn` 路径）+ TS 类型导出；`scripts/copy-lint.mjs`（TypeScript AST，只扫字符串字面量与 JSX 文本，排除测试/注释/类型名/开发者与文档目录/mock/generated）；先 report-only，清理现有 ~14 处用户可见命中后转阻断；接入 `package.json` 与 CI；复核 `safeProjectError` 文案 | `shared/copy/*`、`scripts/copy-lint.mjs`、`ci.yml`、命中的 8 个文件 | `copy-lint.test.mjs`（命中/排除/白名单）、受影响组件测试 |
| W3 布局基础 | `lib/featureFlags.ts`（localStorage 键 `autoflow.flags.newStudioLayout`，默认 false，URL/环境覆盖）；`layoutStore` 升 version 2 并迁移（左栏折叠、底部模式；不丢宽度）；`lib/studioLayoutMetrics.ts` 纯函数 + 面积守卫测试 | 新文件为主，`layoutStore.ts` | 开关默认/读取/回退/存储异常；迁移不丢宽度；1440×900 空闲态占比 ≥ 0.60、1280×800 折叠 ≥ 0.50（引用实际常量） |
| W4 调色脚本 | `scripts/palette-migration.mjs`：映射表 JSON（前缀+色系-色阶 → 语义类），保留变体前缀与 `/透明度`，`--dry-run` 默认、`--write`，无映射的类原样保留并输出人工校对清单到临时目录；不改界面 | `scripts/palette-migration.*`、映射表 | 脚本单测（替换、变体、透明度、未映射清单、幂等） |
| W5 配置分段组件 | `lib/configSections.ts`（`ADVANCED_FIELDS`：moduleType→高级字段 key，默认全基本；通用高级项）；`ConfigField` 包装组件（标签、字段下方错误、`aria-invalid`）；`useSelectorMatchCount`（防抖 ~500ms、单飞、运行中暂停、无浏览器显示"未连接浏览器"）——新文件，**先不接入 ConfigPanel** | 新文件 | 组件测试、hook 测试（防抖/单飞/暂停）、一致性守门（`ADVANCED_FIELDS` 的 key 真实存在于对应节点组件） |
| W6 模块条与预检（后端+模型） | 先写复现测试：`generateGraphFromBlocks` 是否丢错误边；`Block` 统一加 `onError?: Block[]` 并往返保真；后端 `validate_graph_entry`（无起始节点→`NO_START_NODE`），由 `runtime.preflight` 与 `run_validation` 双入口调用，不改 parser | `blockFlowModel.ts`、`apps/backend/.../scope.py` 等 | 前端模型往返测试；后端预检单测 + 一次真实入口（HTTP 预检）测试 |

### 第二批（串行队列，按文件所有权排序）

| 序 | 切片 | 所有者文件 | 内容 |
|---|---|---|---|
| S1 | 令牌 | `styles/tokens.css` | 一次提交：缺口令牌（info 状态色、文字三级）+ 合并后的动效令牌（`--motion-fast/base/slow/loop`，只留一份命名，与现有 control100/toggle120 等的关系写清）+ 对比度单测 |
| S2 | 动效与节点 | `ModuleNode.tsx`、`index.css`、`webrpa.css`、设置偏好 | ① 去掉 `animate-pulse`，运行中仅外圈进度；失败节点仅变色 ② 偏好取值改 `full/reduce/off`，旧值 `system` 在 store.load 迁移；CSS 以 `data-motion` 为准，reduce=保留 ≤120ms 过渡无循环动画，off=动画与过渡归零 ③ 节点两行、正文 ≥13px、左侧细色条、状态角标、`nodeIssues` 警告角标（单一来源：`staticNumberIssues` + 后端必填；与配置面板字段错误共用） |
| S3 | 配置面板 | `ConfigPanel.tsx`、`config-panels/*` | 接入 W5 组件；顶部汇总改"N 项必填未填"并可跳转；试点 6–10 个网页类高频节点（click_element/input_text/get_element_info/wait_element/open_page/hover_element）；选择器旁常驻匹配数 |
| S4 | WorkflowEditor 队列 | `WorkflowEditor.tsx`（一个所有者） | 连线拖出弹同一面板并自动连线（多句柄规则写成验收用例）→ 失败时画布平移一次 → 新布局（底部状态条/运行展开 30%、右栏随选中收起、折叠记忆，全部受 `newStudioLayout` 保护）→ 小地图默认关闭（仅新装与迁移后未显式设置者） |
| S5 | 命令面板与工具栏 | `CommandPalette.tsx`、`studioCommands.ts`、`Toolbar.tsx`/新工具栏、`useStudioIntegration.ts` | 命令面板先于工具栏接线；仅在 `newStudioLayout` 开启时 Ctrl/Cmd+K 打开命令面板，AI 小助手改 Ctrl/Cmd+J（保留按钮与命令项）；新单行工具栏复用现有 handler，保持无障碍名称（保存/新建/运行等），旧工具栏保留作回退；撤销/重做先确认 `editor-store` 现有 API，缺则独立小步骤 |
| S6 | 模块条视图 | `BlockFlowView.tsx` | 来源节点下方渲染 `onError` 子序列并标注"出错时"（warning 色）；`EmptySlot` 增 `onError` 放置目标；前端同步预检提示（后端权威，前端镜像文案） |
| S7 | Electron 实测 | `scripts/qa-studio-layout-m5.mjs` 等 | 1440×900 / 1280×800 画布面积实测、开关回退演练、动效 computed-style 实测；截图与数字放 CI 产物，不入 `docs/` |

## 4. 第一个可交付切片

W1（快速添加）：真实入口是 Studio 画布双击空白处或按"/"；纯前端；新代码只用语义令牌类与 lucide 图标，不扩大 `paletteClasses`/`secondIconLibraryFiles` 基线。先只统计内置模块（`customModuleId` 记录留作后续）。

## 5. 风险与应对

| 风险 | 应对 |
|---|---|
| `WorkflowEditor.tsx` 被多处修改 | 第一批只允许 W1 碰其快捷键钩子；其余改动进 S4 队列，一个所有者 |
| `Toolbar.tsx` 近 1740 行且大量测试按按钮名称查询 | 新工具栏复用 handler；两种开关状态下既有测试都要通过 |
| 动效三档改取值会触及 5 个测试文件与 store 校验 | 在 store.load 做一次迁移；测试随改；定义写入决定记录 |
| 按文件基线的 ratchet 与 copy-lint 基线可能互相冲突 | 5A 不改 ratchet 口径；copy-lint 基线独立文件 |
| 1440×900 的 60% 可能卡线 | 以 Electron 实测为准；不达标先调左栏默认宽度，不降低验收 |
| 规则 1（新增配置项需后端读取） | `newStudioLayout` 不在设置界面暴露，纯前端实验开关；小地图/折叠为本机偏好，不算后端配置项 |

## 6. 退出

5A 全部切片合并、CI 三平台通过、Electron 实测数字记录后，在 `.ai/plans` 登记开关默认开启条件（连续 7 天正确性/视觉回归、消费者迁移、回退验证），再进入 5B 的步骤级细化（M2A/B 接口已进入 OpenAPI，需先盘点 5B 后端契约缺口）。

## 7. 进度

| 切片 | 状态 | 提交 | 备注 |
|---|---|---|---|
| W1 快速添加 | 已完成（本机） | feea0fd7 | 评审发现并修复：收藏星标上按 Enter/空格误添加模块 |
| W2 术语与文案检查 | 已完成（本机） | 9ac88c2b | 28 处命中中约 14 处为代码键名误报（改用裸键规则排除）；项目结束节点"记录目标"标签同步到后端、导出脚本与两份 JSON |
| W3 布局基础 | 已完成（本机） | a57cf168 | 评审修复：窗口尺寸为 0 时不再返回 NaN |
| W4 调色脚本 | 已完成（本机） | 44850753 | 评审发现并修复：不带 --report 时丢掉首个路径参数；用 TypeScript 解析器取代手写引号状态机（可替换类名由 1235 增至 1252） |
| W5 配置分段组件 | 已完成（本机） | cb993209 | 新文件，S3 接入；`noBrowser` 依赖后端措辞，接入时留意 |
| W6 模块条模型与预检 | 已完成（本机） | d786023a | 已知限制：错误链按终止链处理；同一节点第二条错误出边与回到主流程的边在往返后不保留（已用测试锁定）；S6 视图须提示"错误处理链不会回到主流程" |

本机验证：前端全量 6086 通过，6 个失败文件均为既有本机问题（kernel-paths、project-files controller、settings ×2、android RuntimeDiagnostics 日期断言、缺冻结源的 recording-source-parity）；类型检查、eslint、`ratchets`（2008/81 未上升）、`copy-lint`（0 处）、脚本测试、后端预检 173 项与 ruff/mypy/严格类型门禁（仅本机缺 face_recognition 的 4 条差异）通过。CI 三平台待验。

### 第二批（S0–S6）与实测（S7）

| 切片 | 状态 | 提交 | 备注 |
|---|---|---|---|
| S0 nodeIssues | 已完成（本机） | a5dec6c5、c04a52f8 | 集成评审发现并修复：节点角标与配置面板各自生成 context，互相顶掉缓存导致无限重渲染（已复现）；`useRequiredFields` 改为模块级共享状态 |
| S1 令牌 | 已完成（本机） | cc386aac | 补 info/文字三级/动效令牌（浅色）；深色与类别色留 5D |
| S2a 动效三档 | 已完成（本机） | 994f64eb、a44877ce、本批 | 实测发现 Studio 不加载 `index.css`，规则抽成 `motion.css` 并由 `webrpa.css` 引入后才在 Studio 生效；全新安装跟随系统减少动画 |
| S2b 节点视觉 | 已完成（本机） | 76546e37、本批 | 实测发现：类别细色条被 `webrpa.css` 的非层级 `* {border-color}` 压成浅米色、标题 `text-sm` 实为 12px，均已修 |
| S3 配置面板 | 已完成（本机） | 840b3b61、e9f35983 | 含变量的选择器不预检；通用高级项报错自动展开 |
| S4a/S4b 连线拖出与新布局 | 已完成（本机） | 6d63cd45、c0449f92、333db689 | 失败定位等两帧；小屏自动折叠不入持久偏好；小地图开关如实显示 |
| S5 命令面板与工具栏 | 已完成（本机） | a54f2f00、ea46e08c | 新工具栏遵守"流程图/模块条切换"配置；评审通过 |
| S6 模块条出错时 | 已完成（本机） | 259af5b2 | |
| S7 实测 | 已完成（Chromium 预览，本机） | 本批 | 数字见 [Studio 样式陷阱与实测](../../../.ai/knowledge/2026-10-07-m5-5a-studio-css-pitfalls.md)：1440×900 空闲 72.1%（旧布局 35.2%）、1280×800 空闲 68.9%、工具栏单行无溢出、动效 reduce/off 在 Studio 窗口生效 |

未做的 5A 内容：Electron 打包窗口里的同类实测（预览与 Electron 同为 Chromium，但打包窗口还有原生标题栏高度）；`scripts/qa-studio-layout-m5.mjs` 自动化脚本（本轮以预览手工实测并记录复现方法代替）；"批量运行"主按钮（D3，5C）；导航（D12，待用户确认）。

