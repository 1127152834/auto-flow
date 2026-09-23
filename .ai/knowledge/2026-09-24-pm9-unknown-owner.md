# PM9 停止批次的归属不明核验

日期：2026-09-24；状态：confirmed 定向测试，完整回归/新包进行中。

2026-09-24 XE-G02归属不明核验修复（confirmed定向子范围，完整回归进行中）：真实worker证明缺失时Task已reconciling而Batch错误stopping。参数/数据调度器现在优先投影核验事实，并从同项目同批次running停止操作保留停止意图，避免后续重新领取或状态版本抖动。四个反例先失败，相关50项通过；真实普通/已知/未知归属强停3项通过（92.10秒），Ruff与mypy408通过。POSIX受控探针失败期间保留真实进程、目录、容量和原命令，恢复证明后原命令结束清理。Windows Job与打包UI联合门禁仍缺；251条状态不升级，releaseAccepted=false。详见unknown-owner-follow-through.json。

根因：两类调度器先在stopping分支返回，再检查active reconciling；仅调换判断仍会让下轮普通停止意图丢失。复用ProjectOperationRow的running stopBatch/forceStopBatch和projectId/batchId约束，没有新增状态存储或恢复执行器。三轮轮询保持同一statusRevision；恢复后原操作成功且批次stopped。

故障注入只作用于本任务POSIX进程组的身份探针，独立原生探针仍验证真实birth；不是制造PID重用、跨进程人工恢复或Windows Job验收。初始真实失败日志和四个参数反例RED均保留，见机器报告哈希。历史force-stop-follow-through.json的未知归属待验由本报告部分补齐，其历史检查不重写。
