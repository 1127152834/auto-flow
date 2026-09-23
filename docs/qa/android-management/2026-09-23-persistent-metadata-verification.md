# 原生窗口、恢复归属与持久数据属性增量验收

- 日期：2026-09-23；状态：`confirmed`（本增量），AM1–AM4 总目标仍 `partial`。
- 来源：规格 T05/T17/T18/T20、恢复增量独立审查、隔离工作区 `codex/android-management-complete` 上的测试与真实 Apple Silicon Mac / Lima / ReDroid 演练。
- 原始结果：[原生窗口](2026-09-23-native-window-result.json)、[Docker 属性探测](2026-09-23-xattr-probe-result.json)、[安卓卷属性清单](2026-09-23-xattr-inventory-result.json)、[客体 tar 属性往返](2026-09-23-gnu-tar-xattr-result.json)、[客体根目录与链接往返](2026-09-23-gnu-tar-root-links-result.json)、[最终恢复演练](2026-09-23-restore-rootfixed-result.json)。对应同名前缀的 `-smoke.txt` 是执行时 `/tmp` Python 脚本的逐字副本；`shasum -a 256` 对应相同，最终演练脚本为 `7b7fe712577985a770a66c314f64218241dd609df72cec3e418c2560f9a9231f`。早一轮[持久数据演练](2026-09-23-restore-persistent-result.json)在修复卷根目录映射之前执行，保留为历史证据，不计入最终实现验收。

独立审查发现旧的恢复写卷只信任传入设备快照。现在持有运行时锁时，从同一数据库会话再次核对持久设备与 `running` 恢复操作：工作区、目标 ID、请求/备份/操作归属、generation、卷、镜像、配置、未删除、停机和控制空闲；缺失操作仓储时拒绝写卷。完成时原有原子 CAS 仍保留。RED：7 个持久归属/失败后重试用例失败；GREEN：定向恢复测试 51 passed，最终 AM4 属性、路径隐私与恢复联合测试 118 passed、1 warning，`uv run ruff check src tests` 为 `All checks passed!`。[完整门槛](2026-09-23-full-gates.md)后端 3964 passed、26 skipped。

真实 Docker `cp` 探测中，源文件 `user.autoflow_probe=metadata`，导出的 tar `archivePax={}`。真实 ReDroid 停机卷有 1794 个条目，属性包括 `user.*` 与 `system.posix_acl_*`；因此“遇到属性即拒绝”的保护会挡住正常备份，已由客体侧 GNU tar `--xattrs --xattrs-include=* --acls --selinux --numeric-owner` 代替。恢复只向经标签核实的空目标卷解包，GNU tar 最小实测保留 `user.autoflow_probe` 和 mode 0640。`--selinux` 已启用，但本机没有可验证的 SELinux 标签，不能宣称标签往返已实测。旧 Docker 归档已丢失的属性无法事后补回。

审查还发现旧的 `--strip-components=1` 丢失数据卷根目录 UID/GID、权限和属性。RED 客体实验证明 UID 10001/GID 2000/mode 0750/`user.autoflow_root` 在旧命令后变成 root/root/0755/无属性；改成 `data` 与 `_data` 路径变换后，客体 GREEN 实验恢复上述全部属性。`@S` 不变换软链接目标；[真实客体链接实验](2026-09-23-gnu-tar-root-links-result.json)还验证了硬链接同 inode、链接数为 2、相对软链接 `_data/nested` 的文本与读回内容。备份/恢复 tar 错误改为固定文案，避免私有路径经操作回执泄漏；恢复写入结果不明时仍保守进入 `needs_verification`。

最终真实命令与结果：

```text
cd apps/backend && uv run python /tmp/autoflow-restore-rootfixed-20260923.py > /tmp/android-goal-restore-rootfixed-real.log 2>&1
# exit 0, status=passed；仓库逐字脚本见 2026-09-23-restore-rootfixed-smoke.txt
```

经真实 FastAPI 路由、Lima 容器和数据卷执行：部分卷写入后注入连接超时，操作进入 `needs_verification`；recover 后直接调用备份服务重写目标返回 `ANDROID_RESTORE_TARGET_INVALID`，HTTP 重放 409；正常恢复 202，同请求重放 202，启动后 ADB 读回测试文件。源与目标在启动目标前的 **1792 个可持久条目**（路径、类型、内容、UID/GID、权限、软链接文本及属性）的 SHA-256 相同：`f760bfe4030acc5ec72cc41f24aac7ff061b0d7c7527fff87297f326fd54ed3f`；双方各有 417 项扩展属性和 55 项 ACL。该全卷扫描不比较 inode/硬链接关系，硬链接由上面的独立客体实验验证。源卷另有 `system/ndebugsocket`、`system/unsolzygotesocket` 两个 Unix socket，GNU tar 不归档此类临时端点；严格全卷比较曾因此失败，逐路径差异检查证明除此之外没有缺失或属性差异。最终三台自建实例均已删除，容器与卷各为 0；源卷“未改变”的额外运行后检查只覆盖测试文件，不宣称全卷运行后未变。

另以真实 scrcpy 打开手动和只读原生窗口，进程均保持存活至少 2 秒，关闭窗口后 Android 仍 ready；自建实例及卷清零。此证据覆盖窗口进程生命周期，不代替真实人工输入/切端、心跳失联、5/10 实例压力、Google 账号/网络、硬进程中断、APK 临时文件清理或 T20 完整失败矩阵；这些仍按对应阶段记录为 `not_run` 或在缺少外部条件时记 `blocked`。
