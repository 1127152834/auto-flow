# M5 5A 实施决定

- 日期：2026-10-06；状态：confirmed
- 来源：用户在 M4 收尾时明确授权"都由你来决定，你来做决策"，并要求继续执行 M5；决定依据 2026-10-06 六个区域的源码调研与完整性评审，步骤见 [5A 步骤计划](../../docs/superpowers/plans/2026-10-06-remediation-m5-5a-step-plan.md)
- 范围：只约束 5A；5B 起另行细化

| 编号 | 决定 | 理由 / 取代 |
|---|---|---|
| D1 | `newStudioLayout` 为纯前端实验开关：`lib/featureFlags.ts` 读 localStorage 键 `autoflow.flags.newStudioLayout`，默认 false，允许 URL/环境覆盖供 CI 与 QA；不在设置界面暴露；旧工具栏与旧布局保留到默认开启之后的下一个里程碑才删 | 仓库无开关基础设施；回退只需清键；不暴露在界面所以不触发整改规则 1 |
| D2 | 仅在 `newStudioLayout` 开启时，Ctrl/Cmd+K 打开命令面板，AI 小助手改 Ctrl/Cmd+J（保留工具栏按钮与命令项）；开关关闭时行为不变 | R5-07 要求命令面板用 Ctrl+K；用开关隔离行为变更 |
| D3 | "批量运行"主按钮不在 5A 渲染，等 5C 把 Studio 嵌入项目工作区、有真实批量入口后再加；不放无后端的占位 | 整改规则 1 |
| D4 | AC5-02 的 60% 以 Electron 实测为准：空闲、未选中节点、右栏收起、底部一行状态条为硬断言；选中节点态与运行态只记录数字；vitest 只测纯函数 | jsdom 无真实布局 |
| D5 | 动效偏好沿用 `UiPreferences.motion`，取值改为 `full / reduce / off`，旧值 `system` 在 store.load 按系统偏好迁移；`reduce` = 保留 ≤120ms 状态过渡、无循环动画；`off` = 动画与过渡全部归零；CSS 以 `data-motion` 为准，不再依赖 OS media query | 规格要求三档；现状 system/reduce/full 与之不符 |
| D6 | 节点警告角标与配置面板字段错误共用一个编辑器层 `nodeIssues` 选择器；首版只含 `staticNumberIssues` 与后端必填字段；"无起始节点"由后端权威判定，前端只镜像文案 | 避免同一节点三套错误来源 |
| D7 | AC5-01 在 5A 的口径是"不新增"，不是归零；新代码禁用调色类与第二套图标库，触及文件顺手迁移；归零、按文件基线与转 lint 规则在 5D | 避免 81 个 phosphor 文件的大面积合并冲突 |
| D8 | 术语表单一来源是 `apps/desktop/src/shared/copy/glossary.json`（TS 导出类型）；`copy-lint` 用 TypeScript AST 扫字面量，路径白名单排除文档内容/mock/测试/generated；"系统 UUID"暂用"系统编号"，待产品确认 | 脚本无需转译 TS |
| D9 | 8 类节点类别色的映射表留到 5D 出稿并请用户确认；5A 节点只复用 `colorClassMap` 提取 border 色做左侧细色条，不新增令牌 | 类别色分类是产品决定 |
| D10 | 错误分支数据模型：`Block` 统一加 `onError?: Block[]`，不新增 Block 种类；无起始节点预检放后端 scope 新函数，`runtime.preflight` 与 `run_validation` 双入口调用，不改 parser | 往返/拖放/复制改动最小；不破坏差分测试 |
| D11 | 配置面板分段采用前端 `configSections.ts` 手写表（默认全基本）并逐步迁移，试点 6–10 个网页类高频节点；匹配数复用 `test-selector`（不高亮），防抖、单飞、运行中暂停、不自动启动浏览器 | 后端下发 advanced 标记应等 M2B 签名接口稳定后再做 |
| D12 | **待用户确认，5A 不实施**：规格 R5-19 要把全局导航改为左侧窄栏，但 2026-09-13 用户对项目管理原型对齐明确说过"导航按照现状，用顶部导航，不要换成侧边"（`.ai/memory/project-context.md`）。两者冲突，5D 开始前需用户明确是否取代旧决定 | 不擅自改变用户明确的导航决定 |
| D13 | 受 `newStudioLayout` 保护的只有：布局（底部状态条、右栏随选中收起、左栏折叠记忆、小地图默认值）、工具栏单行、命令面板与快捷键变化。**始终生效**的改动：快速添加面板、节点两行与细色条与外圈进度、状态与配置问题角标、配置面板"基本/高级"与字段级错误与匹配数、模块条"出错时"视图、动效三档、术语检查 | 这些是渐进改进，不改变整体布局；开关的作用是布局与快捷键的整体回退 |
| D14 | `newStudioLayout` 默认开启前的检查清单：①教学文档（`content-getting-started.ts`）与全局配置说明里的 Ctrl+K→Ctrl+J 文案；②旧布局的 Ctrl+K 提示与旧工具栏分支的去留；③Electron 实测（S7）的画布面积、单行不溢出、动效 computed-style；④"流程图/模块条切换"小组件配置在新工具栏里已按设置生效（已做）；⑤连续 7 天正确性/视觉回归 | 评审指出开关开启后静态文案会过期，默认开启前统一处理 |

