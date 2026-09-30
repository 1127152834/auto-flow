# AM3 真实双实例批量链与 HTTP 响应修复

- 日期：2026-09-23；状态：`confirmed`（下述本机链），AM3 完整规模/部分失败场景仍为 `partial`。
- 环境：隔离 worktree 的真实后端 sidecar、独立临时工作区、Mac/Lima/ReDroid；固定本机 ARM64 ReDroid imageId `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b`。
- 脚本：`/tmp/autoflow-am3-bulk-real-qa-20260923.py`；以真实认证 HTTP 调用，运行时容器/卷由 Lima Docker 执行。

先在空工作区运行时，第二台创建被 `ANDROID_IMAGE_UNAVAILABLE` 拒绝：该工作区还没有登记基础镜像。这是预期准入规则，不能算批量验收。第一轮自建两台设备的容器/卷均核实为 0 后，删除该轮专用临时工作区。脚本随后补上本工作区镜像登记，再创建第二台，单实例准备完成。

接着真实 `POST /management/bulk-operations` 返回 500。sidecar 堆栈定位到 `BulkRead.model_validate()` 接收持久记录的内部 `workspaceIdentity`，被严格 DTO 作为额外字段拒绝；GET 和批次动作同样直接返回内部记录。新增契约测试先观察到创建/查询/动作 `500/500/500`，随后三个路由复用公开字段投影，包含核实分支；定向后端 `20 passed, 1 warning`，Ruff `All checks passed!`。

修复后的真实批量重跑输出 `status=passed`：两台自建实例 `19a8728b-41cb-44e9-a642-5024e0237b06`、`b27e0788-71c8-4548-8de5-3c9277430e11` 分别在批量 `start`、`stop`、`delete` 三阶段均得到批次 `succeeded`、两个条目均为 `succeeded`。永久删除使用 `deleteData=true`；管理列表不再包含两台，随后按其持久记录和工作区身份调用真实 `management.verify`，两台容器与卷均为 0。成功工作区为 `/tmp/autoflow-am3-bulk-real-qa-20260923-c7fa8a4b82a2481caee51d66a8942381`。

最初暴露 500 的自建工作区中，第一台曾因失败收尾时立即请求下一操作留下 `recovery_required`；独立认证 HTTP 重启后，明确 `recover` 等到成功，再用 `deleteData=true` 永久删除。另一台已删除；两个旧实验 ID 均未再关联运行容器或数据卷。所有清理只针对本轮自建工作区和标签，不触碰其他工作区已有的容器或卷。

这条真实链覆盖正常批量排队、每项持久操作、双实例启动/停止/永久删除及实际资源消失。部分失败、取消未开始项、失败重试和未知结果仍由自动化覆盖，未在真实双实例故障注入中复验；5/10 台性能门槛也没有从两台结果推断。
