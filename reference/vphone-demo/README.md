# AutoFlow iOS 实验 Demo

日期：2026-09-13。独立 Python + React Demo，调用相邻的固定版 `vphone-cli`。实际结果见 [VERIFICATION.md](VERIFICATION.md)，范围见 [PLAN.md](PLAN.md)。

## 启动控制台

```sh
cd reference/vphone-demo
bash scripts/start.sh
```

打开 <http://127.0.0.1:8083>。没有 iOS 时也可查看真实环境检查和空状态。页面不使用 mock 设备。默认专用数据根目录 `~/.vphone-autoflow-demo`；与 `~/.vphone` 分离。设置 `VPHONE_DEMO_ROOT` 可改变位置，必须让控制台和 runtime.sh 使用相同设置，并保持完整 socket 路径短于 104 字节。

## 构建与首次运行

```sh
bash scripts/runtime.sh build
bash scripts/runtime.sh check
```

要求 Apple Silicon Mac、macOS 15+、完整 Xcode/iOS SDK。构建安装少量 Homebrew 工具和上游 Python 依赖，不更改 SIP/AMFI。第一次创建固件需要网络与较多磁盘，选择固件版本时遵循上游支持表；不默认选择最新 beta。

**当前宿主需要人工完成恢复模式配置，不能在普通终端里直接启动研究虚拟机。** 上游 README 的 Option B 是保留 SIP 大部分保护、仅放宽调试并允许研究 guest：

1. 结束其他任务并关机，长按电源进入启动选项 → 选项 → 终端。
2. 执行 `csrutil enable --without debug` 和 `csrutil allow-research-guests enable`，按系统提示选择安装并认证，然后重启到 macOS。
3. 阅读固定版上游 [SIP/AMFI 说明](../vphone-cli/README.md#sipamfi-relaxation)；运行已构建 app 内的 `reference/vphone-cli/.build/vphone-cli.app/Contents/Resources/vphone-amfidont`，按系统提示授权，使该二进制可以使用私有权限。此步骤应从项目根目录执行该路径，或者使用绝对路径。
4. 再运行 `bash scripts/runtime.sh check`。配置判断与实际 signed binary 检查都通过后，进入创建步骤。

以上为上游提供的路径，本次没有执行。恢复默认策略时，停止设备后在恢复模式执行 `csrutil enable` 与 `csrutil allow-research-guests disable` 并重启；不需要采用关闭全部 SIP/AMFI 的 Option A。

```sh
# 在真实终端交互选择固件；系统授权使用 macOS 原生弹窗
bash scripts/runtime.sh create af-ios-demo
# 首次创建/设置完成后如需再次启动
bash scripts/runtime.sh launch af-ios-demo
```

首次创建调用 upstream `vm create`，包含固件下载/补丁/恢复/CFW 安装并可能进入首次启动。失败后保留上游日志和设备目录，不自动覆盖或删除。窗口首次设置完成后，刷新控制台并读取截图。

## 三个实验

1. **画面与触控**：读取真实截图，点击图片或拖动进行滑动；使用 Home/音量/电源键；保存截图。坐标按配置完整像素换算，不把上游缩小后的 JPEG 当完整屏幕坐标。
2. **步骤回放**：默认“截图 → Home → 截图”；可编辑最多 20 个动作，逐步执行，任一步失败则停止。坐标 x/y/x1/y1/x2/y2 均为 0–1；swipe 可设置 ms。`clipboard` 只设置剪贴板，需在 App 内粘贴。当前没有自动 OCR 或元素定位，不提供未经验证的应用管理按钮。
3. **Python 真实链路检查**：`python3 demo.py smoke --device af-ios-demo`。成功需每一步同时收到成功响应及 JPEG；结果和截图保存到 `.data/runs/`。这只证明控制链路，不证明目标 App 的业务结果，需检查截图。未找到设备或 socket 时非零退出并记录失败。

HTTP：GET `/api/state` 获取设备、环境和本服务 token；POST `/api/action` 使用 `X-Demo-Token` 并提交 `{"device":"af-ios-demo","action":{"t":"screenshot"}}`；POST `/api/lifecycle` 提交 `{"device":"af-ios-demo","operation":"start"}` 或 stop。请求限同源 loopback。没有任意 shell、任意文件写入、远程监听或 sudo 密码接口。

页面启动的设备可以在页面停止；从终端启动的设备由原终端 Ctrl+C 停止。关闭控制台不自动终止虚拟机；控制台重启后不会恢复旧进程的停止权限，继续从原终端或 vphone 原生窗口关闭。日志 `.data/<name>.log` 保存上游启动结果；页面只显示当前已知状态，不把“进程存在/socket 存在”标为 iOS 就绪。

## 验证命令

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile demo.py
bash -n scripts/start.sh scripts/runtime.sh
cd frontend
npm ci
npm run typecheck
npm test -- --run
npm run build
```

协议测试使用临时 socket，不是真实 iOS，报告中单独列出。Demo 采用现有安卓 Demo 的依赖版本和 Vite 配置，自有代码由 AutoFlow 跟踪；不复制上游实现。上游源码、镜像、运行数据与 screenshots 不纳入主仓库。
