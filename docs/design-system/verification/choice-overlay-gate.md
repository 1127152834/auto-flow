# T2 / G0：控件基础与浮层兼容验收

- 日期：2026-09-12；状态：**confirmed，本机 G0 通过；全系统专项未完成**。
- 代码位置：独立 worktree `autoflow-ui-controls-plan`，分支 `codex/ui-controls-plan`。T0 基线 dff8860，T1 bb62007；G0 运行于 T2 提交前工作树，机器结果明确记录 `sourceIncludesWorkingChanges`，本报告与对应代码同批提交。
- 范围：T0 基线、T1 令牌与滚动条、T2 开发验收页/浮层宿主。T3–T13 未开始，不把此报告作为真实业务页面或全部控件完成的证明。
- 环境：macOS **26.4.1**、arm64；Electron **41.10.3**、Chromium **146.0.7680.216**。版本来自当前运行进程及系统查询。

## 1. 实现与复验入口

`npm run build` 后执行 `npm run smoke:ui-controls`。脚本在自己的 Vite 服务上加载 `#/__ui`，启动任务目录 Electron，传入 `mkdtemp` 创建的独立 userData，并校验 Electron 返回的实际目录。结束时只关闭自身窗口/服务并移除自己的临时目录，不使用共享 Electron、真实业务配置或账户。

日常开发可在开发 renderer 的 `#/__ui` 打开展示页；生产入口不会挂载此页。页面目前包含：

| 案例 | 已实现 | 后续范围 |
|---|---|---|
| A02 令牌/密度 | 暖灰/黏土棕色板、32/40 输入尺寸、常规/只读/禁用 | 所有控件完整状态在 T3–T7 加入 |
| A03/A04 表单 | 真正 RHF Controller、ref、错误绑定、setFocus、dirty、保存/重置、500 项搜索 | 严格单选和自由输入正式 API、IME、空/失效值等 T5 |
| A06/A07 浮层 | Radix Dialog → Dialog → AlertDialog，内层 React Aria ComboBox，本地横纵滚动样本、busy | 真实内核/配置弹窗接入 T8；通用菜单与 ScrollArea 在 T6 |

`LabCombobox.tsx` 是 G0 行为集成探针，领域不能直接 import。它不会写业务数据；500 项 CloakBrowser 名称只是明确标注的验收样本。

## 2. 锁定依赖与取舍

| 依赖 | 实际锁定版本 | 用途 |
|---|---|---|
| react-aria-components | 1.21.1 | G0 组合框成熟行为，T5 后封装应用 API |
| @radix-ui/react-radio-group | 1.4.7 | T2 按计划核对安装，T4 接入 |
| @radix-ui/react-scroll-area | 1.2.18 | T2 按计划核对安装，T6 接入 |
| @playwright/test | 1.63.0（开发依赖） | 真实 Electron 可重复自动验收 |

安装前已核对 peer dependencies 与现有 React 19 相容，锁定在 desktop workspace 和根 lockfile。没有运行 shadcn 生成覆盖命令。将原 T13 测试工具依赖提前到 T2，是为了 G0 当场就能复验实际窗口与焦点；不提前进行领域替换。

该版 React Aria 的 `UNSTABLE_portalContainer` 能将 popup 放入当前 Dialog，但类型已标 deprecated，推荐后续 PortalProvider。当前只在探针内隔离使用；T5 封装时复核该 API 并重跑本脚本，不能让领域依赖第三方 Portal 细节。

## 3. G0 检查结果

执行：`npm run smoke:ui-controls`，**6 组场景通过、renderer 异常 0**。机器输出：[g0/results.json](g0/results.json)。

| 场景 | 实际断言 |
|---|---|
| 隔离/令牌 | userData realpath 等于本脚本临时目录；DEV 页可达；全部色板 token 非空、背景不透明；只读/禁用背景不同；密度 40→32→40 |
| RHF | 空提交 aria-invalid 与 input 焦点；搜索 #0249 从 500 项中选值；dirty、setFocus、submit、reset |
| 嵌套与 Escape | popup 的最近 Dialog 深度为 1；首次 Escape 后 popup 消失，父层仍为 data-state=open，焦点回 Input；Tab/Shift+Tab 各 9 次均留在内层 |
| 忙与返回 | busy 时 Escape 无法关闭；第三层为 depth 2 且默认焦点在取消；依次关闭后分别返回删除、管理内核、打开验证触发器 |
| 缩放/滚动 | 外窗 1280×800 的 100/125/150/200% 下，首次鼠标展开与键盘展开均可用；popup 全部位于视口内；关闭按钮完整可见；End 使局部 scrollTop 增加 |
| 减少动效 | emulate reduced-motion 后弹窗动画小于 0.001 秒；无 renderer pageerror |

外窗包含标题栏；测到的 CSS 内容视口分别是 1280×768、1024×614、853×512、640×384。不要把外窗 1280×800 写成内容视口尺寸。初始窗口截图为 1440×1024 外窗，非独立的 1440×900 验收。

