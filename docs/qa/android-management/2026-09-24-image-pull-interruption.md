# 镜像拉取回执持久化后中断核实

- 日期：2026-09-24；产品后端基线 `33e7f547`，本轮没有改后端业务代码、契约或迁移。[脚本哈希](2026-09-24-image-pull-interruption/candidate-hashes.json)绑定实际最终执行源。
- 状态：本故障边界 confirmed；T09 整体 partial，桌面删除和下载途中断网仍未验。
- 平台：真实 Apple Silicon Mac / Lima Docker；独立临时工作区、认证 HTTP sidecar、生产 ImageCatalog、SQLite 和 Operation。

## 实验及实际结果

```sh
uv run --project apps/backend python docs/qa/android-management/scripts/image-pull-interruption-smoke.py --allow-image-pull --output docs/qa/android-management/2026-09-24-image-pull-interruption/result.json
```

实际 exit 0，`status=passed`：[可复现脚本](scripts/image-pull-interruption-smoke.py)、[完整输出](2026-09-24-image-pull-interruption/passed.log)、[结构化结果](2026-09-24-image-pull-interruption/result.json)。缺少允许拉取标志时 [exit 2](2026-09-24-image-pull-interruption/cli-guard.log)，没有启动实验。

脚本从已缓存官方镜像的 RepoDigests 取得固定仓库引用，执行真实 Docker pull；Id 单独用于验证本机内容身份。计数包装不替换拉取 IO。故障钩子先调用生产 `_save_registration` 提交镜像和请求回执，再原子写出边界标记并暂停；监督进程只终止自身 sidecar 进程树，此时 Operation 尚未写入成功终态。

1. 原 HTTP 请求收到真实 `RemoteProtocolError`，本次终止 1 个自有进程组。
2. 同工作区重启后，原请求对应同一 operationId，状态 `needs_verification`，结果码 `SERVICE_RESTART_RESULT_UNKNOWN`。
3. 再提交原 requestId 返回同一待核实操作；不会重放拉取。
4. 以原 requestId 显式核实，生产服务按持久回执检查固定 imageId，得到 `succeeded / IMAGE_PULL_VERIFIED`。
5. 跨两个服务进程记录的实际 ImageCatalog.pull 调用总数为 1；原基础 tag 的 Id 不变。
6. 仅取消本次新工作区的镜像登记，`deleteContent=false`；没有删除基础镜像内容，没有创建实例或数据卷，自有服务均退出。

这是**拉取已完成、回执已提交但 Operation 终态尚未落库**的真实进程中断实验。它不证明镜像层下载中途网络中断、磁盘不足恢复或真实桌面入口行为；也不是冷缓存下载速度测试。

## 首次失败、修正与审查

首次脚本在显式核实时误传新 requestId，生产契约正确返回 `409 ANDROID_REQUEST_CONFLICT`：[失败输出](2026-09-24-image-pull-interruption/first-run-failed.log)、[当时已完成步骤](2026-09-24-image-pull-interruption/first-run-incomplete.json)。按实际契约改为原编号后，先单独核实并取消首次自有登记：[恢复与清理](2026-09-24-image-pull-interruption/first-run-recovery.json)，再从新工作区完整重跑。首次失败不能计为完整通过，也没有因此放宽产品校验。

独立审查指出不能把 Docker Id 普遍当成仓库 manifest 摘要；最终脚本改用 RepoDigests，并补 marker 原子发布和失败时登记可能保留的说明。最终只读复审无剩余 Critical/Important；审查者没有重新运行实验。脚本 Ruff 通过；镜像单元/目录/HTTP契约/生命周期集成实际[38 passed / 1 warning，0.76s](2026-09-24-image-pull-interruption/contracts.log)，命令 `uv run --project apps/backend pytest apps/backend/tests/unit/test_android_images.py apps/backend/tests/unit/test_android_image_catalog.py apps/backend/tests/contract/test_android_images.py apps/backend/tests/integration/test_android_images_templates.py -q`。产品后端未变，完整后端 4048 passed / 26 skipped 仍属[上一提交的实际门禁](2026-09-24-bulk-actions/full-backend.log)。

后续规格复核确认镜像页面目前只有GET查询，尚未调用本实验使用的POST核实；这是待补的软件缺口，不能把后端实验当作页面已实现。

剩余：Mac 锁屏阻塞真实桌面内容删除；下载进行中的网络故障需要另设受控边界，不使用本实验替代。T12 回退演练、T14/T16 桌面性能及最终全分支验收继续保留未完成状态。
