# T3：按钮、文字控件与表单绑定

- 日期：2026-09-12；状态：**implemented，本机自动验收通过；手动 IME / 跨平台验收未完成**。
- 用户授权：在 T0–T2 交付后回复“好的 继续”，按约定执行 T3。
- 工作树：`autoflow-ui-controls-plan` / `codex/ui-controls-plan`，起点 a932626。只读核对主目录 17e0870；相对 a1f3925，共享 components/styles 无主线增量。本批没有合并其他任务的后台或模型改动。
- 技能：Superpowers executing-plans、test-driven-development、systematic-debugging、verification-before-completion；沿用独立 worktree 和已确认计划的内联执行方式。

## 实现与兼容约定

| 组件 / 文件 | 本批结果 |
|---|---|
| ui/button.tsx | primary / secondary / ghost / danger，32/40px，默认 type=button；ref、loading、loadingText；加载禁止重复激活、保留原可访问名称、预留文案占位以保持宽度 |
| ui/icon-button.tsx | 必填 aria-label，32/40px 方形命中区，加载用装饰 Spinner 替换图形；复用 Button |
| ui/input.tsx、textarea.tsx | ComponentPropsWithRef 保留标准事件、name、ref；统一 data-af-control、边框/焦点/只读/禁用/错误样式；size 为 sm/md，不透传成原生 size；数字仍由 input 与领域校验处理 |
| ui/search-input.tsx | 受控 value:string + 标准 onChange；可选 onClear 独立回调，清除后焦点回输入框；空值/只读/禁用不展示清除，loading 保留输入空间与值 |
| ui/password-input.tsx | 默认密码遮蔽；allowReveal 显式开启显隐；切换不提交、不改值，鼠标操作保留输入焦点；禁用状态不能显隐 |
| ui/spinner.tsx | Phosphor CircleNotch，aria-hidden；700ms 旋转，系统/应用减少动效时 animation:none，由所在按钮或字段提供状态语义 |
| FormField.tsx | 增加 render-prop，把 id/aria-invalid/aria-describedby 交给真实输入节点；错误消失恢复 hint。旧 children/clone 路径为领域迁移暂留，T12 移除 |
| FieldGroup.tsx | fieldset / legend，描述连到组，保留原生组禁用；不克隆或重写子输入 ID |
| shared/ui-lab/TextControlCases.tsx | 按钮、文字、数字、多行、搜索、密码状态矩阵；32/40联动、长文、RHF Controller/register/setFocus/reset案例 |

所有现有业务表单的提交按钮已显式 type=submit（ProfileFormDialog、ProfileActionDialog、LicensePanel、ProxyConnection、LocalProxyGroups），因此更改默认按钮类型不需要业务页面修改。现有 Input/Button/FormField 消费者直接获得共享视觉更新；SearchInput/PasswordInput/FieldGroup 的领域接入仍留在后续切片。没有扩建 packages/ui，也没有新增依赖。

SearchInput 保留输入事件与清除动作的不同语义，例如：

```tsx
<SearchInput value={query} onChange={event => setQuery(event.target.value)}
  onClear={() => setQuery('')} aria-label="搜索配置" />
```

FormField 与 Controller 的新用法是把属性交给实际控件：

```tsx
<FormField htmlFor="name" label="名称" error={fieldState.error?.message}>
  {a11y => <Input {...field} {...a11y} />}
</FormField>
```

## 发现与修正

- 行为红灯：占位导出后，13 条行为断言因缺少 loading、默认按钮类型、清除/显隐、FieldGroup 及 render-prop 绑定失败；原有输入透传行为保留作回归检查。实现后共享组件 33 条通过。
- 字号：Electron computed style 实测为 16px，违反 md=14px。旧全局 font:inherit 在 Tailwind 层外覆盖 utility；移入 @layer base 后，实测 md=14px / sm=12px，高度40/32往返通过。
- 字段对齐：有 hint/error 的网格项使相邻无提示项内部拉伸；FormField 增加 content-start，截图确认同行输入对齐。
- 展示页测试：新增错误案例后存在多个 alert，旧全局查询失效；限定到原有“表单绑定与错误聚焦”区域，仍检查原错误 ID、描述、焦点与重置行为。
- 开发入口测试：只改 hash 不会重新执行 main.tsx 的 DEV 分流；从实验室切到真实应用时显式 reload，再验证真实 sidecar/页面，不把实验室当业务页。

## 验证证据

执行 `npm run build` 后运行 `npm run smoke:ui-controls`。脚本沿用独立临时 userData；本批输出到 `verification/t3/`，保留 T2 的 g0 历史资产。脚本只操作自己启动的窗口，结束关闭实例并清理自己的临时数据。

| 检查 | 本批结果 |
|---|---|
| npm test | 53 文件 / 289 测试通过（起点47 / 273，新增16条） |
| npm run typecheck、npm run lint | 通过 |
| npm run build | 通过；原有 Zod PURE 注释警告仍在 |
| node --test scripts/ui-tokens.test.mjs scripts/structure.test.mjs | 13/13 |
| npm run smoke:ui-controls | 9组通过：原G0六组 + T3按钮/输入行为 + RHF/200% + 真实配置表单 |
| 保护/生产隔离 | 225个源码SHA-256与T0一致；生产JS无TextControlCases/样本标记；CSS61个令牌全部存在 |
| 真实应用 | macOS 26.4.1 arm64 / Electron41.10.3 / Chromium146；真实 sidecar 正常，打开新建浏览器配置、核对共享 Input 边界、聚焦、取消；不创建数据 |

机器运行信息见 [t3/results.json](t3/results.json)。最终脚本每个100/125/150/200%缩放各执行两次；另进行了三轮缩放诊断。ASCII/中文字符串 fill 已验证，不能据此声称原生 IME 组字已验证。

实际窗口截图，已查看：

- [按钮与字段状态](t3/05-text-controls.png)
- [搜索、密码、数字与表单](t3/08-search-password.png)
- [200% 表单焦点](t3/06-text-form-200.png)
- [真实浏览器配置表单](t3/07-real-browser-form.png)

## 浮层复验待查项

**UI-G0-01：根因未知，T5 前必须收口。** 一次复验在125%缩放下，鼠标展开组合框后第一次 Escape 使内层 Dialog 消失，随后 ArrowDown 找不到 popup。最终诊断显示只剩外层 Dialog；当次没有完整按键/滚动事件记录，不能认定根因是组件代码或测试时序。

当次保留的[窗口截图](t3/ui-g0-01-observed.png)和[可访问树](t3/ui-g0-01-observed-aria.txt)显示仅外层仍在。

增加 popup 所属层检查、Escape 后父层 data-state=open 断言和失败事件记录；之后两轮完整缩放通过，临时恢复原断言节奏再进行三轮缩放也通过。没有为消除此问题而改动 T2 的 overlay-host/Dialog 实现，**不宣称根因已修复**。T4 不依赖组合框，可继续；T5/G1 和领域选择控件迁移前，必须通过专门复现与压力测试重新评估 G0。既有 G0 报告是其当时结果，不能覆盖本待查项。

## 未执行与下一步

- 中文 IME 组字、候选确认；真实剪贴板交互；Windows、VoiceOver/NVDA：未执行。
- 全系统业务闭环与全部平台/缩放矩阵：未执行。本次真实页面检查仅限浏览器新建表单打开/焦点/取消。
- 主目录未修改、后端/接口/数据逻辑保护清单保持一致；分支尚未合入主项目。
- 下一步 T4：Checkbox、RadioGroup、Switch、Disclosure；G1 前处理上述浮层待查项。
