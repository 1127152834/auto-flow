# T4：Checkbox、RadioGroup、Switch 与 Disclosure

- 日期：2026-09-12；状态：**implemented，本机自动验证通过；跨平台与实体键盘验收待完成**。
- 用户授权：T3 交付后回复“继续”，按既定顺序执行 T4；不进入 T5 或领域迁移。
- 工作树：`autoflow-ui-controls-plan` / `codex/ui-controls-plan`；起点 `985eb3d`。
- 只读核对主目录 `72a6157`：相对 `a1f3925`，shared/components 与 styles 没有已提交增量。本次没有合并主线其他任务。
- 使用技能：Superpowers executing-plans、test-driven-development、systematic-debugging、verification-before-completion。按已确认计划内联执行。

## 控件与调用约定

| 文件 | 本阶段能力 / API |
|---|---|
| ui/checkbox.tsx | Radix Root/Indicator；checked/defaultChecked 支持 boolean 或 indeterminate；勾/横线跟随 Radix data-state，所以非受控半选也正确；ref/name/value/onBlur 透传 |
| ui/radio-group.tsx | Radix Root/Item/Indicator，value/onValueChange、defaultValue、disabled、orientation、name、ref；组名称由 aria-label 或 aria-labelledby 提供，Item 通过 label 或 aria-label 命名 |
| ui/switch.tsx | Radix Root/Thumb，保留 checked/onCheckedChange、disabled、name、ref；关闭/开启/禁用仍用位置区分 |
| ui/disclosure.tsx | 原生 details/summary，summary:ReactNode、open/onToggle、ref 与标准 details props；隐藏系统 marker，Phosphor CaretRight；不叠加按钮角色、不重写键盘事件 |
| styles/controls.css | 复选/单选图形18px、实际控件命中32×32px；Switch命中44×32px，轨道44×24px，Thumb20px；统一边框、焦点、禁用、错误、120ms过渡及 forced-colors |
| shared/ui-lab/ToggleCases.tsx | 三态、禁用原因、长label、单选组错误、受控/非受控折叠、RHF boolean映射、错误聚焦、提交与reset |

组件保留语义和成熟交互，不提供虚构的 readonly/loading 开关 API。任务进行中由调用方 disabled 并给出原因。Label 可扩展命中区，控件自身已有32px高度；长标签使用独立文本容器换行。

RHF Checkbox 用 `onCheckedChange={checked => field.onChange(checked === true)}`，Switch 直接传 `field.onChange`。错误通过 `aria-invalid` 和 `aria-describedby` 指向 FieldGroup 错误；单选项的 ref 应连接需要聚焦的 Item，而不是仅能容纳选项的 Root。Disclosure 的受控调用为 `open={open} onToggle={event => setOpen(event.currentTarget.open)}`；不使用模拟点击或额外 Enter/Space 监听。

现有 Checkbox 的真实消费者是模型候选列表与设置诊断弹窗；Switch 的消费者覆盖浏览器环境/资源、代理和供应商。它们直接获得共享视觉更新。代理原生 radio、profiles/models 的 details、settings 的折叠按钮仍留在后续领域切片，未声称已完成全系统替换。

## 调试与验证边界

