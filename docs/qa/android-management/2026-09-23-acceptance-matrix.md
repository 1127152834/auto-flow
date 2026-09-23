# 安卓模拟器管理 24 项验收校准

- 日期：2026-09-23；状态：`partial`；来源：[需求规格第 8 节](../../superpowers/specs/2026-09-19-android-emulator-management-design.md)与本目录实际测试/真机记录。
- 基线：隔离分支 `codex/android-management-complete`。`passed` 仅表示该验收项已有相应自动化或真实证据；`partial` 表示实现/证据尚未覆盖完整场景；`blocked` 仅用于明确缺少外部条件。自动化、真实 Mac 和网络/账号证据分别列出，不互相代替。

| 验收 | 状态 | 已有证据与缺口 |
| --- | --- | --- |
| AM-AC01 | `partial` | Android 管理页已停止旧设备列表和详情 `/runs` 轮询，移除退役分配/运行记录入口；[详情测试](2026-09-23-control-session-verification.md)覆盖受控顶栏导航，其他模块及完整真机 UI 链未专项验收。 |
| AM-AC02 | `passed`（自动化） | 环境缺失/超时/不支持的只读契约测试；真实 Mac 环境 `available=true`，见 [AM1](am1-verification.md)。 |
| AM-AC03 | `passed`（自动化） | 状态规则和前端状态测试覆盖 stop/delete/recover/unknown，见 [AM1](am1-verification.md)。 |
| AM-AC04 | `passed`（自动化） | 持久操作幂等、冲突、generation、紧凑回执与同事务设备投影测试，见 [AM1](am1-verification.md)。 |
| AM-AC05 | `partial` | [本轮 RED→GREEN](2026-09-23-control-session-verification.md)覆盖迟到会话、旧输入、结束未知守卫、服务端回收后双重核实；打开→输入→返回→再输入与 30 秒失联的真实链未验收。 |
| AM-AC06 | `partial` | 手动/只读原生 scrcpy 窗口进程保持存活、关闭不停止 Android，见 [原生窗口实测](2026-09-23-persistent-metadata-verification.md)；列表归属、显式结束与第二台不隐式结束已有前端自动化，切换写端未实测。 |
| AM-AC07 | `passed`（自动化） | 旧 generation、重复 sequence、跨工作区 heartbeat 拒绝测试，见 [AM1](am1-verification.md)。 |
| AM-AC08 | `partial` | 真实停止/启动和新卷恢复数据读回成功；完整保留卷恢复与缺卷错误路径尚需同链验收。 |
| AM-AC09 | `partial` | 双实例不同 ADB serial、真实自建资源标签清理及丢响应 `needs_verification` 证据存在；同场景删除一台仍保留另一台和外部卷的完整真机链未验收。 |
| AM-AC10 | `partial` | 默认单台、模板与空态前端自动化；长名称、200% 缩放、断线旧数据及键盘焦点未专项验收。 |
| AM-AC11 | `partial` | tag 漂移/固定 imageId/引用阻删集成通过；网络拉取和真实内容删除未验收，见 [AM2](am2-verification.md)。 |
| AM-AC12 | `passed`（自动化） | 模板 revision 冲突及已有实例配置快照不变集成，见 [AM2](am2-verification.md)。 |
| AM-AC13 | `passed`（自动化） | 谷歌组件检测与验证状态分离，缺项不报通过；见 [GApps](gapps-validation.md)。 |
| AM-AC14 | `blocked` | 无专用候选镜像、测试账号和商店下载链；登录/下载/重启/隔离均 `not_tested`，见 [GApps](gapps-validation.md)。 |
| AM-AC15 | `partial` | 批次部分失败/取消/重试规则与 UI 自动化存在；真实多实例批次未演练，见 [AM3](am3-verification.md)。 |
| AM-AC16 | `passed`（自动化及真实容量实验） | 持久预留、未知预算拒绝、stop 丢响应后核实释放，见 [容量实测](2026-09-23-capacity-verification.md)。 |
| AM-AC17 | `partial` | 聚合快照、陈旧规则及可见预览自动化通过；1/5/10 台延迟、前台/内存指标未实测。 |
| AM-AC18 | `partial` | APK 大小/Manifest/split、未知结果和保护包自动化；无真实测试 APK，卸载/清数据真机未演练。 |
| AM-AC19 | `partial` | 运行中备份拒绝与原子发布自动化、真实停机备份成功；磁盘不足、取消、权限和硬中断未完整验收。 |
| AM-AC20 | `partial` | [最终真实恢复](2026-09-23-persistent-metadata-verification.md)覆盖新 ID/卷、1792 持久条目及启动读回；损坏包/镜像不符/越界拒绝为自动化，硬中断未实测。 |
| AM-AC21 | `passed`（自动化及真实清理） | 预览后指纹/引用变化 409、外部路径/标签保护及真实 HTTP 清理，见 [清理验收](2026-09-23-cleanup-verification.md)。 |
| AM-AC22 | `passed`（默认导出） | 默认诊断字段白名单排除输入、账号、原始日志、截图和数据；受限 IPC 本地保存且无自动上传，见 [后端增量](2026-09-23-validation.md)。高级日志单次同意/限时限量仍属 T19 缺口。 |
| AM-AC23 | `passed`（代码与迁移门槛） | Alembic 唯一 head `am01_management_operations`，未改旧迁移字节；[全量后端与构建门槛](2026-09-23-full-gates.md)通过。 |
| AM-AC24 | `partial` | 四阶段 QA 与真机/自动化/外部条件分列；完整场景、全分支最终审查和剩余失败矩阵未完成。 |

当前软件缺口是 T05/T06/T07 的完整交互链、T13/T14/T16 规模与性能、T17/T19/T20 的磁盘/硬中断/APK 临时文件/高级日志及完整失败矩阵。外部阻塞主要为 AM-AC14 的专用谷歌镜像与账号/网络条件；测试 APK 缺失只影响相应真机验收，不阻止其他软件工作。真实备份与恢复实验只清理本轮自建资源，已有外部卷和实例不纳入删除范围。
