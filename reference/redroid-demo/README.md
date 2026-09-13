# redroid 管理 Demo

Python Flask + Docker SDK 后端，React + TypeScript 前端。直接复用并修正 RedroidManager 的管理实现，在同一界面演示实例管理、设备操作、APK 分发、三实例批量任务和 Magisk 镜像检查。

这是 `reference` 下的独立工程。真实运行和测试结果见 [VERIFICATION.md](VERIFICATION.md)，接口见 [API.md](API.md)，复制来源和许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## Mac 原生窗口验证入口

新增“页面监控 + scrcpy 原生操作”小闭环：运行 `bash scripts/start-native-mac.sh`，打开 <http://127.0.0.1:8082/native>。复现前置条件、真实验证结果与鼠标自动化稳定性限制见 [NATIVE_MAC_TEST.md](NATIVE_MAC_TEST.md)。该入口只用于本机单窗口验证，原 Demo 功能说明如下。

## Mac 启动（Apple Silicon）

本轮按用户要求在 Mac 本机实测：**macOS → Lima VZ → Ubuntu 24.04 ARM64 → Docker Engine → redroid 13**。使用 Apple 原生虚拟化；Android 使用 ARM64 的 `13.0.0_64only-latest` 镜像和软件渲染。独立 Linux VM 提供 binder 内核能力，管理页面仍在 Mac 浏览器中打开。

```sh
brew install lima
cd reference/redroid-demo
bash scripts/start-mac.sh
```

访问 **http://127.0.0.1:8081**。8081 转发到 VM 内管理服务的 8080，不与之前的 Docker Desktop 诊断页面冲突。首次下载 Ubuntu、内核模块、Android 和构建依赖需要网络；之后重复执行会更新 VM 内的 Demo 并保留设备数据。运行任务结束后再更新管理服务。整台 VM 停止后，重新启动管理服务会找回原设备；再在页面点击启动或批量启动，Android 不会自动启动。

VM 名称为 `autoflow-redroid`，配置在 [lima-mac.yaml](scripts/lima-mac.yaml)：6 vCPU、8 GiB 内存、40 GiB 虚拟磁盘。这是本次测试配置，不是最低硬件要求。脚本复制 Demo 源码进入 VM；Android 数据放在 VM 内 named volume，不共享 Mac 主目录，不更改 Docker Desktop 的默认 context。

```sh
bash scripts/start-mac.sh check
python3 examples/batch_demo.py --api http://127.0.0.1:8081
# 停止这台 VM，保留磁盘和 Android 数据
bash scripts/start-mac.sh stop
```

Mac 上构建 root 镜像时，在 Linux VM 内执行包装器：

```sh
limactl copy -r ../redroid-script autoflow-redroid:/tmp/
limactl shell --workdir=/tmp autoflow-redroid bash -c '
  cd "$HOME/redroid-demo"
  sudo python3 scripts/build_root.py --source /tmp/redroid-script \
    --base-image redroid/redroid:13.0.0_64only-latest --output .data/root-builds
'
```

宿主 ADB 检查在 VM 内运行，输出写到当前用户可写的位置：

```sh
limactl shell --workdir=/tmp autoflow-redroid bash -c '
  python3 "$HOME/redroid-demo/scripts/check_root.py" \
    --instance-id "<页面中的实例 ID>" --api http://127.0.0.1:8080 \
    --output /tmp/redroid-root-check.json
'
```

Mac 的实际结果与复测边界见 [MAC_TEST.md](MAC_TEST.md)。Windows 路线保留，但不属于本轮实测。

## Windows 启动

支持目标为 **Windows 11 x64 + WSL2 Ubuntu 24.04 + 安装在该发行版内的 Docker Engine/Compose**。Android 运行在 Linux 内核上，Windows 使用浏览器访问。Docker Desktop 不是本 Demo 验收基线。

准备顺序：

