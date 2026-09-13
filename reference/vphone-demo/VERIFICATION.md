# iOS Demo 验证记录

- 日期：2026-09-13；状态：confirmed（本机执行证据）。
- 结论：源码克隆、宿主/guest 编译、独立控制台及协议测试完成；**真实 iOS 尚未启动，截图/触控/步骤回放未通过实机验收**。
- 置信度：构建、测试及当前宿主阻塞为高；目标 App 兼容性、真实回放稳定性为未知。

## 代码与产物

| 项目 | 固定版本 / 实际结果 |
| --- | --- |
| vphone-cli | `9c23c8adcd4b362120988ab9d228b959bcc23ae3`；递归子模块初始化完成，tracked source 无修改 |
| vphone-aio | `1db79dccd95391d6247c41f3cc4eac523567f295`；7 个归档保留 LFS 指针，未下载约 12GB 镜像 |
| 工具准备 | `zsh scripts/setup_tools.sh` exit 0，trustcache / insert_dylib / Python 依赖可用 |
| 宿主构建 | `make build` exit 0 |
| 完整打包 | `zsh scripts/build.sh` exit 0；`.build/vphone-cli.app` 和 `.build/vphoned.signed` 已生成并签名 |

构建过程安装了 Homebrew `gnu-tar`、`ldid-procursus`、`sshpass`、`keystone` 及所需依赖，Python 依赖位于上游 `.venv`。最初 Homebrew 的自动清理遇到现有全局 Node 目录权限问题，随后关闭自动清理完成工具准备；未修改该目录权限。完整本地日志在被忽略的 [setup-tools.log](.data/setup-tools.log) 和 [build.log](.data/build.log)。没有更改 SIP/AMFI、安装镜像或重启宿主。

## Demo 验证

| 验证 | 结果与边界 |
| --- | --- |
| Python unittest | 6/6 通过：真实临时 Unix socket 分帧、坐标换算、缺图/错误/超时拒绝、命令和路径约束、HTTP 来源/token 约束 |
| Python / Shell 静态检查 | py_compile、bash -n、Ruff E4/E7/E9/F/I 通过 |
| 前端 | TypeScript、Vite production build 通过；Vitest 3/3；项目现有 ESLint 配置检查通过 |
| 浏览器 | Codex 内置浏览器访问 `127.0.0.1:8083`，确认真实宿主诊断、已有构建产物、研究许可 disabled、设备空列表、设备操作禁用；没有示意设备画面 |
| 无设备 smoke | exit 1，明确失败“设备不存在”，未生成通过记录；[原始结果](verification/smoke-without-device.json) |

协议单测使用临时 socket 与合成响应，仅验证传输逻辑；JPEG 检查为 base64 和首尾标记检查，不等同于完整图像解码、实际 iOS 画面或业务断言。前端单测使用测试夹具，生产页面读取真实后端。

## 实际阻塞证据

- Apple Silicon 物理 Mac；macOS 26.4.1，Xcode 26.2。
- `csrutil status`：SIP enabled。
- `csrutil allow-research-guests status`：disabled。
- 上游 `scripts/boot_host_preflight.sh --assert-bootable`：signed release binary 的 `--help` **exit 137**，host preflight 同样失败。
- Demo `doctor`：exit 2、`canAttemptLaunch: false`。

原始证据：[host-preflight.txt](verification/host-preflight.txt)、[doctor.json](verification/doctor.json)。系统策略未满足且签名二进制被终止，不能以成功编译推断实际虚拟机可以运行。preflight 文字列出完全关闭 SIP 的旧通用路径；当前固定版 README 同时提供仅放宽 debug 的 Option B，操作指南采用后者。

## 重启后的继续入口

按 [README](README.md#构建与首次运行) 完成恢复模式配置与上游二进制权限配置后：

1. `bash scripts/runtime.sh check`，确保配置检查和签名二进制实际执行均通过。
2. `bash scripts/runtime.sh create af-ios-demo`，在终端选择受支持固件并完成首次启动。
3. `bash scripts/start.sh`，读取实际画面，验证点击/滑动/按键/剪贴板。
4. `python3 demo.py smoke --device af-ios-demo`，保存三步真实画面及结果；再选择目标 App 做业务流程验证。

尚未验证：固件创建/恢复、iOS 启停、真实截图触控、剪贴板粘贴、目标 App 安装登录、多实例、Windows 远程控制。上述完成后追加新证据；本记录不能作为这些能力的通过证明。
