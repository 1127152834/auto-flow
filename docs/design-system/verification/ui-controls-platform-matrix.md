# UI 控件平台验收矩阵

日期：2026-09-12；状态：实现完成，G3 跨平台人工验收未完成。不能把本机 Electron 自动测试推广为 Windows/读屏/真实输入法通过。

| 平台 / 环境 | 场景 | 方式 | 结果 / 证据 |
|---|---|---|---|
| macOS 26.4.1 arm64，Electron 41.10.3 / Chromium 146.0.7680.216 | 1280×800、1440×900、1024×768，各 100/125/150/200%；浏览器表单保存/取消与内核弹窗、水平溢出 | 真实 App、真实隔离 sidecar；运行时 webContents 缩放，不写入业务缩放枚举 | `real-pages/summary.json` 的 12 行矩阵与截图；以最终报告为准 |
| 同上 | 五个真实导航页面、浏览器四个表单页签、嵌套内核 | axe WCAG2 A/AA、2.1 AA | 真实页面，不注入业务 mock；结果见 `real-pages/summary.json` |
| 同上 | 代理详情协议、成员勾选、搜索后顺序；模型候选/手动 ID/标签/payload | 明确的页面 API fixture + 真实生产页面组件 + axe | 不代表 ProxyPanel 或模型服务实网验证 |
| 同上 | DEV 展示：radio/checkbox/switch、下拉/搜索、500 条虚拟化、滚动条、焦点、键盘、RHF、减少动效、忙态和反馈 | 共享控件 fixture，Electron 合成输入 | `final-controls/results.json`；16 组检查，正常键盘按下/抬起顺序 |
| 同上 | 代理 API Key 显隐、模型连接表单、设置缩放、诊断 Checkbox/预览 | 真实隔离 sidecar | 不提交真实 API Key，不触发文件导出或 License 下载 |
| macOS 系统“自动/始终显示滚动条”分别切换 | 页面/弹窗/水平轨道 | 系统设置与人工 | **未执行**；CSS/轨道计算不等价于两种系统设置实测 |
| macOS VoiceOver | 标签朗读、错误、单选组、组合框、嵌套焦点 | 读屏人工 | **未执行** |
| macOS 中文实体输入法 | composition/候选窗口/Enter、空值/草稿 | 真实输入法人工 | **未执行**；Unicode fill 和合成 composing 事件不能代替 |
| Windows + 系统显示缩放 + 常显滚动条 | 同上所有窗口/缩放/真实页面 | Windows Electron | **未执行：当前无 Windows 执行环境** |
| Windows NVDA / 中文输入法 | 同上读屏与 IME | 人工 | **未执行** |
| 实际远程账号 | License 登录、正式版下载、ProxyPanel 写操作、远程模型测试 | 实网账号 | **本轮未执行**；不得用 fixture 宣称通过 |

## 已知待验收项

`UI-T4-01`：Radix RadioGroup 的零间隔合成 keyup 可能先于异步焦点，造成焦点移动但值未更新。正常 down→等待焦点/值→up 的自动检查通过；保留历史复现，不将其标为修复。需使用 Windows/macOS 实体键盘与读屏确认用户实际路径；若复现，应先最小复现并核对 Radix 行为，不在领域页面堆补丁。

G3 关闭条件：完成以上人工/Windows 条目，或用户明确调整交付验收边界。当前没有将这些条目勾选为完成。
