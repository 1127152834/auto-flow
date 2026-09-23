# PM9 停止批次的归属不明核验

日期：2026-09-24；状态：confirmed 本机源码完整回归/新ARM包，当前三平台待验。

2026-09-24 XE-C06/XE-G02归属不明核验修复（confirmed本机源码/新包子范围，三平台pending）：生产cb040daf修复参数/数据批次在Task核验中仍显示stopping，并通过既有停止操作保留停止意图，避免重新领取及状态版本抖动。四个反例先失败，相关50项通过；真实普通/已知/未知归属强停3项通过（92.10秒），Ruff/mypy408及映射4项/251引用通过。串行完整后端3497 passed/84 skipped/2 warnings（900.44秒）；新未签名ARM包完整桌面passed/22截图，已目视核对3张。真实worker1004条/31410ms、万行43624ms/0busy、固定1000条合成输入60016ms均为单次本机观察。归属证明缺失期间保留进程/目录/容量/原命令，恢复后原命令完成。Windows Job和打包核验UI仍缺；旧35902129697三平台job成功但不含当前源码，CLI401/日志403仍阻断新矩阵与产物复核。251条状态不升级，releaseAccepted=false。详见unknown-owner-follow-through.json。

根因：两类调度器先在stopping分支返回，再检查active reconciling；仅调换判断仍会让下轮普通停止意图丢失。复用ProjectOperationRow的running stopBatch/forceStopBatch和projectId/batchId约束，没有新增状态存储或恢复执行器。三轮轮询保持同一statusRevision；恢复后原操作成功且批次stopped。

故障注入只作用于本任务POSIX进程组的身份探针，独立原生探针仍验证真实birth；不是制造PID重用、跨进程人工恢复或Windows Job验收。初始真实失败日志和四个参数反例RED均保留，见机器报告哈希。历史force-stop-follow-through.json的未知归属待验由本报告部分补齐，其历史检查不重写。
