# 安卓批次公开修订号一致性

- 日期：2026-09-24；状态：`confirmed`；来源：[真实部分失败与取消](../../docs/qa/android-management/2026-09-24-bulk-failure-cancel.md)及 `test_android_bulk.py` RED→GREEN。

管理列表对新设备 `generation=0` 公布 `revision=1`；批次执行旧代码直接将 0 与页面提交的 1 比较，导致合法请求误报修订冲突。公开修订号必须由同一 `public_device_revision` 规则生成和比较，覆盖管理列表、备份和同步/持久队列批次。真实 HTTP 复验两台部分失败、修订冲突项显式 `retryFailed` 后两项均成功、容量等待取消及本轮三台资源彻底清理通过；真实运行时瞬时失败后的重试仍缺证据。
