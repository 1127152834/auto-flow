# redroid Demo 验证记录

- 日期：2026-09-13（Asia/Shanghai）。
- 状态：**confirmed：源码、打包及管理服务通过；Android / Windows / Magisk 实机结果未知，待验证**。
- 范围：已确认的 [PLAN.md](PLAN.md)；独立 Flask + React Demo，不改 AutoFlow 正式运行架构。

## 已执行的检查

| 检查 | 结果与证据 | 能证明的范围 |
|---|---|---|
| Python 后端 | Python 3.11.13 本地 25 项 unittest 通过；Linux amd64 管理镜像内 25 项也通过 | Docker 替身覆盖端口/卷隔离、busy、两线程容量、超时隔离、就绪、APK、root 诊断等关键分支 |
| React 类型与静态检查 | `npm run typecheck`，另加 TypeScript unused/fallthrough 检查通过 | API 类型及组件代码静态检查 |
| React 交互 | Vitest 3 个文件、17 项测试通过 | 创建/部分失败、API 错误、按键与文本、真实尺寸坐标、点击滑动、留白、截图刷新边界 |
| Python 部署/示例 | 7 项 unittest 通过 | 丢响应后的延迟实例清理、部分创建失败仍继续成功目标、清理超时、root 构建失败记录、loopback 绕过环境代理 |
| Python lint / 编译 | Ruff 0.15.17 `E9,F63,F7,F82` 检查、compileall 通过 | 致命语法/名称错误检查；没有声称执行完整风格格式化规则 |
| Shell / Compose | `bash -n`、`docker compose config --quiet` 通过 | Linux shell 语法和 Compose 配置有效；PowerShell 未实测 |
| 生产构建 | 本地 React 构建通过；Docker Compose 原生 arm64 管理镜像及 buildx Linux amd64 管理镜像构建通过 | Python 3.11 + Node 22 多阶段打包，包含上游许可和来源说明 |
| 管理服务 | Compose 启动后 healthy；`/`、environment、instances、jobs 实际 HTTP 检查通过 | 页面及 API 可启动，真实连接 Docker，不生成假设备 |
| 不满足条件时的行为 | Docker 已连接，environment.ready=false；创建返回 503 host_unsupported；count=4 返回 400；跨来源/非本机 Host 返回 400 | 拒绝不支持的实际宿主和非法请求，测试结束仍为零台 Android |
| 真实 Docker exec | 在本次管理容器运行固定 Python 输出，分别核验 stdout、stderr、退出码和容器 running 状态 | Docker SDK 7.2.0 的真实 socket 分帧解析可用；这不是 Android 命令成功的证明 |
| 浏览器 | 打开最终页面、点击“重新检查”、观察诊断与禁用状态；无控制台 error/warn | 前端真实联通管理 API，空设备/失败环境画面已目视检查 |
| 上游与许可 | 两个参考仓库 HEAD 与固定版本一致，git status 为空；复制的 LICENSE 与上游 SHA-256 相同 | 未修改上游基线，复制来源可以追溯 |

以上合计 **49 项自动测试**（25 后端 + 17 前端 + 7 脚本），重复在另一架构运行后端测试不重复计数。自动测试中的 Android 使用替身；截图坐标测试使用受控图片尺寸，不能替代真实 APK 和设备实验。

## 本次实际宿主

- macOS arm64；本地 Node 26.7.0，Python 3.11.13 用于后端兼容检查。
- Docker Desktop 4.83.0；Docker Engine 29.6.2，daemon Linux arm64，内核 `6.12.76-linuxkit`；Compose 5.3.1。
- 管理镜像运行时 Python 3.11.16；前端构建阶段使用 Node 22。
- 原生管理服务监听 `127.0.0.1:8080`。Linux amd64 镜像通过本机跨架构执行运行后端测试，**没有在 Windows/WSL 上执行**。
- 环境诊断实际结果：`docker_host=fail`、`binder=fail`、`images=fail`。没有拉取 redroid 镜像，没有启动 Android，也没有执行 Magisk 下载/构建。
- 本次只保留管理服务、其 Compose 网络/上传卷与构建镜像，供继续查看；跨架构测试容器用 `--rm` 回收。没有 Android 容器或 Android 数据卷。停止方式见 README。

## 真实设备待验收项

| 场景 | 状态 | 下一次执行及记录内容 |
|---|---|---|
| Windows 启动 | 未验证 | Windows 11 x64、WSL2 Ubuntu 24.04 内 Engine；记录 WSL/内核/Engine 版本、binder 条件、PowerShell 启动和 Windows 浏览器访问 |
| 单实例生命周期 | 未验证 | 实际 image ID/digest、Android release、boot 时间；启停/重启后数据标记保留，删除卷无残留 |
| 设备操作 | 未验证 | 两个分辨率的点按/滑动与按键；真实截图；ASCII 输入；已知 ABI 兼容 APK 安装启动；无效 APK 的真实错误 |
| 三实例隔离 | 未验证 | 运行 `examples/batch_demo.py`，保存逐台结果与截图；检查三个 ADB 端口、专用卷与独立数据标记 |
| 实际故障和清理 | 未验证 | 启动超时、单台安装失败、冲突 busy；确认其他目标继续，清理只影响本次资源，核对容器及卷 |
| Magisk 镜像 | 未验证 | 固定 redroid-script 构建记录、base digest、下载 APK SHA-256、最终 image ID、新镜像启动/重启 |
| 宿主 ADB root | 未验证 | 在实际 WSL/Linux 宿主运行 `scripts/check_root.py`；保留 adb root、shell id、magisk、su 原始结果 |
| Android 应用 root | 未验证 | 用独立 APK 请求 su、确认授权并保留应用侧输出；容器 UID 或 adb shell UID 不能替代该结果 |

可复现命令见 README。Linux amd64 镜像的附加检查命令如下；测试文件有意不放进运行镜像，因此测试时只读挂载：

```sh
docker buildx build --platform linux/amd64 --load -t autoflow-redroid-demo:amd64-check .
docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,source=$PWD/backend/tests,target=/app/backend/tests,readonly" \
  autoflow-redroid-demo:amd64-check python -m unittest discover -s backend/tests -v
ruff check --select E9,F63,F7,F82 backend scripts examples
python3 -m compileall -q backend scripts examples
```

## 交付判断

源码与管理界面交付完成（置信度：高）；Windows、真实 Android 和具体 Magisk 组合兼容性（置信度：未知）。摄像头、环境伪装、视频串流和集群调度仍按计划留给后续专项 Demo。
