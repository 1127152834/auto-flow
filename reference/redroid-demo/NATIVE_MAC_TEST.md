# Mac 原生安卓操作窗口：小闭环验证

- 日期：2026-09-13。
- 状态：**confirmed：小闭环已实测；原生输入稳定性仍有待定位项**。
- 用户范围：页面监控，点击后打开真实 Android 的原生操作窗口；只验证 Mac。没有接入正式 AutoFlow 安卓领域或工作流。
- 当前入口：<http://127.0.0.1:8082/native>。原 Linux VM 管理 API 继续使用 Mac 8081；8080 的另一套诊断服务未改动。

## 已验证行为

| 检查 | 结果与证据 |
| --- | --- |
| React 页面发现真实实例 | 从既有 8081 API 读取三台实例，无假数据 |
| 页面按钮打开原生窗口 | CUA 点击页面“打开原生窗口”，Mac 出现 `AutoFlow · Mac 日常测试 · afd-ef3857a550924052` 窗口 |
| 原生画面 | scrcpy 报告 redroid Android 13、Metal renderer、720×1280 texture；同时实际查看了原生窗口 |
| 鼠标点击与滑动 | 固定版 3.3.4 首轮从桌面点击 Gallery、返回桌面、滑动打开应用列表、点击 Notes 成功；所有操作经 Mac 原生窗口完成 |
| 键盘输入 | CUA 原生键盘在 Notes 原有测试文本后追加 `Native window verified 2026-09-13`；未调用网页 `/input` 或 `adb shell input` 来代替原生输入 |
| 关闭窗口 | 监控状态变为 closed，Android 仍为 running/ready；该窗口专用 SSH listener 已关闭 |
| 再次打开 | 从页面重新连接同一实例，测试文字完整保留 |
| 启动已停止设备 | 测试准备阶段经原 Demo API 停止该实例；CUA 点击页面“启动并打开原生窗口”，真实启动任务完成、Android 就绪、原生窗口出画面 |
| Android 重启后的数据 | 原生键盘在应用列表搜索并打开 Notes，再次看见完整测试文字 |
| 自动检查 | 新增 4 个 Python 测试；前端 28 个测试通过（其中本轮新增 2 个）；TypeScript 检查、Vite 构建、Python 编译、启动脚本语法检查通过 |

截图和结构化结果见 [verification/native-mac-2026-09-13](verification/native-mac-2026-09-13/README.md)。本轮没有删除实例、卷或已有应用数据；只追加了上述测试文字。

## 复现启动

在 `reference/redroid-demo` 中执行：

```bash
# 仅当现有 Mac VM/API 尚未运行时执行：
bash scripts/start-mac.sh

# 复用 Demo Python 环境；首次准备时执行：
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
cd ..

# 启动监控页及本机窗口启动器：
bash scripts/start-native-mac.sh
```

打开 <http://127.0.0.1:8082/native>，选择就绪或已停止的实例，点击对应按钮。终端需要保持运行；Ctrl+C 退出启动器并收尾它创建的窗口连接。关闭 scrcpy 窗口只结束连接；停止或删除 Android 仍属于原 Demo 的显式管理操作。

前置条件：Apple Silicon Mac、Lima、宿主 `adb`、可用的既有 Demo API 和 Python 3.12+。可通过官方 Android platform-tools 或 Homebrew 的 `android-platform-tools` 安装 adb。脚本检查已下载压缩包的 SHA-256，并解压固定版 scrcpy；不依赖全局 scrcpy 版本。

## 固定客户端与来源

