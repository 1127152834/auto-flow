# redroid 管理系统生态调研

- 日期：2026-09-13
- 状态：confirmed（公开源码/文档事实）；proposed（选型与实施建议）
- 范围：为 AutoFlow 寻找现成 redroid 管理、网页控制、批量任务和 root 镜像工具；未修改业务代码。
- 完整报告：[redroid 现成管理系统与源码借鉴研究](../../docs/references/redroid-research-2026-09-13/README.md)
- 来源与固定版本：[evidence.json](../../docs/references/redroid-research-2026-09-13/evidence.json)；报告内提供逐项原始链接。

## 可复用结论

1. Webscreen 有 redroid Compose 和网页控制代码，适合显示/输入层；不是容器供应器；AGPL-3.0。
2. RedroidManager 为 MIT、Flask + Docker SDK 小型面板；固定版本创建和克隆把宿主 ADB 端口同时当成容器端口，标准多实例外部 ADB 路径有错；克隆不复制 userdata。
3. redroid-script 可参考容器镜像内 Magisk 集成；不能推导全部 Android 版本/模块已兼容。
4. STF 有设备分配和 REST API，LICENSE 实为 Apache-2.0；redroid 生命周期仍要另行供应。
5. Damru 有实际 Python 设备池、Docker 自动模式和实验性 UI，核心为 Android 浏览器；LICENSE 为非商业许可及项目条款，商业用途另行许可。
6. Hydra 的 README 平台描述与公开文件树不一致；yimi-cloud-phone 缺少前端调用的管理后端；redroid-cpp 部分 API 忽略参数直接报成功。
7. Virtroid 有实际 Go 后端，但主控制端为 Android 客户端、Web 台只读；相机为媒体导入而非实时 Camera HAL 输入；未找到顶层许可证。
8. 本次未找到经独立验证、同时满足完整批量生命周期和实时宿主摄像头的现成一体化系统。不能把未找到写成无法实现。

## 建议与验证边界

- proposed：优先验证 redroid Linux 节点 + AutoFlow 原管理界面 + Webscreen；参考 RedroidManager 生命周期、redroid-script 镜像、Damru/STF 设备租约概念。不是架构批准。
- confirmed：已核对仓库元数据、文件树、关键实现、许可证和四项静态断言；没有运行候选安装脚本、拉取系统镜像、启动 Android 或压测。
- unknown：实际并发容量、目标 APK/风控 SDK 的兼容结果、实时摄像头、各 Magisk/Android 组合。
- 上一轮背景：[Android 运行时比较](2026-09-12-android-runtime-options.md)。
