# redroid 现成管理系统与源码借鉴研究

**结论：有可用组件和有实质源码的管理系统，但在本次核查的公开项目中，没有找到一个可以直接接入 AutoFlow、同时完整满足批量生命周期、通用安卓自动化、环境配置、应用级 root 和实时摄像头输入的成熟一体化产品。** 最值得优先验证的是 Webscreen 的网页控制、RedroidManager 的简单实例管理、redroid-script 的镜像改造，以及 STF 的设备分配。Damru 的设备池与批量浏览器任务非常相关，但用途和许可都有明确边界。

本文适用于 AutoFlow 的技术选型与源码借鉴，资料核查日期为 **2026-09-13**。仓库功能判断固定到文末记录的 commit；“有代码”表示对应实现存在，不等于已经通过实际部署、负载或目标应用兼容测试。置信度分为：**高**——公开源码或明确项目文件支持；**中**——据源码提出的适配判断；**未知**——缺少独立运行证据。实施建议均为 **proposed**，不构成已批准的架构变更。

## 1. 优先级与现成程度

| 项目 | 已有成果 | 对 AutoFlow 的主要价值 | 主要边界 | 判断 |
|---|---|---|---|---|
| [huonwe/webscreen](https://github.com/huonwe/webscreen) | 网页远程控制、音视频传输、redroid Compose 示例、跨平台二进制 | 安卓屏幕嵌入、交互接管 | 不负责创建、销毁和分配容器；AGPL-3.0 | **优先试用的显示控制组件** |
| [JinHisAndy/RedroidManager](https://github.com/JinHisAndy/RedroidManager) | Flask + Docker SDK 管理面板、实例 CRUD、APK 分发 | 最容易读懂和改造的生命周期参考 | 外部 ADB 多实例映射有问题；克隆不复制数据；MIT | **适合拆解借鉴，不宜原样采用** |
| [ayasa520/redroid-script](https://github.com/ayasa520/redroid-script) | 改造 redroid 镜像，加入 Magisk 等组件 | 可重复制作带应用级 root 的镜像 | 不是管理系统；不同安卓版本须实测；脚本 MIT | **root 镜像参考首选** |
| [DeviceFarmer/stf](https://github.com/DeviceFarmer/stf) | Web 设备农场、远程操作、设备分配、REST API | 占用/归还、多人设备管理、远程 ADB | 主要管理已接入设备；不自动供应 redroid 容器；Apache-2.0 | **成熟设备管理参考** |
| [akwin1234/damru](https://github.com/akwin1234/damru) | Python SDK/CLI、设备池、Docker 自动模式、实验性 UI | 一任务一设备会话、健康恢复、代理配置 | 核心面向 Android 浏览器；非商业许可，商业用途另行许可 | **工作流模型相关度高** |
| [mattyperrott/Virtroid](https://github.com/mattyperrott/Virtroid) | Android 客户端、Go 控制面和节点、快照相关实现 | 状态协调、生命周期和恢复设计 | 以 Android 客户端为主；Web 操作台只读；未找到顶层许可证 | **架构参考，非即插即用组件** |
| [kasmtech/workspaces-images](https://github.com/kasmtech/workspaces-images) 的 redroid 镜像 | 浏览器可访问的 Android 桌面封装 | 快速人工体验和演示 | 官方标注实验性；DinD + scrcpy；整个 Kasm 产品不等于此仓库许可 | **可体验，集成较重** |
| [jimedrandatorg/reddock](https://github.com/jimedrandatorg/reddock) | Go 命令行管理工具 | Docker 生命周期、binder 检查 | 无管理网页、工作流调度；GPL-2.0 | **小型辅助参考** |

以上优先级是针对 AutoFlow 的适配判断，不是通用产品排名。各项功能与许可的依据见第 2–5 节。**最接近“直接启动后能操作安卓”的是 Webscreen + redroid；最接近“可读懂的创建管理后台”的是 RedroidManager；最接近“批量任务执行库”的是 Damru。** 这些定位不能互相替代。

## 2. 优先阅读的四个项目

### 2.1 Webscreen：现成的浏览器屏幕与交互层

Webscreen 仓库提供专门的 redroid 快速部署文档，Compose 中包含 Webscreen 服务和 redroid 服务；页面通过 PIN 进入，未自动发现设备时可以手动连接。项目还发布了 v1.3.5，包含 Windows、macOS、Linux 等平台二进制。**这是有部署配方和发布产物的项目，并非只有截图。**[^1][^2]

源代码中，`sdriver/scrcpy` 负责连接 ADB、启动和对接 scrcpy、传输控制事件；`streamAgent` 负责媒体传输；`webservice/android` 处理设备连接；`public/static` 包含网页输入逻辑。Go 侧使用 Pion WebRTC，存在 H.264/H.265 视频与 Opus 音频的处理路径，音频能力会依据 Android 编码支持调整。适合作为 AutoFlow 中“查看设备”和“手动接管”的参考。[^3]

它没有替 AutoFlow 完成实例供应：创建 Docker 容器、为任务分配设备、任务结束后清理数据、失败后回收，都属于另一层。Compose 示例也不代表已经有集群管理器。接入时还需要验证浏览器编解码支持、连接恢复、实际网络下的 WebRTC 连通性，以及运行端的 ADB 地址。

**许可为 AGPL-3.0。** 因此，“已有代码可研究”“按许可证条件集成”和“随意复制进闭源桌面产品”是不同判断；不能把它当作 MIT 组件处理。[^4]

**推荐：优先做独立服务式的技术验证，先确认画面与输入链路；是否直接引入源码，另行根据最终交付方式确定。置信度：组件存在与部署文档为高；AutoFlow 集成成本为中；延迟和并发容量未知。**

### 2.2 RedroidManager：最小的实例管理参考，但多开路径有实际缺陷

这个项目有实际 Flask 路由、Docker SDK 调用和 HTML 页面，范围包括创建、列出、启停、重启、删除、按参数克隆、APK 上传及批量安装、状态统计、截图和输入。主要实现集中在 `app.py`，依赖较少，很适合快速看懂从“点击创建”到“启动安卓容器”的完整路径。许可证是 MIT。[^5][^6]

源码检查发现下列问题，均针对本次固定版本：

| 位置 | 源码实际行为 | 对需求的影响 |
|---|---|---|
| `create_instance` 与 `clone_instance` | 将宿主端口和容器端口都设为分配出的 `adb_port`，而启动参数没有同步改变 adbd 监听端口 | 标准 redroid 默认 ADB 为 5555；第二个分配到 5556 的实例会映射成宿主 5556 → 容器 5556，外部 ADB 连错端口 |
| `clone_instance` | 用相同镜像/显示参数创建新的 `/data` 卷，没有复制原实例数据的流程 | “克隆”只相当于复制配置，不会带走已装 APK、登录态或应用数据 |
| `find_available_port` | 只扫描管理标签中的端口，未实现原子预留 | 并发创建存在竞争；外部进程占用也不在这一步检查 |
| `instance_screen` | 循环执行 `screencap -p`，通过 multipart 发送 PNG | 不是视频编码串流；成功路径未执行帧间休眠，不能把注释中的约 3 FPS 当成限帧保证 |
| APK 批量任务 | 进程内线程与任务状态 | 不等于有持久化、可恢复的工作流队列 |
| Flask 入口与对象操作 | 监听 `0.0.0.0` 且 `debug=True`；相关路由未见认证和管理对象归属限制 | 不适合原样作为正式共享管理入口 |

前三项和截图路径都能直接在源码中确认；端口问题的影响是结合 redroid 官方默认端口作出的静态推断。**这不等于第二个 Android 容器无法启动，也不等于它的 docker-exec 截图一定失败；出问题的是通过该端口映射访问 ADB。**[^6][^7]

还需注意，镜像未缓存时它返回错误并要求手动 `docker pull`，没有完成镜像下载任务系统；创建代码没有配置 CPU、内存配额。因而可借鉴容器标签、数据卷、显示参数、实例状态和操作按钮设计，但批量调度与资源约束需要另做。

**推荐：将它当作小型参考实现，沿用 AutoFlow 的 Python/FastAPI 边界重写必要部分，不再引入一个 Flask 管理后台。置信度：源码发现为高；修复后的运行质量未知。**

### 2.3 redroid-script：root 和定制镜像的实用入口

`ayasa520/redroid-script` 的目标是在不完整重编 AOSP 的情况下，为 redroid 镜像加入 Magisk、GApps、native bridge 等组件。`redroid.py` 是入口，`stuff/magisk.py` 实际处理 Magisk 相关安装和 Android init 集成。这比直接照搬针对传统模拟器 boot/ramdisk 的脚本更贴近容器式 Android。[^8][^9]

这里必须区分两层 root：redroid 官方提供的属性配置可以获得 root ADB shell；应用内部调用 `su`、Magisk 模块和相关启动逻辑，则属于镜像内的应用级 root 能力。前者不能直接替代后者。[^7][^9]

项目仍有近期默认分支提交，但 README 的版本示例主要列到 Android 13；不能据此自动推导所有 Android 14–16 镜像和所有模块均已兼容。近期更新只是维护信号，不是兼容性验证。脚本本身是 MIT，所下载的 Magisk、GApps 和二进制转译组件各有自己的来源和条款。[^8][^10]

**推荐：参考它建立版本固定的镜像制作流程，分别保留普通调试镜像与 Magisk 镜像。先在选定 Android 版本证明应用可获取所需权限，再扩展版本矩阵。置信度：镜像修改实现存在为高；具体组合兼容性未知。**

### 2.4 STF：现成设备农场，负责设备使用管理

DeviceFarmer STF 已有网页设备列表、远程控制、设备查找、用户/组及远程 ADB 功能，并提供 REST 接口。API 规格中可以找到 `/user/devices`、`/user/devices/{serial}` 和远程连接相关操作。这些适合研究工作流取得设备、占用期间防冲突、归还设备以及人工调试的交互和契约。[^11][^12]

STF 的核心对象是接入的 Android 设备。它不等于 Docker 供应器：如果要“任务来了创建 redroid，任务结束销毁”，仍需由外部生命周期服务实现容器创建和清理，然后将设备接入 STF。已有 Zebrunner mcloud-redroid 项目展示 redroid、Appium 与 STF 的组合，证明这种集成路线有公开先例，但该集成仓库已经归档。[^13]

STF 是本次候选中历史更长、设备农场功能更丰富的项目，实际 LICENSE 为 Apache-2.0；不能因为 GitHub API 的自动识别值为 `NOASSERTION` 就写成无许可证。它的依赖也比极简管理器重，README 对 Node.js 等运行条件有明确要求。已有设备控制链路对特定 Android 版本的兼容性仍需测试。[^11][^14]

**推荐：首先借鉴设备租约和 REST 契约；只有多人共享设备农场成为明确需求时，再判断是否部署完整 STF。第一版单用户桌面模块不必直接装入整个设备农场。置信度：项目能力与 API 为高；适配 AutoFlow 的部署取舍为中。**

## 3. 与批量工作流最接近的 Damru

Damru 有实际 Python 库、CLI 和 UI 服务代码。它支持 redroid 的 Docker 自动模式，因此虽然仓库还有 MuMu 模式，**使用 redroid 路线并不要求安装 MuMu**。核心定位是 Android Chrome/WebView 上的浏览器自动化，结合 Playwright/CDP；不能把其浏览器能力直接理解为任意原生 APK 的控件自动化能力。[^15][^16]

最有价值的是 `damru/pool.py`。这里不是只有一个循环启动脚本，而是已有 `DeviceSlot`、`DamruPool`、异步 session、批量 map、设备槽位获取/释放、任务超时监视、健康检查和异常恢复路径。`docker.py` 处理容器相关操作；`profiles.py`、`profile_apply.py` 和代理模块提供环境配置参考；UI 服务暴露 worker 管理及查看入口。[^16]

这对应 AutoFlow 需要的基本概念：工作流执行申请一个设备会话，获得设备连接信息，执行任务，在结束和异常路径归还设备。**可借鉴的是资源管理模型；若复制代码或作为运行时依赖，则必须遵守该项目自己的许可。**

它有三个关键限制：

1. **许可限制。** 仓库 LICENSE 标为 PolyForm Noncommercial 1.0.0，并列出项目附加条款；对商业、企业部署和托管服务等用途提供单独商业许可。因此它是公开源码项目，但不能按宽松许可开源依赖直接搬入 AutoFlow。[^18]
2. **平台与成熟度限制。** 自有状态文档把公开支持路径限定为 Ubuntu 24.04 和使用其配套内核的 Ubuntu 24.04 WSL2；UI 仍标注 experimental，也明确没有自己管理成千上万宿主节点的能力。镜像/APK 大文件在 Git 仓库之外，源码齐全不代表运行资产已经齐全。[^17]
3. **环境伪装效果边界。** 项目宣传和验证截图不能证明对全部风控 SDK 或原生 App 都有效。本次没有对任何具体检测系统复现其效果。环境属性存在修改代码，与定位、图形、传感器和完整性结果一致，是不同层次的证据。

**推荐：若第一批任务主要是 Android 浏览器，可将它列为专项验证候选；若目标是通用云手机模块，则借鉴设备池结构更合适。置信度：池与自动模式实现、许可和公开支持范围为高；目标站点/SDK 效果未知。**[^18]

## 4. 其他有价值的成品或半成品

### 4.1 Virtroid：有后端实质，但产品方向不同

Virtroid 有 Go 控制面、运行节点、Android 客户端和 Web 操作台。节点代码包含 Docker 健康探测、运行状态协调、媒体导入、数据持久化与快照相关路径；因此它不能归为“只有 README”。它适合研究创建、停止、恢复、清理以及控制面和运行节点之间的状态协作。[^19][^20]

作者将当前产品描述为单 VPS 的 release candidate，且网页操作台是只读观察界面，主要控制入口是 Android 客户端。多节点调度仍有未完成验收项。其摄像头能力明确是拍摄照片/视频后导入 guest，**不是把物理摄像头实时注入 Android Camera HAL**。这些“已部署”陈述来自作者，本次没有访问其在线系统作验证。[^19]

核查的树中未找到适用于项目整体的顶层许可证；存在第三方文件的许可不能替代整个项目的授权。可以研究架构，不能默认获得整体复制和再分发许可。对 AutoFlow 而言，值得读，但不是优先直接接入的系统。置信度：源码与 README 所述边界为高；部署质量未知。

### 4.2 Kasm redroid：可以体验的打包方案

Kasm 的镜像仓库包含 redroid Dockerfile、启动脚本和单独文档。其方式是 Docker-in-Docker 启动 redroid，再启动 scrcpy，将桌面通过浏览器提供给使用者；宿主仍要具备 binder 支持，镜像文档明确标注实验性。[^21]

它可以减少搭建一个人工操作演示环境的步骤，但 AutoFlow 若只需要 Android 画面和输入，整套桌面串流通常引入更多层次。Docker-in-Docker 也不免除底层 Linux 内核要求。仓库许可证正文采用 MIT 条款，同时明确只覆盖该仓库直接维护的代码，不能推导整个 Kasm Workspaces 产品或全部镜像依赖均为 MIT。[^22]

### 4.3 Reddock 与 RK3588 方案

Reddock 是小型 Go CLI，具有 Docker 容器与数据卷生命周期、ADB 和 binder 环境检查等实现。可读它的 `pkg/container` 和 `pkg/sysinfo/binder.go`，但它没有现成 Web 管理层，不能直接解决桌面内多设备操作。许可证为 GPL-2.0。[^23]

`CNflysky/redroid-rk3588` 是针对 RK3588 的专用运行方案，适合已有对应 ARM 板卡的部署选型；它不是通用宿主机的集群管理系统。若 AutoFlow 后续明确走 ARM 硬件设备池，这类镜像和宿主适配才进入重点。[^24]

## 5. 不应当误判成完整系统的项目

### 5.1 Hydra：架构描述领先于公开实现

`SakuraPuare/Hydra` 的 README 描述了 Go/Gin、React/Ant Design、PostgreSQL、监控等完整平台，并给出根目录 `make dev` 的启动路径。但固定 commit 的公开文件树主要由镜像构建、redroid Compose、配置和文档组成，没有对应的 `cmd`、`internal`、`web`、`go.mod` 或根目录 Makefile。`redroid-builder/Makefile` 的存在并不能满足根目录启动指令。[^25]

**结论：可以参考镜像构建材料，不能当作已公开交付的完整控制平台。** README 提到 MIT，但树中没有相应 LICENSE 文件，不能仅依据 README 的一句话判断具体授权文本。置信度：公开代码与启动文档不一致为高；是否有未公开实现未知。

### 5.2 redroid-cpp：部分关键接口仅返回成功

`mostakimnasim5/redroid-cpp` 有 C++/Qt 源码、测试目录和较丰富的模块命名，但 `APIServer.cpp` 中的 `updateProfile`、`deleteProfile`、`setAccelerometer` 会忽略输入并直接返回成功，未执行名称所表示的更新或传感器操作。`getProfile` 则返回有限的预设设备模板。[^26]

这不意味着所有功能都是空壳；它意味着**不能根据 REST 接口数量、模块名称或自我评分，将它认定为环境配置和传感器功能已经完成的系统**。GPS 接口写属性也不足以单独证明应用定位 API 已收到对应坐标，仍要跟踪实际数据消费路径。该项目 LICENSE 为 Apache-2.0，但当前能力完整性不适合作为首选依据。

### 5.3 yimi-cloud-phone：前端与后端没有闭合

`a782987770/yimi-cloud-phone` 的公开树只有 README、Compose、Nginx 配置、部署脚本和网页。前端调用创建、启停和 APK 安装 API，但树中没有实现这些业务接口的后端服务；现有容器清单也没有补足这些自定义 API。**可参考页面想法，无法仅凭公开仓库认定一个完整云手机管理系统已经交付。**[^27]

### 5.4 vphone-rental-crm：是真的 CRM，但底层不是公开的通用 redroid 管理器

`thanhrohan1/vphone-rental-crm` 有实际 Node 服务、SQLite 存储、管理员/客户页面、租用权限、设备同步与代理控制。问题在于它调用已有 VPhone 管理 API；README 明确区分 CRM 源码和未在此公开的虚拟化服务端。其主机地址及 8080 API 依赖在 `src/vphone-client.js` 中也可找到。[^28]

因此它适合研究设备列表、多主机分组、租用权限和客户门户，但不能删除厂商后端后直接管理原版 redroid。README 中每 box 同时 live 的数量限制来自这套产品逻辑，不能外推成 redroid 的并发上限。核查版本未找到顶层许可证。

### 5.5 Zebrunner mcloud-redroid：历史集成参考

它提供 redroid、Appium、STF 组合的部署材料，但 GitHub 显示已于 **2026-08-22** 归档。适合读清楚设备发现、ADB 和 Appium 的接线方式；新项目不宜把无人维护的集成脚本当成长期基础。默认示例还连接项目演示 STF，部署自有环境时不能不加区分照用其默认配置。[^13]

## 6. 对原始能力要求的逐项回答

| 要求 | 现有可利用部分 | 尚需证明或自行实现的部分 |
|---|---|---|
| 创建并管理 Android | redroid 容器运行时；RedroidManager 生命周期；Virtroid 状态协调 | 固定镜像、下载进度、启动就绪判断、状态持久化、失败恢复 |
| 批量运行 | Docker 多容器；Damru 设备池；STF 设备分配 | 有界并发、原子分配、任务取消、冷启动与热池、配额、故障回收 |
| 每任务独立数据 | redroid 的独立 `/data`；镜像作为共同基础 | 清洁基线、真实快照恢复、跨任务残留检查；参数克隆不算数据克隆 |
| root | 官方 root ADB 路径；redroid-script 的 Magisk 镜像流程 | 应用内 `su`、模块加载、重启后稳定性及版本兼容 |
| 位置与网络环境 | 官方 DNS/代理配置；Damru 的环境与代理模块 | 目标应用实际看到的坐标、DNS/出口一致性、原生网络与浏览器的差异 |
| 厂商与设备属性 | 官方可覆写调试属性；环境 profile 相关代码 | 属性间一致性、native API 读数、图形能力、传感器与系统服务行为 |
| 设备指纹/反检测 | 有配置和研究工具 | 无证据支持“对所有 SDK 不可检测”；硬件证明不能由字符串模板替代 |
| 宿主机实时摄像头 | 本次候选中没有验证到开箱即用的完整方案 | 摄像头采集→传输→Android Camera HAL/Provider→Camera2 应用端整条链路 |
| 跨 Windows/macOS 使用 | 控制端可以运行在桌面，Android 运行在合适 Linux 节点 | 本地虚拟机/WSL 所需内核、GPU、网络、设备通道；不是安装 Docker Desktop 即可保证 |

表中的已存在能力分别依据 redroid 官方文档及前述项目源码；未验证能力刻意保留为未知，不用 README 的“支持”代替运行验收。[^7][^16][^19]

### 6.1 批量运行的核心是分配与回收

红色/绿色状态卡片和“批量启动”按钮只覆盖前台操作。对于工作流，一个设备从创建到可执行任务，应至少经历就绪确认、独占分配、执行、归还和必要清理。容器处于 running 不代表 Android 启动完成，Android 启动完成也不代表目标应用可用。

合理的第一版可以只做单个 Linux 运行节点和固定数量的设备池，不必起步就做 Kubernetes 或多地域调度。优先证明两个并发任务不会拿到同一设备，任务异常时资源能够归还，下一次任务读不到上次不应保留的数据。这是基于 AutoFlow 需求的工程建议，而非任何候选已经通过的测试。

### 6.2 环境配置和检测结果应分开记录

“改了厂商信息”只证明某个配置层被修改；“目标应用读到预期值”证明该读取路径生效；“风控测试得到预期结果”还涉及其他信号和服务端判断。三者应保留独立证据。

建议将环境测试结果记录为：配置版本、镜像 digest、Android 版本、应用版本、预期观测值、应用内实际观测值、测试时间和结果。这样可以比较不同环境，而不把成功执行一条属性写入命令误记为完整伪装成功。root 适合调试与观测，但不能同时充当“与未修改实体机完全等价”的证明。

### 6.3 实时摄像头是当前选型中最大的明确缺口

必须分清三个方向：向 Android 上传照片；把 Android 摄像头画面输出到桌面；把桌面物理摄像头作为 Android 应用可打开的摄像头。原始需求对应第三项。Webscreen 的屏幕视频、Virtroid 的媒体导入、Kasm 的远程桌面通道，都不能自行证明第三项成立。[^3][^19][^21]

如果摄像头是首版硬性验收项，应先独立验证 Camera2 应用能看到持续实时帧，再扩展管理页面与批量系统。只把 `/dev/video0` 暴露给容器，不足以证明 Android Camera Provider 已经识别并提供该设备；本次没有找到可据此承诺即插即用的候选实现。这里的结论是“未找到/未验证”，不是断言 redroid 永远无法实现。

## 7. AutoFlow 的建议借鉴路线

**建议采用 redroid 运行节点 + AutoFlow 原有管理界面的路线。** redroid 官方支持在 Linux 上启动多个实例；AutoFlow 当前目标是 Windows/macOS 桌面，因此让桌面连接一个具备适配内核的 Linux 节点，是明确且易于分段验证的起点。第一轮不承诺 Windows/macOS 上本地 Docker 一键运行。[^7]

这只是待验证方案，先前 Android 运行时比较中的其他选项并未因此被正式淘汰。

| 子能力 | 优先参考 | 建议处理方式 |
|---|---|---|
| Docker 创建、标签、数据卷、显示参数 | RedroidManager `app.py` | 参考后用现有 Python provider 边界实现，修复端口和并发分配 |
| 屏幕查看和输入 | Webscreen `sdriver/scrcpy`、`streamAgent`、网页输入层 | 先验证独立运行的连接方式，再决定源码整合 |
| Magisk 镜像制作 | redroid-script `redroid.py`、`stuff/magisk.py` | 生成固定版本镜像，记录构建输入与产物 digest |
| 工作流设备会话 | Damru `damru/pool.py`；STF 设备 API | 参考职责与接口语义；源码复用按各自许可处理 |
| 节点状态协调与恢复 | Virtroid Go 节点和快照模块 | 研究状态机，不在首版照搬完整控制面 |
| 多人设备门户 | STF；VPhone CRM 页面 | 明确多人共享需求后再进入实现 |

**不建议第一版同时引入 Flask 管理器、STF、Kasm、Damru 和独立 Go 控制平台。** 它们会重复拥有实例状态、用户权限和设备连接，增加集成成本。先以 AutoFlow 为任务和配置的唯一入口，选择一个实际需要的显示组件；其余项目作为针对性源码和设计参考。

## 8. 最小验证计划与通过标准

以下是建议实施前的专项验证清单，尚未执行。并发数量是试验阶梯，不是性能承诺。

1. **单实例基线：** 在选定 Linux 节点启动固定版本 redroid；确认 ADB、系统启动完成、目标 APK 安装与启动、停止后数据保留。
2. **多实例正确性：** 从 2 个实例开始，确认外部端口均指向各自容器的 5555，卷不串用、输入不串设备；再按宿主实际资源提高数量。
3. **浏览器控制：** 用 Webscreen 验证点按、拖动、文本输入、分辨率变化、断线重连；记录端到端延迟与观看时资源消耗。
4. **任务租约：** 让任务超时、取消并模拟节点连接中断；确认设备归属和任务状态一致，没有静默重复分配。
5. **root 镜像：** 分别测试 root ADB 和应用 `su`，验证需要的模块，以及重建和重启后的行为。
6. **环境用例：** 由目标应用或自有探针读取位置、网络出口和相关设备信息，保留实际值与预期值，避免只检查配置文件。
7. **摄像头专项：** Android 测试应用通过 Camera2 打开摄像头，看到实时运动并可持续采集；媒体导入不算通过。
8. **密度评估：** 分别记录空闲、任务执行、屏幕观看的 CPU、内存、GPU、磁盘和启动时间，确定每节点的实测容量。

**决定是否采用 redroid 的关键，是第 2、5、6、7 项与目标 APK 的兼容结果。** 没有宿主硬件与应用负载数据，目前不给“单机几十/几百开”的数字。

## 9. 版本、证据与剩余不确定性

| 项目 | 本次固定 commit（短） | 默认分支最新提交时间 UTC | Release 观察 |
|---|---|---|---|
| RedroidManager | `853b786b2943` | 2026-08-14 | 查询未见 Release |
| Webscreen | `2961169f863f` | 2026-05-28 | v1.3.5，2026-05-25 |
| redroid-script | `a4951b782fc8` | 2026-09-12 | 查询未见 Release |
| STF | `1d321cb3e72d` | 2026-09-12 | v3.7.9，2026-07-08 |
| Damru | `56988fc8067e` | 2026-07-05 | v0.1.0-beta，2026-06-04 |
| Virtroid | `3bfee99e1fdf` | 2026-09-08 | 查询未见 Release |
| Hydra | `fca0db7e5a32` | 2026-08-03 | 查询未见 Release |
| redroid-cpp | `75b3a0fe7ac5` | 2026-09-10 | 查询未见 Release |

日期来自 GitHub 默认分支 commit 与 Release API，而非将仓库 `pushed_at` 当作代码更新时间。完整固定版本、来源 URL 和静态检查结果保存在同目录的 [evidence.json](evidence.json)。提交新不代表系统成熟；发行标签也不是独立质量认证。

已核实：主要仓库的公开文件树、关键源码路径、部署文档、许可证文本以及上述版本信息。没有执行候选的安装脚本、镜像构建、真实 Android 启动或压力测试。因此，源码存在性和明确缺失项可信度高，实际部署成功率、性能、ARM-only 应用兼容性、摄像头及检测效果仍未知。

进一步检索不太可能改变当前组件分工判断；下一步最有价值的是按第 8 节完成有限范围的运行验证，而不是继续按功能宣传收集更多仓库。

## 来源

以下均为项目维护者发布的第一手材料。固定 commit 链接标识核查版本；未单列发布日期的文档以该版本为准，访问日期均为 2026-09-13。

[^1]: huonwe，Webscreen，[redroid 快速部署文档](https://github.com/huonwe/webscreen/blob/2961169f863f1f00bbeba6bc77e86742607f8914/doc/quick-start-redroid.md)。
[^2]: huonwe，[Webscreen v1.3.5 Release](https://github.com/huonwe/webscreen/releases/tag/v1.3.5)，2026-05-25。
[^3]: huonwe，Webscreen，[scrcpy 驱动](https://github.com/huonwe/webscreen/blob/2961169f863f1f00bbeba6bc77e86742607f8914/sdriver/scrcpy/driver.go)、[媒体串流](https://github.com/huonwe/webscreen/blob/2961169f863f1f00bbeba6bc77e86742607f8914/streamAgent/streaming.go)、[固定版本文件树](https://github.com/huonwe/webscreen/tree/2961169f863f1f00bbeba6bc77e86742607f8914)。
[^4]: huonwe，Webscreen，[LICENSE](https://github.com/huonwe/webscreen/blob/2961169f863f1f00bbeba6bc77e86742607f8914/LICENSE)。
[^5]: JinHisAndy，RedroidManager，[README](https://github.com/JinHisAndy/RedroidManager/blob/853b786b29430886ae8db58eb2d9e3432e0c8684/README.md)、[LICENSE](https://github.com/JinHisAndy/RedroidManager/blob/853b786b29430886ae8db58eb2d9e3432e0c8684/LICENSE)。
[^6]: JinHisAndy，RedroidManager，[app.py](https://github.com/JinHisAndy/RedroidManager/blob/853b786b29430886ae8db58eb2d9e3432e0c8684/app.py)，创建/克隆/截图/服务入口实现。
[^7]: remote-android，[redroid 官方文档](https://github.com/remote-android/redroid-doc)，Linux 运行、默认 ADB 5555、数据与环境配置、root 调试属性。
[^8]: ayasa520，redroid-script，[README](https://github.com/ayasa520/redroid-script/blob/a4951b782fc8e06c845d9553bf07bb643fd8c158/README.md)、[镜像脚本入口](https://github.com/ayasa520/redroid-script/blob/a4951b782fc8e06c845d9553bf07bb643fd8c158/redroid.py)。
[^9]: ayasa520，redroid-script，[Magisk 安装实现](https://github.com/ayasa520/redroid-script/blob/a4951b782fc8e06c845d9553bf07bb643fd8c158/stuff/magisk.py)。
[^10]: ayasa520，redroid-script，[LICENSE](https://github.com/ayasa520/redroid-script/blob/a4951b782fc8e06c845d9553bf07bb643fd8c158/LICENSE)。
[^11]: DeviceFarmer，STF，[README](https://github.com/DeviceFarmer/stf/blob/1d321cb3e72d90abd817ead5b003860dcbcd831c/README.md)。
[^12]: DeviceFarmer，STF，[API v1 Swagger 规格](https://github.com/DeviceFarmer/stf/blob/1d321cb3e72d90abd817ead5b003860dcbcd831c/lib/units/api/swagger/api_v1.yaml)。
[^13]: Zebrunner，[mcloud-redroid 仓库与部署说明](https://github.com/zebrunner/mcloud-redroid)，GitHub 归档标记日期 2026-08-22。
[^14]: DeviceFarmer，STF，[LICENSE](https://github.com/DeviceFarmer/stf/blob/1d321cb3e72d90abd817ead5b003860dcbcd831c/LICENSE)。
[^15]: akwin1234，Damru，[README](https://github.com/akwin1234/damru/blob/56988fc8067e8e51cc6f362662b5fd5762522af1/README.md)。
[^16]: akwin1234，Damru，[设备池实现](https://github.com/akwin1234/damru/blob/56988fc8067e8e51cc6f362662b5fd5762522af1/damru/pool.py)、[固定版本文件树](https://github.com/akwin1234/damru/tree/56988fc8067e8e51cc6f362662b5fd5762522af1)。
[^17]: akwin1234，Damru，[Automation Status and Roadmap](https://github.com/akwin1234/damru/blob/56988fc8067e8e51cc6f362662b5fd5762522af1/docs/AUTOMATION_GAPS_PLAN.md)，文档自述复审日期 2026-06-05。
[^18]: akwin1234，Damru，[LICENSE](https://github.com/akwin1234/damru/blob/56988fc8067e8e51cc6f362662b5fd5762522af1/LICENSE)、[LEGAL.md](https://github.com/akwin1234/damru/blob/56988fc8067e8e51cc6f362662b5fd5762522af1/LEGAL.md)。
[^19]: mattyperrott，Virtroid，[README](https://github.com/mattyperrott/Virtroid/blob/3bfee99e1fdf8b484c7e48613061e4bc5c7bac5f/README.md)。
[^20]: mattyperrott，Virtroid，[运行节点](https://github.com/mattyperrott/Virtroid/blob/3bfee99e1fdf8b484c7e48613061e4bc5c7bac5f/backend/cmd/virtnoded/main.go)、[文件树](https://github.com/mattyperrott/Virtroid/tree/3bfee99e1fdf8b484c7e48613061e4bc5c7bac5f)。
[^21]: Kasm Technologies，[redroid 镜像说明](https://github.com/kasmtech/workspaces-images/blob/bafab6d531eefd5a5aa6f2c9088ebc8f02e12fae/docs/redroid/README.md)、[启动脚本](https://github.com/kasmtech/workspaces-images/blob/bafab6d531eefd5a5aa6f2c9088ebc8f02e12fae/src/ubuntu/install/redroid/custom_startup.sh)。
[^22]: Kasm Technologies，workspaces-images，[LICENSE.md](https://github.com/kasmtech/workspaces-images/blob/bafab6d531eefd5a5aa6f2c9088ebc8f02e12fae/LICENSE.md)。
[^23]: jimedrandatorg，Reddock，[README](https://github.com/jimedrandatorg/reddock/blob/843382fc4bf54470e80a1fcfc82256a03c7de418/README.md)、[源文件树](https://github.com/jimedrandatorg/reddock/tree/843382fc4bf54470e80a1fcfc82256a03c7de418)、[LICENSE](https://github.com/jimedrandatorg/reddock/blob/843382fc4bf54470e80a1fcfc82256a03c7de418/LICENSE)。
[^24]: CNflysky，redroid-rk3588，[README](https://github.com/CNflysky/redroid-rk3588/blob/c742a34f3d65df479214a10d4e9375c57c95b52f/README.md)。
[^25]: SakuraPuare，Hydra，[README](https://github.com/SakuraPuare/Hydra/blob/fca0db7e5a32f112e7e83ca729b3291900b6d624/README.md)、[实际公开文件树](https://github.com/SakuraPuare/Hydra/tree/fca0db7e5a32f112e7e83ca729b3291900b6d624)。
[^26]: mostakimnasim5，redroid-cpp，[APIServer.cpp](https://github.com/mostakimnasim5/redroid-cpp/blob/75b3a0fe7ac529a670dd1e9108bc98a0daf1c5bf/src/ReDroidController/APIServer.cpp)、[LICENSE](https://github.com/mostakimnasim5/redroid-cpp/blob/75b3a0fe7ac529a670dd1e9108bc98a0daf1c5bf/LICENSE)。
[^27]: a782987770，yimi-cloud-phone，[公开文件树](https://github.com/a782987770/yimi-cloud-phone/tree/fbdb90a56a1621e68646d033f896acef55d74558)、[网页实现](https://github.com/a782987770/yimi-cloud-phone/blob/fbdb90a56a1621e68646d033f896acef55d74558/web/index.html)、[Compose](https://github.com/a782987770/yimi-cloud-phone/blob/fbdb90a56a1621e68646d033f896acef55d74558/docker-compose.yml)。
[^28]: thanhrohan1，vphone-rental-crm，[README](https://github.com/thanhrohan1/vphone-rental-crm/blob/c09e0e895abf5be99f3e112d7585811cc45cf75c/README.md)、[VPhone API 客户端](https://github.com/thanhrohan1/vphone-rental-crm/blob/c09e0e895abf5be99f3e112d7585811cc45cf75c/src/vphone-client.js)。
