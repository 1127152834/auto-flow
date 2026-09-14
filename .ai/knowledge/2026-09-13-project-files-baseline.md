# PM2 受控文件交互接入基线

- 日期：2026-09-13；状态：confirmed（只读代码盘点），实现仍planned。
- 来源：当前implementation的shared/settings.ts、preload/index.ts、main/index.ts、main/ipc/settings.ts、settings controller、proxy-credentials/kernel-paths；旧browser-automation仓库324748a的autoflow-desktop/src/main/excel-file-picker.ts及测试。

1. 复用DesktopResult，选择取消为ok/value:null。拟新增shared/project-files.ts和main/project-files/{registry,controller}.ts；renderer只见token/displayName/kind/expiresAt，不接收任意path。
2. IPC绑定创建时主窗口webContents.id，并校验senderFrame为mainFrame；projectId为规范UUID，输出建议名只是安全basename。dialog前捕获workspace/instance/window，返回后复验仍为同一上下文再登记，防切换期间迟到选择。
3. 输入单个.xlsx regular file；输出只能受控新文件，保留中文/空格。文件操作前由基础设施再核验身份与fingerprint；dialog本身不创建输出。
4. 主进程没有供sidecar反向兑换的现成RPC。沿PM2执行卡，通过hostToken保护的/internal/project-files/register把授权登记到当前sidecar短期registry；公开inspect/export仅交token，按project/purpose/instance原子领取。不是新增main HTTP server。
5. token绑定window/workspace/instance/project/purpose/action/expiry；主进程保留ownership供回收。窗口关闭、真实工作区切换、restart/shutdown停止实例前撤权；新实例不接受旧token，结果未知查询原Operation而非重发文件写入。
6. Host上下文从SettingsController.getHostStatus取得，不进入renderer；遵循现有127.0.0.1内部endpoint校验、redirect:error、timeout/no-store及x-autoflow-host-token。当前bootstrap已拒internal请求Origin并验证hostToken。
7. 旧picker可借鉴单选xlsx/取消null/窗口销毁行为测试；旧直接返path、仅sender校验不满足新边界，不复制其安全缺口。

本盘点未启动旧应用、未选择真实文件、未操作账号凭据或修改主目录。Google实网、Windows和文件IPC运行验收未执行。
