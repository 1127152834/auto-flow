# 安卓管理全分支审查修复与真实验收增量

- 日期：2026-09-23；状态：`confirmed`（本页列出的定向测试与真实实验）；全阶段最终验收仍为 `partial`。
- 来源：隔离分支 `codex/android-management-complete` 的只读全分支审查、RED→GREEN 测试、Apple Silicon macOS 上的生产 Mac/Lima/ReDroid 适配器。三份既有 Studio 未提交文档改动未纳入本模块。
- 基线：`d4677354` 后的增量；最终提交和全量门槛以同目录 `2026-09-23-current-full-gates.md` 后续记录为准。

| 审查发现 | RED 可观察失败 | 修复与 GREEN |
| --- | --- | --- |
| 备份使用工作区路径、镜像引用保护使用运行时哈希，删除镜像会漏掉备份 | 同工作区备份存在时内容删除未抛异常 | 镜像服务按备份实际路径身份筛选；同工作区阻删、异工作区不误阻删两项通过。 |
| 自定义缓存镜像恢复只看环境默认镜像列表 | 精确镜像缓存可核实时 HTTP 恢复仍返回 `409 ANDROID_BACKUP_IMAGE_MISSING` | 恢复前对备份固定 imageId 做运行时 inspect，检查 Linux/ARM64；真实缺失仍拒绝，探测未知保持 `needs_verification`；相关集成通过。 |
| 元数据核验通过被读成 GApps 整体验收通过 | `validation` 缺失，界面只显示泛称“验证 通过” | 契约单列 `validation`，元数据检查只更新技术核验；谷歌六项未做时 `not_tested`，不支持项记 `blocked`；界面分别显示组件声明、元数据核验、谷歌组件验收。 |
| 同一摘要第二次拉取的请求无法核实 | 第二次拉取无独立回执，`POST /operations/{id}/verify` 返回 503 | 每次拉取写持久 `image_pull_receipt`，核实原请求、引用及固定 imageId 的运行时缓存；第二次拉取回执和 HTTP 核实通过。 |
| 已删除摘要重新拉取后目录仍标记已删除 | 运行时已重新缓存镜像，但目录仍返回 `state=deleted` | 重新拉取确认后恢复目录当前态并推进 revision；未核实的删除请求仍阻止重拉。 |
| 应用操作跨进程重启失去原会话核实入口，普通设备恢复可吞掉完成标记 | 重建控制台后原 `verify_app` 返回 410；`recover` 对 pendingCommand 继续进入运行时 | 从持久会话回执重建只用于核实的上下文，锁定设备，写入终态后释放标记；有未核实标记时普通恢复返回 `ANDROID_APP_OPERATION_UNVERIFIED`。 |
| 整卷 tar 多次进入 Python 字节缓冲，随卷大小增长有内存风险 | 文件流适配器测试先因 `backup_volume_to_path` / `restore_volume_from_path` 缺失而失败 | 生产 Lima 子进程把归档直接写入 staging 文件或从已校验文件读取；应用逐块算摘要，tar 安全校验保持；测试显式禁止旧整包字节接口。 |

定向命令：

```text
uv run --project apps/backend pytest -q apps/backend/tests/unit/test_android_backup.py apps/backend/tests/unit/test_android_runtime.py apps/backend/tests/integration/test_android_backup_restore.py apps/backend/tests/integration/test_android_restore_isolation.py apps/backend/tests/unit/test_android_console_lifecycle.py apps/backend/tests/unit/test_android_management.py apps/backend/tests/unit/test_android_images.py apps/backend/tests/contract/test_android_management_operations.py apps/backend/tests/contract/test_android_images.py
```

实际输出：`188 passed, 1 warning in 11.06s`（修复归档流最后两个测试前的集合）；随后文件流专门测试与真实实验通过。Ruff 对变更文件 `All checks passed!`，`git diff --check` exit 0。完整后端和前端测试正在独立重跑，结果以当前门槛记录为准；本页定向结果不冒充全量通过。

真实五实例：`uv run --project apps/backend python /tmp/autoflow-am3-five-device-qa-20260923.py`，exit 0，`status=passed`。隔离工作区内 5 台实例全部达到 `ready`；20 次认证 HTTP 列表读取 `min=1.93ms, median=2.13ms, p95=2.74ms, max=3.91ms`，陈旧数恒为 0；两台并发预览各返回 654359 字节 PNG，耗时 1002.70/1013.22ms。五台 Docker 实测内存分别为 576.7MiB/1.5GiB、604MiB/1GiB、590.4MiB/1GiB、626.6MiB/1GiB、673.2MiB/1GiB。批量停止与 `deleteData=true` 后目录无这五台，独立 Docker 容器/卷名称核查均为空。10 台及真实部分失败/取消仍未跑。

真实归档文件流：`uv run --project apps/backend python /tmp/autoflow-am4-stream-real-qa-20260923.py`，exit 0，`status=passed`。单独工作区源实例写入探针，停机备份归档 17,868,800 字节，HTTP 新实例恢复后启动并读回 `stream-proof-20260923`。实验把旧字节缓冲备份/恢复方法替换成抛异常函数，因此成功结果证明调用了文件流方法；源/目标实例与备份在 `finally` 中删除，报告无清理错误。

真实完成标记：`uv run --project apps/backend python /tmp/autoflow-am1-restart-app-receipt-real-20260923.py`，exit 0，`status=passed`。真实设备执行应用 stop 并保留客体完成标记；最新一轮故障注入把持久回执停在 `running` 且不保存 marker ID，模拟命令成功后进程退出的窗口。新构造的控制台凭设备上持久的 `pendingCommand` 绑定原会话/请求编号并核实，终态为 `succeeded`，标记删除后普通恢复成功。本实验重建服务对象与运行时，没有发送真实进程 `SIGKILL`；HTTP 进程级硬重启故障注入仍需单独验收。自建实例删除后容器/卷核实为空。

限制：GApps 专用镜像、测试账号、商店下载及第二实例隔离仍缺外部条件，状态 `blocked/not_tested`；真实断网、10 台规模、磁盘不足、归档传输/解包中断、桌面精确缩放和高级日志仍未通过完整验收。旧版无持久归属的客体临时文件不能靠本次新路径推断已清理。
