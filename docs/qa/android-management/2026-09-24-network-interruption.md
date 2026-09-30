# 真实镜像下载中断、重启与网络恢复验收

2026-09-24；confirmed；结果passed；产品候选0f6f8fac（HEAD4e7268f1），生产代码未修改。命令：

```sh
uv run --project apps/backend python docs/qa/android-management/scripts/image-network-interruption-smoke.py --allow-image-pull --output /private/tmp/android-network-interruption-final.json
```

实际exit0。完整[结果JSON](2026-09-24-network-interruption/real-final.json)、[输出](2026-09-24-network-interruption/real-final.log)、[检查记录](2026-09-24-network-interruption/checks.json)。脚本Ruff、guest代码编译、help通过；缺少变更授权参数exit2。

## 隔离与证据范围

真实认证HTTP、SQLite、ImageCatalog及MacAndroidRuntime运行在新建workspace。QA仅将Docker命令传输指向Lima中的独立Unix socket；执行真实Docker和独立containerd，没有mock返回值。data-root/exec-root/socket/containerd目录均为本轮专属路径；与现有运行时相同的overlayfs/containerd snapshotter。测试代理只监听VM回环地址，TLS透传、不解密、不记录认证内容；故障只关闭测试守护进程的代理连接，未修改Lima防火墙、系统Docker配置或用户网络。[Docker官方守护进程文档](https://docs.docker.com/reference/cli/dockerd/)说明独立目录、socket和containerd配置参数。

这是隔离Docker连接下的生产服务/运行时真实网络故障验收；不宣称对用户共用守护进程断网，也不替代Electron桌面验收。

## 实际结果

- 官方固定引用redroid/redroid@sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b。
- TLS上游已读取4212479字节，真实containerd ingest文件已落盘3145728字节后截断连接。Docker报告期望640472802字节、实际收到4144085字节的short read/unexpected EOF，证明故障发生在镜像层传输中。
- HTTP返回502/ANDROID_COMMAND_FAILED；持久Operation为failed，相同requestId重放202返回原失败回执，不再次拉取；重启sidecar后仍为同一失败Operation。失败时镜像目录为空，实际pull计数保持1。
- 解除测试代理故障，使用新requestId发起第二次真实pull，约67秒后succeeded/IMAGE_PULL_SUCCEEDED；返回固定imageId与原镜像一致。实际pull总数2，没有隐式重试创建新请求。
- 通过生产HTTP删除测试守护进程中唯一新镜像，目录状态deleted且Docker镜像列表为空。独立dockerd/containerd退出，专属临时目录移除。既有六个容器ID列表与原镜像ID前后完全一致。

Operation失败b4e0bb7d-6908-472f-947d-619f84bb3ec2；恢复成功b5422abc-d2b4-4b6e-bf0c-96b71079a6cb；完整requestId、时间及PID见JSON。

## 测试脚本校准与剩余项

首轮脚本把TTY的Downloading进度文字作为证据，但非TTY只输出Pulling fs layer，因此观察断言失败；保留[首轮输出](2026-09-24-network-interruption/initial-harness-failure.log)。随后改为读取真实下载暂存文件大小。中间VFS隔离环境已成功恢复拉取，但imageId表示与原containerd存储不同，固定身份断言失败；保留[存储差异输出](2026-09-24-network-interruption/storage-identity-harness-failure.log)。最终改用相同存储后端，原身份断言保持并通过。这两次是QA环境/观察修正，不是产品RED→GREEN，也没有放宽产品断言。

本证据关闭T09“下载途中真实网络中断与恢复”缺口；原先回执持久化后SIGKILL/未知结果核实证据仍独立有效。Mac本轮复查仍锁屏，桌面内容删除、新入口、长期隐藏心跳/性能和同发布入口切换组合链仍blocked/未执行；十台容量和GApps条件未变。未重跑未变的全量产品测试；0f6f8fac后端4124与相同前端5689结果继续适用。整体仍partial，102步骤计数仍85passed/14not_run/3blocked，不追认缺失历史RED。
