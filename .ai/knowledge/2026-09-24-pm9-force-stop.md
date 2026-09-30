# PM9 参数任务真实强停

日期：2026-09-24；状态：confirmed本机子范围。来源：execution-and-environment.md §10/XE-G02；生产dispatcher与进程归属实现；真实HTTP/SQLite/worker测试。

2026-09-24 XE-G02强停补证（confirmed本机子范围）：参数真实worker在普通停止后模拟下行通道丢失，实际30秒宽限期内409，公开门禁到期才强停；原生birth身份/进程退出、执行代次撤销、interrupted未知结果、人工取消、临时目录/容量回收及原命令终态查询重放通过，无后续节点/额外Task。最终普通停止+强停2 passed/34 deselected（74.42秒），Ruff通过；既有CI选择新增场景并collect35/46（非运行）。早期夹具/终态/DTO时间比较错误全部保留，不称产品修复。归属不明核验、打包UI与新增三平台仍待验；无生产改动，251条状态不变，releaseAccepted=false。详见force-stop-follow-through.json。

复用原参数批次harness，仅在worker.stop_requested后丢弃manager._send下行消息。没有改时钟、宽限期、原生identity或终止实现；人工timeout设置120秒给真实30秒宽限期留足测试时间，轮询预算60秒不改变产品。原单消息夹具被取消回复正常结束，所以不足以产生强停；强停正确结果为interrupted而非普通cancelled。停止命令running到succeeded可查询；查询BatchView把时间序列化为Z，run命令result保留JSON偏移写法，比较时仅归一两个ISO时刻，其余操作/结果字段完全相等。

未声明归属不明场景通过，未据本机原生身份调用冒充Windows Job成员验收。新增CI选择等待认证恢复后的最终矩阵，当前旧矩阵不包含本轮断言。详见机器报告和原始日志SHA256。
