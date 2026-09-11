# 浏览器管理桌面视觉验收

- 日期：2026-09-12；状态：confirmed（本记录覆盖本机人工 UI 验收，不替代最终代码审查和平台矩阵）。
- 基准：浏览器页面集成 `d1e4b9a`，macOS arm64，实际 Electron 应用，独立临时 userData。
- 工具：CUA 原生应用交互与截图；截图未经图像生成或编辑。

## 已观察结果

1. 浏览器配置页面是单主内容区，只有应用级导航；空列表显示创建第一个固定指纹环境。
2. 新建/编辑复用四个横向标签页。环境字段、高级说明折叠/展开、固定底栏正常显示。
3. 输入中文名称和描述，进入内核弹窗再返回后，两项输入均保留。原生自动输入工具的中文键入未生效时改用粘贴，已在辅助功能树中核实真实值后继续。
4. 内核列表来自真实 catalog，仅包含 CloakBrowser；本机已安装公开版 `145.0.7632.109.2`。正式版无 License 时按钮禁用，元数据缺失显示未知。
5. 内核删除确认默认聚焦取消，Escape 只关闭最上层确认；底下内核管理仍在。再次关闭内核管理后配置表单仍在。
6. “打开目录”通过实际 host IPC 打开 Finder，并定位验收目录内 `Chromium.app/Contents/MacOS/Chromium`。
7. 有修改时关闭表单出现未保存确认；选择继续编辑后仍可完成保存。
8. 创建真实配置成功，显示“配置已创建”。列表展示服务端生成的指纹、内核、语言/时区、代理模式及操作入口；完整 Reload 后配置仍在，编辑弹窗读回保存的名称和描述。
9. License 登录按钮曾发生换行，已反馈给 Task11 实现者并在最终构建再次观察确认修复。

## 产物与边界

- `docs/migration/browser-management-screenshots/profiles.png`
- `docs/migration/browser-management-screenshots/profile-environment.png`
- `docs/migration/browser-management-screenshots/kernel-manager.png`

截图使用测试名称“浏览器验收环境”，来自临时数据库，不是生产 fixture 或内置示例。使用的真实内核来自本轮冻结后端实际下载；没有输入 License，也没有迁移旧数据。测试窗口已退出，用户已有应用和业务目录未作修改。

默认窗口 1440×1024，CUA 输出为等比例缩小截图。1024/1280 的精确 viewport 边界、完整复制/删除闭环、断线恢复以及打包版结果由自动化测试和最终 [验收记录](../../docs/migration/browser-management-validation.md) 单独记录，不根据缩小截图推断。