1. 在 PowerShell 用 `wsl --list --verbose` 确认 Ubuntu 使用 WSL2。
2. 在 Ubuntu 内按 [Docker 官方说明](https://docs.docker.com/engine/install/ubuntu/)准备 Docker Engine 与 Compose plugin，当前用户能够访问 `/var/run/docker.sock`。
3. 核查 [redroid 的 WSL 内核要求](https://github.com/remote-android/redroid-doc/blob/master/deploy/wsl.md)。binder/binderfs 等能力缺失时需要适配内核；该官方示例来自旧内核版本，不能直接推断当前系统已满足条件。自定义内核入口见 [微软 WSL 配置](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)。启动脚本不会替换内核。
4. 在 WSL 内预拉镜像：

```sh
docker pull --platform linux/amd64 redroid/redroid:13.0.0-latest
```

5. 将 Demo 代码放到 Windows 或 WSL 可访问的位置，在 Windows PowerShell 执行：

```powershell
# 从 reference/redroid-demo 目录运行
.\scripts\start-windows.ps1 -Distribution Ubuntu-24.04
```

也可以指定 WSL 中的项目位置：

```powershell
.\scripts\start-windows.ps1 -Distribution Ubuntu-24.04 -DemoPath '/home/me/autoflow/reference/redroid-demo'
```

脚本先检查宿主条件，再构建并启动管理服务。浏览器访问 **http://localhost:8080**。WSL localhost 转发有问题时，按 [微软网络说明](https://learn.microsoft.com/en-us/windows/wsl/networking)检查，不必把服务开放到局域网。

管理服务通过 Docker socket 创建兄弟 redroid 容器。Android 数据使用独立 named volume；不挂载 Windows NTFS 目录作为 Android `/data`。管理服务在容器内监听 8080，宿主只发布到 `127.0.0.1`；ADB 同样只发布到 Linux 宿主回环地址。

如果手动配置自定义 WSL 内核，先备份 `%UserProfile%\.wslconfig`。恢复时还原该文件或移除新增的 `kernel` / `kernelModules` 配置，再执行 `wsl --shutdown` 后启动发行版；此命令会停止当前运行的 WSL 发行版，应先完成正在执行的任务。

## Linux / WSL 直接启动

```sh
cd reference/redroid-demo
bash scripts/environment.sh
bash scripts/start.sh
```

检查会确认实际 Docker daemon 的平台和来源、binder 信号、默认镜像缓存。检查通过只是启动前提；每台实例还必须完成 Android 就绪检查。页面区分 Docker running、Android starting/ready/failed，不伪造运行设备。

镜像默认 Android 13、软件渲染；可选 Magisk 镜像需要按后面的步骤构建。只允许配置中的镜像；容器 port 始终是 5555，宿主端口由 Docker 原子分配并从 inspect 读取。

## 演示 1：实例生命周期

1. 查看环境诊断；准备好默认镜像。
2. 创建一台设备。默认 720 × 1280、DPI 320、2 CPU 配额、2048 MiB 内存上限，这些是可调整的 Demo 参数，不代表实测最低资源需求。
3. 等待 Android 状态变为就绪，再操作设备。
4. 停止、启动、重启设备；这些动作保留数据卷。
5. “复制配置”创建新实例和空数据卷，不复制 APK、登录态或应用数据。
6. 删除前确认目标。删除会移除该设备的专用数据卷；卷清理失败会显示错误。

最多保留三台 Demo 实例（包含停止的实例）；需要继续创建时先删除不需要的设备。所有修改操作检查专用标签，不会按任意容器名字操作 Docker 中的其他工作负载。

## 演示 2：屏幕、输入与 APK

选择一台就绪设备，打开查看后即可点击、拖动以及发送 Home、Back、Recent 等按键。画面采用每秒最多一次的非重叠截图请求；关闭查看或页面隐藏时停止刷新。坐标使用实际 PNG 尺寸，画面留白不发送触摸。

基础文字输入支持可打印 ASCII，包括英文、数字、空格；暂不支持中文输入法、多点触摸或视频级串流。

上传一个与 Android 13 及目标 ABI 兼容的单文件 APK（Mac 路线为 arm64-v8a，Windows 基线为 x86_64），选中目标设备后安装，查看每台设备的真实结果。单文件限制 256 MiB，不支持 XAPK/APKS/split APK 集合。设备包列表来自 Android 包管理器，可选中包名启动。未附带测试 APK。

## 演示 3：批量任务与 Python

界面可一次创建三台设备，或对选中目标批量启停、重启和安装。操作并发最多二；同一设备忙碌时拒绝冲突操作，每台设备分别显示结果。服务内任务记录有限且不跨进程重启恢复；重启后重新查询实例状态。

Python 示例只使用标准库，运行在能够访问管理 API 的 Mac、Windows、WSL 或 Linux 上（Mac API 端口改为 8081）：

```sh
python3 examples/batch_demo.py --api http://127.0.0.1:8080 --output .data/batch-runs
```

Windows 原生 Python 可使用 `py -3` 替换 `python3`。流程为创建本次专属实例、等待就绪、打开系统设置、保存截图、汇总结果，并清理本次创建的实例。示例不会删除此前已有设备；失败和清理错误使进程非零退出。运行前留出三台设备的容量。

## 演示 4：Magisk 镜像

构建步骤在 Linux amd64/arm64 中执行，需要 Docker、Python 3 和网络；Mac 使用前述 Lima VM 命令。先确保固定参考源码存在；如果单独复制了 Demo，也要准备它的相邻参考仓库：

```sh
git clone https://github.com/ayasa520/redroid-script.git ../redroid-script
git -C ../redroid-script checkout --detach a4951b782fc8e06c845d9553bf07bb643fd8c158
python3 scripts/build_root.py --source ../redroid-script --output .data/root-builds
```

已有相邻仓库时不重复 clone，直接执行构建命令。包装器在临时源码副本中运行固定版本，修正构建错误处理与下载边界，生成 `autoflow/redroid:13-magisk`；只有验证产物后才登记成功。输出保存构建来源、补丁和镜像信息，详细路径以命令输出为准。原参考源码保持不变。

刷新页面，在创建表单中选择 Magisk 镜像。设备操作区的 root 检查分别展示容器 exec UID、Magisk 版本和 shell `su` 结果。**容器 exec UID 为 0 不代表 Android App 已获 root。**

宿主 ADB 检查应在 WSL/Linux Docker 宿主执行（需要安装 Android platform-tools）：

```sh
python3 scripts/check_root.py --instance-id '<页面中的实例 ID>' --api http://127.0.0.1:8080 --output .data/root-check.json
```

宿主侧 ADB 与容器内部检查分开记录；脚本不会把管理容器自身的 localhost 当成 Docker 宿主。应用 root 必须另外用 APK 发起 `su` 请求并验证授权；没有做这个实验时，状态保持未验证。某个 Magisk/Android 组合失败不影响前面三个管理场景的使用。

## 停止与数据

Mac 使用以下命令停止专用 VM，保留 Android 数据；这不会停止其他 Docker Desktop 服务：

```sh
bash scripts/start-mac.sh stop
```

Linux / WSL：在页面删除不再需要的设备，确认任务完成后，在**实际 Docker 宿主内**停止管理服务：

```sh
bash scripts/stop.sh
```

Windows：

```powershell
.\scripts\start-windows.ps1 -Distribution Ubuntu-24.04 -Action stop
```

仅停止管理服务不会自动删除或停止动态创建的 redroid 容器、Android 数据或上传卷；重新启动管理服务后，通过标签重新发现原实例。停止整台 Mac VM 则会停止其中的所有实例，重新打开后需在页面启动设备。不要用全局 Docker prune 代替 Demo 清理。任务执行过程中停止管理服务会丢失进程内任务记录；再次启动时先核查设备状态。

## 本地开发与检查

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run typecheck
npm test -- --run
npm run build
cd ..
.venv/bin/python -m unittest discover -s backend/tests
python3 -m unittest discover -s scripts/tests
```

构建 React 后可启动 Python 服务查看页面。Docker SDK 使用 `DOCKER_HOST`，不会自动读取 Docker CLI 的当前 context；若需要只在 Mac 本机查看实际诊断页，可显式指向该 context 的 socket，系统仍会报告其不满足 Android 验收基线。

```sh
.venv/bin/python -m backend.app
```

前端开发模式用 `npm run dev`，由 Vite 将 `/api` 代理到本地 Python 服务。部署时同源服务前端与 API；浏览器变更请求校验来源，Python CLI 无 Origin 请求可使用。Host 仅接受 localhost / 127.0.0.1 / ::1；访问远程验证机时使用 SSH 转发到本机。

构建检查：

```sh
docker compose config
docker compose build
```

这些检查不代表已经验证 Android、WSL 内核或 root。实测记录按平台单列，见 [VERIFICATION.md](VERIFICATION.md)。实时摄像头、环境伪装、视频串流和集群调度不属于本批 Demo。
