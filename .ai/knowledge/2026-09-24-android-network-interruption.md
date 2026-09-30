# Android真实镜像下载中断

2026-09-24；confirmed；来源docs/qa/android-management/2026-09-24-network-interruption.md及原始结果。

在同一Lima中启动独立Docker/containerd（相同overlayfs snapshotter），只将QA进程Docker命令连接路由到独立Unix socket。TLS透传代理在镜像层实际落盘3MiB后断开测试连接，生产HTTP502及持久failed符合已知失败语义；原编号重放和sidecar重启未新增pull。恢复代理后新编号约67秒成功，固定imageId一致。生产HTTP删掉测试镜像，独立daemon/containerd与临时目录清理；原六容器/镜像身份前后一致。无产品修改、无mock返回值。

首次非TTY进度观察断言不适用；改为真实暂存字节。中间VFS与containerd imageId表示不同，最终使用一致存储后端保留原身份断言通过。不能将这两个QA调整冒充产品RED。Mac仍锁屏；这不替代桌面内容删除、隐藏控制与性能验收。