- TDD 红灯：修正 jsdom 缺少 ResizeObserver 的环境问题后，4条断言因缺 Indicator、radio角色、details/summary 失败；2条既有回调/禁用行为作为回归通过。实现后6条通过。展示页 RHF 测试先因缺案例失败，再实现通过。
- jsdom 不具备完整 summary 键盘默认行为：单元测试检查原生元素、点击展开及 open/onToggle；Enter/Space、Tab跳过收起内容由真实 Electron 检查，不为测试增加自定义键盘逻辑。
- 焦点样式检查：同步读取可能早于 Chromium 更新 focus-visible；失败截图中实际已有焦点环。改用真实 Tab/Shift+Tab 和 computed-style 条件断言，不加固定 sleep、不改产品焦点规则。
- 初次引入 RadioGroup 时，Vite 优化新依赖触发重载，同时观察到一次 `Cannot read properties of null (reading 'useMemo')`；没有完整堆栈能证明因果。后续保留 error.stack 记录，不隐去 pageerror。最终脚本使用临时 userData 下 node_modules/.vite 的独立冷缓存，并显式预优化 RadioGroup，避免和开发实例争用缓存；冷启动复验通过，不声称已证明原错误的唯一根因。
- **UI-T4-01：极快合成按键时序限制。** 本机安装的 Radix roving-focus 在 setTimeout 中移动焦点，radio-group 在 keyup 清除方向键标记；若零间隔 keyup 抢在焦点任务前，焦点已移动但值可能未改变。单元及 Electron 都观察到此路径。正常顺序检查分开发送 keydown/keyup，并等待实际焦点/选中条件；不把该结果当作零间隔序列已修复。实体键盘快速按键、长按及辅助技术仍待人工验证；领域 RadioGroup 迁移前复核此项。
- **UI-G0-01 继续保留**：T3 曾发现第一次 Escape 可能关闭内层 Dialog，根因未知。T4 不修改 overlay-host/Dialog，也不能凭本轮 G0 冒烟通过把待查项关闭；T5前单独复核。

## 样式回归修正

- 选中态的边框规则优先级覆盖了组错误颜色。先让样式/渲染稳定再断言，实际得到黏土棕 `rgb(141, 78, 47)`，与要求的危险色 `rgb(177, 60, 50)` 不符；调整 enabled 错误规则后选中/悬停仍保留红边框，disabled继续使用禁用样式。
- forced-colors 中误把 checked 当作 Thumb 父级状态，得到黑色滑块而非 HighlightText。改为读取 Thumb 自身的 data-state，滑块和轨道有清晰对比；错误项另用系统色虚线轮廓表达错误，不只依赖红色。
- 截图使用 Electron webContents.capturePage，并等候渲染帧及有限动效完成，避免截图仍停留在切换前一帧或过渡中间色。无限加载动效不参与等待。

## 最终检查

| 检查 | 结果 |
|---|---|
| npm test | 56 文件 / 296 测试通过（T3为53 / 289，本批增加7条） |
| shared定向测试 | 18 文件 / 62 测试通过 |
| npm run typecheck、npm run lint | 通过 |
| npm run build | 通过；原有 Zod PURE 注释警告保留 |
| node --test scripts/ui-tokens.test.mjs scripts/structure.test.mjs | 13/13通过 |
| npm run smoke:ui-controls | 12组通过，包含G0/T3回归、T4状态/键盘/RHF/样式及两个真实页面 |
| 生产隔离 | 生产JS无ToggleCases/实验室标记；CSS61个令牌存在 |
| 保护边界 | 225个源码SHA-256与T0一致；没有修改业务领域文件/后端/接口/main/preload |

实际平台为 macOS26.4.1 arm64 / Electron41.10.3 / Chromium146.0.7680.216，见 [机器结果](t4/results.json)。原G0的100/125/150/200%各两轮，新增T4长标签在200%下可见且无页面横向溢出。forced-colors为媒体模拟。

已查看的实际窗口截图：

- [控件状态与组错误](t4/09-toggle-controls.png)：截图在交互验证后保存，样本可切换，不以名称推断当前值。
- [高对比度媒体模拟](t4/10-toggle-forced-colors.png)
- [200%长标签](t4/11-toggle-200.png)
- [真实浏览器表单Switch](t4/12-real-browser-switch.png)：Space切换并恢复原值，取消新建，未保存配置。
- [真实设置诊断Checkbox](t4/13-real-settings-checkbox.png)：切换包含日志的本地预览后取消，没有导出文件。

脚本输出本批目录`t4/`，保留`t3/`历史。独立 userData、Vite缓存、Electron和sidecar均由脚本创建/清理；没有操作主项目或用户正在使用的窗口。

## 未执行

Windows、macOS实体键盘快速/长按、VoiceOver/NVDA、原生IME、系统滚动条偏好矩阵尚未运行。forced-colors 是 Chromium 媒体模拟，不代表 Windows 高对比度实机验收。展示页辅助检查和本轮真实页面冒烟不能替代后续五个入口的完整业务回归。