- scrcpy **3.3.4** 官方 macOS aarch64 便携包；SDL **2.32.8**。
- 下载：[官方发布包](https://github.com/Genymobile/scrcpy/releases/download/v3.3.4/scrcpy-macos-aarch64-v3.3.4.tar.gz)。
- 校验来源：[官方 SHA256SUMS.txt](https://github.com/Genymobile/scrcpy/releases/download/v3.3.4/SHA256SUMS.txt)。
- SHA-256：`8fef43520405dd523c74e1530ac68febcc5a405ea89712c874936675da8513dd`。
- scrcpy 主项目 Apache-2.0；本轮仅调用官方二进制，不复制或修改上游源码；便携依赖随官方分发，正式产品打包时另行梳理依赖许可。原生窗口使用原始包内的 Android server，不混用不同版本客户端/server。
- 运行文件位于 `.data/native-monitor/`，含下载包、本机 `.app` 身份包装与会话日志，不入 Git。
- 官方连接思路：[redroid Getting Started](https://github.com/remote-android/redroid-doc#getting-started)、[scrcpy 连接](https://github.com/Genymobile/scrcpy/blob/master/doc/connection.md)。

## 实现边界

`frontend/src/NativeMonitor.tsx` 是与原 Demo 同一构建产物中的独立 `/native` 页面，只显示实例状态与启动窗口入口，不包含安卓点击、滑动或文字输入接口。

`scripts/native_monitor.py` 在 **Mac 宿主**运行 Flask/Waitress；Python 直接启动原生 scrcpy。VM 内的 Flask 不能自行把窗口显示在 Mac 桌面。启动器固定连接 `autoflow-redroid`，先核对 Mac 8081 与 VM 8080 的 API session ID，再通过原 API 读取带 Demo 归属校验的实例。

ADB 端口来自真实 Docker 映射；只接受 VM 回环地址。为每次会话创建独立 SSH 本机回环转发，scrcpy 连接相应 serial；不依赖 Lima 自动转发所有动态 ADB 端口。关闭时只终止本次持有的子进程、断开本次 serial，不执行 `adb kill-server`、不停止 VM 或 Android。

HTTP 仅监听 `127.0.0.1:8082`，校验 Host、同源 Origin、JSON 类型、实例 ID 和请求字段；页面不能提供可执行文件、命令参数、任意 IP 或 SSH 目标。启动过程在后台执行，状态区分 starting、connecting、open、closing、closed、failed；没有看到 scrcpy texture 输出不会报窗口就绪。

## 已发现的问题与限制

1. **原生自动化鼠标存在偶发偏移，尚未完全解决。** Homebrew scrcpy 4.1 / SDL 3.4.16 在本次 CUA 自动化中多次点击不同位置却向 Android 注入相同坐标。对照 3.3.4 首轮完成了点击/滑动/Notes 操作，但后续重连也有坐标异常，因此不能声称降版本彻底解决。键盘操作仍可完成重启后的内容核验。需要继续区分 CUA 合成事件、窗口焦点、SDL 坐标读取与真实鼠标输入；没有让用户手动验收，不能宣称真实鼠标完全稳定。SDL 的 [macOS 26 坐标问题](https://github.com/libsdl-org/SDL/issues/16152) 和 [3.4.16 Cocoa 源码](https://github.com/libsdl-org/SDL/blob/release-3.4.16/src/video/cocoa/SDL_cocoawindow.m) 仅作为线索，未认定为同一个缺陷。
2. **首轮日志缓冲误判已修正。** 将 stdout 直接写普通文件时，scrcpy 的 texture 日志未及时刷出；改为 PTY 读取并及时写日志后，能确认原生画面。真实窗口同时通过 CUA 截图核验，不单凭进程存活。
3. **一次仅一个原生窗口。** 本轮启动器拒绝重复打开和并发打开，尚未提供多窗口、自动聚焦已有窗口、正式工作流占用或暂停接管。原 Demo 的其他入口仍可操作同一实例；本验证只检查打开前 busy，不声称已经实现整个会话期间的排他租约。
4. **不承诺未测能力。** 中文输入、音频、摄像头、应用级 root、视频性能指标和 Windows 原生窗口未验证。启动参数关闭音频和自动剪贴板同步。
5. **本机依赖变动记录。** 研究初期执行 Homebrew scrcpy 安装，安装了 4.1_1/SDL3 并更新若干媒体依赖；其 cleanup 因无关的 `/opt/homebrew/lib/node_modules/@gsd-build/sdk` 权限返回错误，未处理该目录权限。scrcpy 4.1 本身可以运行，但当前启动器使用独立固定版 3.3.4，不依赖它。

结论：页面 → 本机原生窗口 → 真实 Android → 输入 → 关窗保留 → 重开/设备重启后数据保留的功能闭环成立，置信度高；鼠标在自动化重连场景的稳定性待进一步核验。进入正式模块前，应先解决这一输入兼容性问题，再接入设备与工作流控制权管理。
