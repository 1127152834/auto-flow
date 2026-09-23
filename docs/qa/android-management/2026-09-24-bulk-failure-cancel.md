# 批次修订号、部分失败与取消真实验收

- 日期：2026-09-24；状态：`confirmed`（定向自动化与自建实例真实 HTTP）。来源：隔离分支、RED→GREEN 测试、Apple Silicon Mac/Lima/ReDroid。

真实故障演练先暴露了新设备修订号不一致：管理列表将 `generation=0` 投影为 `revision=1`，批次执行却直接比较原始 0，导致页面刚创建的设备提交正确修订号仍被错误标为冲突。同步执行和持久队列的两个测试先 RED（两项均 `failed`），然后抽取统一的公开修订号规则给列表、备份与批次共用，GREEN：相关批次/设备/备份 25 项通过。失败前的一轮真实批次两项都报修订冲突，故没有被当作部分失败通过。

修复后运行 `uv run --project apps/backend python /tmp/autoflow-am3-bulk-failure-cancel-real-20260924.py`，exit 0，`status=passed`。在独立工作区，批量停止两台真实实例：第一台按当前修订号执行成功，第二台故意提交过期修订号，批次最终 `partially_failed`、子项 `[succeeded, failed]`，第二台仍保持 `ready`。随后创建一台最低准入无法容纳的 8192 MiB 停机实例，批量启动进入 `waiting_capacity`；对原批次执行 `cancelPending`，批次及子项均为 `cancelled`，设备仍 `stopped`。最后逐台用认证 HTTP 永久删除本轮三台；独立 Docker 标签查询 `ownedContainers=[]`、`ownedVolumes=[]`。

最终分支复审又发现两个软件边界：容量异步探测返回后旧批次可越过已更新设备版本；真实运行时失败推进 generation 后，`retryFailed` 沿用旧版本必定冲突。两项先有失败回归，再改为容量返回复读、管理器持运行时锁核对 `expectedRevision`，以及显式重试冻结新的内部修订号。上述真实脚本在这两项修复后重跑，并进一步对修订冲突的失败项执行 `retryFailed`，exit 0，输出 `partial=[succeeded,failed]`、`retried=[succeeded,succeeded]`、`cancelled=cancelled`、`capacityItem=cancelled`。重试项拥有 `retryOf` 持久关联，两台最终均停机。随后用生产 `MacAndroidRuntime.verify_deleted` 对本轮三台设备及其归属容器/卷只读核实，输出 `realDeletedDevices=3`、`states=[missing,missing,missing]`。

这是明确的乐观并发冲突、该冲突的显式重试和容量等待取消演练，不代表已验证运行时中途崩溃、ADB 断连、未知结果重试或取消已开始的副作用。真实运行时瞬时失败后的重试仍未演练。
