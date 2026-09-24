# 项目任务 SSH 节点族（2026-09-24）

- `ssh_connect`、`ssh_execute_command`、`ssh_upload_file`、`ssh_download_file`、`ssh_disconnect` 复用冻结 WebRPA@5ccb900e 已迁入执行器及现有 Paramiko 服务，进入项目目录 167→172；Studio 有效范围仍为 213。项目目录剩余 41 个入口，包含不能作为普通执行节点的画布工具，不能将目录数量当作最终完成率。
- AutoFlow 必要适配：项目文档允许精确的 `{{cred:名称.字段}}` 托管引用，仍拒绝密码原文；项目文件端口提供密钥/上传读取及下载持久化，支持空二进制文件，保留大小、路径及父进程回执边界；命令输出按真实变量登记。生产执行器未重新设计。
- 专项命令：`cd apps/backend && uv run pytest tests/integration/test_project_ssh_worker.py tests/integration/test_b6_ssh_worker.py tests/integration/test_project_screenshot_writer.py tests/unit/test_workflow_drafts.py -q`：60 项通过（27.10 秒）。覆盖真实项目保存、五节点、空文件、退出码失败、长命令停止、下游不执行、连接关闭及本地命令子进程退出。无浏览器失败按原错误产物合同登记“截图不可用”，不伪造截图。之前关联回归 93 项、原版 SSH 差分/服务关联 43 项通过；Ruff、mypy、OpenAPI、目录及脚本检查通过。
- 正式 Electron [开发入口](../formal-project-ssh-electron-J7Ygg9/result.json)与[macOS arm64 本地未签名包](../formal-project-ssh-electron-IoxCUH/result.json)：真实 UI 添加五节点、配置、保存、正常关闭 Studio、创建项目自动化并启动任务，项目任务页查看文件。受控 SSH/SFTP 服务验证远程命令、上传、下载与 SHA-256；任务完成后活动连接为 0、命令进程退出码为 0。凭据通过真实系统密钥链创建/读取/删除，使用独立测试名称。没有修改用户数据库，没有启动其他浏览器。
- 保留失败证据：[正常关窗首次超时](../formal-project-ssh-electron-1rJnjo/blocked.json)、[旧固定名称凭据创建失败](../formal-project-ssh-electron-Uw4XmX/blocked.json)。前者补用系统 AX 关闭按钮，未使用 BrowserWindow.destroy；后者隔离测试凭据名称后通过。没有据此宣称所有跨构建的既有密钥链项目均已验证。SFTP 测试服务器保留已接受通道，修复通道被回收造成的偶发关闭；不改生产网络行为。
- PyInstaller 冻结后端与 Electron 目录包构建通过。包内 app.asar SHA-256：`6e7de4e80636aa7bb855a9dcaa19ec0a38708d615ecb278a3cc5fff08eb10127`；后端：`c9f8e1ca4d3f86eb0ee840ad19026397094dc8e13d537f69bf8707ed851608c2`；Electron：`afa086d829713c1385c6f15999898a8b959af24abb46df949ac324047afc30a7`。前端业务未改，复用此前 renderer 检查；本次正式包再次验证入口。证据 gitHead 是提交前基线。
- 外部 SSH 主机、macOS Intel、Windows、用户数据库、跨构建旧凭据访问未实测。开发/包内正常 UI 链路与 worker 异常测试分别记账，不把后者当作原生异常交互验收。