## 4. 发现和修正的问题

1. **Escape 同时关闭 popup 与父层。** Radix DismissableLayer 在 document capture 接收 Escape，早于 React Aria ComboBox 的目标节点处理器。仅检查可见性会被退出动画误导；现改为断言父层 `data-state=open`。每层 host 通过 `data-af-popup` 识别活跃 popup，父层阻止自身关闭，组合框保留自己的 revert/键盘处理，不重写 listbox 协议。
2. **下拉内容高度失控。** 初稿用了该版本没有提供的 `--available-height`；截图显示项目溢出容器。现在使用 Popover 的 `maxHeight={320}` 和自身 overflow-y，交给定位引擎收缩可用高度；完整 popup 可见范围断言与截图均复核。
3. **缩放后鼠标命中时序。** 测试原先在对话框入场动画尚运行时继续点击。改为等待实际 animation.playState 不再 running，再检验首次鼠标展开；不使用固定 sleep 或重试点击掩盖问题。连续两次 Escape 之间等待焦点返回，避免退出层尚未卸载时再次处理 Escape。
4. **200% 截图为空白。** 当时 DOM/焦点断言已通过，但 Playwright 截图文件未正确呈现窗口。未将空白图计作验收；改由 Electron `webContents.capturePage()` 保存实际窗口画面，重新查看确认内容存在。未证实具体底层截图原因，不将其描述成业务 UI 修复。
5. **RHF 错误关联与工具类型。** 错误消息通过稳定 id 绑定到真实 Input 的 aria-describedby；RTL 不接受 Playwright 的 exact 选项，已移除。最新 typecheck 与测试通过。
6. **只读选择器。** CSS :read-only 限于可用的 input/textarea，避免普通 button 被当成只读输入，也避免禁用输入同时匹配只读状态后因特异度覆盖禁用背景。运行时先复现两个背景均为 rgb(246, 243, 238)，修正后区分通过。
7. **声明存在但运行时缺少令牌。** 色板截图发现 success/warning 空白。普通 `@theme` 会裁掉未静态引用的变量，动态 inline style 读取不到；新增实际 computed style 检查先报 `Missing runtime token: success`，改为 `@theme static` 后所有色板通过。令牌是共享运行时 API，不能只靠源码解析测试验收。

实现仍保留现有 Button 等外观（例如删除确认探针使用旧 danger Button）；它们统一 token/API 属于 T3，不把展示页骨架当成最终视觉标准。

## 5. 截图复核

以下均为脚本启动的实际 Electron 窗口，已逐张查看，不是生成图：

- [令牌与展示页骨架](g0/01-lab.png)
- [两层 Dialog 内的搜索选项浮层](g0/02-nested-choice.png)
- [第三层删除确认](g0/03-third-layer.png)
- [200% 缩放与可见关闭操作](g0/04-zoom-200.png)

## 6. 自动回归与隔离边界

| 检查 | 本批最终结果 |
|---|---|
| npm test | 47 文件 / 273 测试通过（T0 为 45 / 270） |
| node --test scripts/ui-tokens.test.mjs scripts/structure.test.mjs | 13/13：令牌 10、目录结构 3 |
| npm run typecheck | 通过 |
| npm run lint | 通过 |
| npm run build | 通过；原有 Zod PURE 注释警告仍在 |
| 生产 renderer JS 扫描 | 仅 1 个 JS chunk，无 lab marker、UiLabPage、展示页标题或 fixture 文本 |
| 生产 CSS 令牌扫描 | tokens.css 声明的 60 个变量全部保留 |
| 保护源码 SHA-256 | T0 清单 225 个文件全部一致，包含后端/main/preload/契约/领域数据逻辑 |
| git diff --check | 通过 |

生产 JS 为约 1785.02 kB（T0 1783.13 kB），CSS 55.39 kB（T0 48.54 kB）。DEV JS 与 fixture 已剔除；Tailwind 静态扫描仍可能生成展示页使用的 utility CSS，这与运行时代码隔离是两个检查项，不声称 CSS 完全没有展示案例样式。

## 7. 未执行项目与下一步

- Windows：未执行。VoiceOver/NVDA、forced-colors 的实际读屏/平台行为：未执行。
- 触控板、拖拽滚动条、macOS 自动/常显设置矩阵：未执行；当前仅原生窗口截图和键盘滚动证据。
- 1024×768 与 1440×900 的独立外窗矩阵、输入法、大量选项性能测量：未执行。
- 浏览器、内核、代理/池、模型、设置、总览真实页面的控件迁移及视觉验收：未执行。已有业务自动测试仍通过，不能替代真实页面验收。

本批 G0 允许继续 T3–T7 共享控件；组件 API 和状态通过 G1 后再迁移领域。T13 平台与辅助技术矩阵未完成前不能关闭整个控件统一专项。
