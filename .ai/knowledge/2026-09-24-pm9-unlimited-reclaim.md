# PM9 不限任务同记录复用与公开停止

2026-09-24 DATA-CLAIM-14不限领取补证（confirmed本机源码子范围）：保存默认上限1、公开启动maxTasks=null，单一最终态A01由真实TCP HTTP/SQLite/worker/CloakBrowser连续成功5Task，第6Task人工等待时公开停止为cancelled；六次同RecordRef/内容版本1/状态版本2，完整原记录不变，每次只持有本Run一条lease，最终6条全部释放。原停止命令查询/重放一致，停止后三轮真实调度无新增Task，工作目录/容量清空。真实1 passed/28.11秒，相关50 passed/26.99秒，Ruff通过；保存策略null和时间格式比较的夹具错误保留，不称产品修复。CI两处选择已包含新用例，collect1/51不是执行；fresh CLI401，新三平台/打包UI说明与停止验收保留。生产仍a7059dc6，不重复无改动全量/构建。251仍209partial/42planned/0verified，249有断言/2未定位及241生产/19实现/8测试/24外部缺口不变；releaseAccepted=false。见unlimited-reclaim-follow-through.json。

来源：data-and-state-rules.md §6.3 / DATA-CLAIM-14；新真实集成测试及runtime-evidence.json原始trace。测试保存策略maxTasks仍要求正整数，启动override null才表示不限；没有放宽生产契约。首次实际运行到回执比较失败，差异为类型化日期与原始JSON日期格式，按现有强停测试比较同一时刻，保留全回执相等。没有使用计数或文件名替代断言。
