# 第三方来源与改动

- 日期：2026-09-13。
- 状态：实现来源已登记；运行验证以 `VERIFICATION.md` 为准。
- 原始参考仓库保留独立 Git 信息，本 Demo 不修改其源码。

## RedroidManager

- 来源：[JinHisAndy/RedroidManager](https://github.com/JinHisAndy/RedroidManager)。
- 固定 commit：`853b786b29430886ae8db58eb2d9e3432e0c8684`。
- 许可：MIT；原文保存在 [RedroidManager-LICENSE.txt](licenses/RedroidManager-LICENSE.txt)。
- 原作者版权声明保留在许可文件中；后端文件头标明来源版本和改编范围。管理镜像包含本说明和两份原始许可。

| 来源文件与职责 | Demo 目标 | 复用与修改 |
|---|---|---|
| `app.py`：Docker SDK 列表、创建/启停、command/volume、getprop | `backend/app.py` | 复制并改编核心操作；新增实例归属、输入校验、资源配额、就绪状态、动态宿主端口、失败处理 |
| `app.py`：APK 的 tar/put_archive/pm install 流程 | `backend/app.py` | 保留传输安装方式；唯一文件 ID、边界校验、真实退出状态、安装临时文件清理；删除自写 AXML 包名推断 |
| `app.py`：screencap 与 input 调用 | `backend/app.py` | 保留 Android 命令路径；单帧 PNG、实际尺寸、有限执行、互斥与超时处理 |
| `app.py`：批量任务 ID/状态查询 | `backend/app.py` | 保留行为组织，重新实现有界任务执行与每设备占用 |
| `templates/index.html`：列表、创建、APK、屏幕交互 | `frontend/src/` | 作为功能和交互参考，重新编写 React 组件；未整页复制原 HTML/CSS/DOM 字符串实现 |

本 Demo 没有复制其“截图流就是 MJPEG 视频”“克隆会复制数据”等不成立的推断。配置副本明确使用新数据卷；截图作为单帧使用。

## redroid-script

- 来源：[ayasa520/redroid-script](https://github.com/ayasa520/redroid-script)。
- 固定 commit：`a4951b782fc8e06c845d9553bf07bb643fd8c158`。
- 许可：MIT；原文保存在 [redroid-script-LICENSE.txt](licenses/redroid-script-LICENSE.txt)。
- 构建入口使用相邻参考仓库的固定版本，在临时副本中运行。脚本的生成文件、提取文件和缓存均放在构建临时区。
- 必要补丁限定在临时副本：构建退出码/产物校验、下载与执行边界、临时路径隔离。补丁实现和实际构建记录可在构建脚本及其输出中核查。
- 使用的 Magisk 下载地址来自该固定版本 `stuff/magisk.py`，为作者维护的 fork；不声称它就是官方 Magisk 的原封不动发行版。

## Docker 镜像与其他依赖

- 基础 Android 来自 `redroid/redroid`；记录实际运行或构建使用的 image ID/digest，浮动 tag 不作为精确版本证据。
- 构建依赖 Node、Python、Flask、Docker SDK、Waitress、React、Vite 等，实际版本见各子工程锁定文件和镜像配置。
- 两份 MIT 许可只覆盖相应脚本/源码，不替代 Android 镜像、Magisk 或其他下载组件自己的许可。
- 本 Demo 不附带第三方测试 APK、Magisk APK、Google 服务或 ARM 转译二进制。
