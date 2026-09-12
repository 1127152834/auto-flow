# 全系统控件统一：实施和验收结果

日期：2026-09-12。状态：**控件与组件实现完成；本机自动验收通过；G3 跨平台人工验收未完成。**

分支 `codex/ui-controls-plan`，位置 `/Users/zhangtiancheng/Documents/projects/autoflow-ui-controls-plan`。本轮起点 `4b2df63`，T6–T7 提交 `6ea07c8`，T8 提交 `5b72457`，后续连续完成 T9–T13 可执行部分。没有合并到主线，没有修改主目录或用户正在使用的 Electron。

## 交付内容

- 统一令牌、Input/Textarea/数字文本/Password/Search、Button/IconButton、Checkbox/RadioGroup/Switch、Select/Combobox/Autocomplete、滚动条/ScrollArea。
- 统一 Dialog/AlertDialog/Modal/Drawer、菜单/Tooltip、Tabs/Disclosure、Table/Pagination、Badge/Alert/EmptyState/Skeleton/Progress/Spinner/Toast。
- 浏览器/内核、代理/代理组、模型、设置、总览、应用壳的真实控件均接入共享实现；模型 TagInput 属于领域组件，不扩建通用多选库。
- FormField 仅显式 render-prop；Select 仅一个正式入口。固定枚举禁用清除，保留原合法空选项；清空输入不伪造原生 ChangeEvent。
- DEV `#/__ui` 展示页供正式验收辅助；生产包无实验室或专用样本。`packages/ui` 保持骨架，没有第二套组件 API。

具体文件/行为边界：[领域接入记录](domain-controls.md)。当前调用位置：[AST 审计](ui-controls-audit.json)。

## 最终自动检查

| 命令 | 结果 |
|---|---|
| `npm run test:structure` | 通过，3 项 |
| `npm run test:scripts` | 通过，22 项（含 token 对比度、AST 审计和结构检查） |
| `npm test` | **70 个文件，325 项通过** |
| `npm run typecheck` | 通过 |
| `npm run lint` | 通过 |
| `npm run build` | 通过 |
| `npm run audit:ui` | 通过；106 个主入口可达源码、11 个 DEV 文件、4 个单列未接入/声明文件；0 原生绕过；生产无展示页泄漏 |
| `npm --workspace @autoflow/desktop run test:ui` | **5 项通过**；其中 3 项真实 App/sidecar，2 项明确的页面 API fixture |
| `npm run smoke:desktop` | 桌面连接健康，桌面结束后 sidecar 退出 |
| `npm run smoke:ui-controls` | **16 组通过**，含 500 项选择性能、滚动条、键盘/焦点、RHF、忙态、真实 Switch/诊断 Checkbox |
| SHA256 保护范围 | **225 个文件，0 个变化**；见 [保护检查](protected-final.json) |
| `git diff --check` | 通过 |

命令日志存于 `final-command-logs/`。`source-manifest.json` 记录被测源文件哈希，防止仅靠变更前 HEAD 识别测试对象。日志中的 `codeBaseCommit` 加 `sourceIncludesWorkingChanges` 表示测试包含本次未提交源码，不表示只测了旧提交。

## 真实页面证据

macOS 26.4.1 arm64，Electron 41.10.3 / Chromium 146.0.7680.216。测试创建独立临时 userData 并核对 `app.getPath('userData')`，本地服务/数据库仅属于该目录；finally 关闭自己的 Electron、Vite 并清理目录。未使用主目录数据库。

- 五个真实页面 + 浏览器四个页签 + 嵌套内核弹窗：axe WCAG 2 A/AA、2.1 AA 自动扫描无违规。
- 浏览器表单：1280×800、1440×900、1024×768 × 100/125/150/200%，共 12 组；操作可达、内核弹窗在视口、关闭返回焦点、无文档横向溢出。其余四个页面额外检查 1024×768 / 200%。
- 真实代理空连接表单检查密码显隐；真实模型向导检查连接字段；真实设置检查缩放保存、详情展开及诊断预览。没有提交远程凭据或执行文件导出。
- 代理页面 fixture 检查 SOCKS5、详情 Drawer、成员筛选不丢勾选与顺序；模型页面 fixture 检查候选元数据、自由 ID、标签和保存 payload。fixture 响应不是远程服务联调结果。

截图和运行矩阵：[real-pages/summary.json](real-pages/summary.json)。控件级证据：[final-controls/results.json](final-controls/results.json)。已目视检查模型编辑和代理组截图；其余布局自动检查、截图留存，不能声称每一帧人工检查。

axe 默认在新页面聚合结果，但 Electron 协议不支持 `Target.createTarget`。依据已安装 `@axe-core/playwright` README 的接口，测试使用 `setLegacyMode()`；真实扫描前断言页面没有 iframe。这是 Electron 适配，不是关闭规则；跨域 iframe 检查不在本应用场景中。axe 不能替代人工读屏和实体键盘。

## 未执行项及已知问题

[平台矩阵](ui-controls-platform-matrix.md) 完整列出 Windows、VoiceOver/NVDA、实体中文输入法、macOS 系统滚动条模式切换和远程账户条件。`UI-T4-01` 的零间隔合成键盘 RadioGroup 竞态保留，未伪称修复；正常 down/up 自动路径通过。

实现与本机自动检查结论置信度高；Windows/辅助技术实际表现仍未知。当前不宣称“全平台验收完成”。
