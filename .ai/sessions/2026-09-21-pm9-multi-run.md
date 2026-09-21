# PM9 S5 独立 Run 所有权

日期：2026-09-21。状态：confirmed（源码验证，平台候选待验证）。来源：已批准 S5 规格、失败复现、定向和生产 smoke。

单 owner 拆为拥有执行代次的 Run 状态。生产项目装配容量 2；通用默认仍 1。保留单参数批次顺序语义，数据领取继续用原事务与额度。预算/暂停/停止/核验/资源释放按 Run，不使用全局 busy 判断另一个 Run 是否清理完成。

既有 OS workspace/Profile/kernel/license 锁由项目资源集合内部引用共享；不同 Run 使用独立工作副本。恢复通过同一资源 guard 保护；历史未知所有权保持全局准入关闭。锁释放失败不会在第二次 release 时消失，并钉住工作区保护。

验证：125 定向，45 owner/guard/恢复边界组，真实两进程不同 PID、独立 ACK/取消/目录清理；单数据批次两记录并发领取和 cookie 隔离，取消另一批次保持原人工 Run，T2 waiting_manual 时 T1 完成结构和值写入而 T2 后续旧契约继续。原始结果 multi-run-business-darwin-arm64.json 来自本轮 PyInstaller backend，不是桌面安装包放行。

附带修正 Intel CI 最后浏览器管理 smoke 的等待：错误提示和 query 刷新存在异步边界；现在有界等待实际按钮存在且恢复可用，不允许缺按钮误通过。真实源码 Electron smoke 通过。

后续：S4 Windows 原生边界、独立最终复审、完整回归与当前三平台 CI。不得合并或发布；releaseAccepted=false。
