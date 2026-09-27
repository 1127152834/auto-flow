# SEC-04 Electron 来源与导航防护

日期：2026-09-28。状态：防御性自动检查通过；完整打包 UI 验收待最终阶段。置信度：高（已覆盖的入口逻辑）。提交：见本文件所在提交。

根因：窗口 ID 与 mainFrame 身份不能证明该 frame 当前仍是受信页面；主窗口没有导航阻止，开发环境变量还可影响打包入口。

最终行为：所有 main IPC 注册统一通过 handleIpc，先校验窗口与实际 frame URL，再进入原有按能力区分的权限检查。只允许对应窗口的精确入口文档；允许其 query/hash，拒绝相似域名、其他端口、其他文件、用户信息 URL、子 frame、空/未知页面。异步响应返回前复核；runtime-context 推送同样复核，避免页面变化后继续交付服务 token。主窗口与 Studio 同步拒绝页面导航、重定向、新窗口与 webview。打包应用忽略 ELECTRON_RENDERER_URL，开发模式保持明确配置的入口与服务 origin。

改动：main/index.ts、ipc/renderer-security.ts、ipc/automation-studio.ts。所有 ipcMain.handle 注册均在统一入口，当前没有额外 ipcMain.on 通道。控制器继续保留自身窗口/操作权限，未给 Studio 开放主窗口的文件或设置能力。

证据：

- electron-before.log：新增三项防御检查均失败，另有三项原生命周期测试失败，共 6 失败/7 通过。
- 生命周期旧测试缺 hide/isVisible，并错误假定主窗口关闭会销毁；当前 retainMainWindowForStudio 明确隐藏并保留交互所有者。补真实接口形状、断言隐藏/激活/复用及 Studio 存活，没有删掉生命周期断言。
- electron-expanded-before.log：新增打包断言的路径错误（Vitest 实际使用源码目录而非 stub __dirname），1 失败/109 通过；改为由测试文件位置推导精确真实入口，不改变产品实现。
- electron-after.log：11 文件、110 测试通过，涵盖所有注册通道的错误页面拒绝、异步返回复核、导航事件、合法本地/开发入口、打包环境变量、既有 IPC/Google/原生文件控制器契约。
- electron-lint.log：定向 ESLint 通过；electron-typecheck.log：tsc 通过。

本次为允许的本地防御性测试，未重试历史被自动安全审查拒绝的动态利用，也未读取或外传真实 token。不把单元事件测试描述为真实攻击成功或动态利用已验证。完整应用启动、保存与重启将在最终产物阶段验证。

设计依据：[Electron security：导航和 IPC sender 校验](https://www.electronjs.org/docs/latest/tutorial/security)、[webContents 事件语义](https://www.electronjs.org/docs/latest/api/web-contents)。现有 file 入口保留；自定义协议迁移不属于本次有界修复。
