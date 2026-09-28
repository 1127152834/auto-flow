# QA-03 运行终态与进程清理诊断

日期：2026-09-28；状态：in_progress；置信度：下述异常栈高，原三项失败根因未知。

原默认全量 `backend-final.log/xml`：4278通过、3失败、44跳过。凭据空值、非法概率、webhook超时三个负向场景预期failed，却进入WORKFLOW_RESULT_UNKNOWN/interrupted。保留原断言、超时与原始输出。

`backend-diagnostic-full.log/xml`：4278通过、5失败、44跳过。开始于faf8fc21；运行途中PM9 End源码开始修改，子进程会读取新源码，此轮不是稳定版本验收。原三个场景没有再次失败；新的一个项目人工输入停止竞争场景捕获明确栈：`capture_processes` → `force_process_tree` → `ProjectWorkflowWorkerManager._cleanup_owned` 抛出 `Candidate browser process ownership is unavailable`。这证明严格归属扫描存在真实失败入口，但尚不证明它就是原三个失败的根因，也未确定候选PID归属、内核读权限或退出竞态。

另外四个sidecar shutdown用例启动未读到READY，随后JSONDecodeError。测试未将stderr写入断言；并行定向pytest使用默认临时根自动清理较旧代次，原stderr目录事后已不存在。不能猜测为End导入问题或环境问题。后续诊断使用每轮专属`--basetemp`，防止不同测试会话删除调查证据。

随后同文件独立复核 `sidecar-shutdown-current.log`：5项通过、30.40秒，使用专属临时根。该结果证明当前时点可以启动及正常清理，不足以确认原四项失败根因；最终仍需稳定源码全量。

非改变行为的诊断插件只包装真实函数：异常保留原栈并原样抛出。第二版增加失败时的候选PID、worker PID、启动身份、进程状态与原生参数可读性，不打印参数或环境值。覆盖四个相关文件的 `cleanup-candidate-focused.log` 31项通过，尚未再次捕获异常。

另用自有真实短生命周期Python进程检查POSIX归属边界：最初100轮、等待10ms后100轮、等待子进程READY后100轮均未复现（`process-exit-probe*.json`）。这是进程边界调查，不是生产工作流场景。保留最终探针 `process-exit-probe.py`；全部自有子进程wait回收，临时目录删除。READY探针首次命令有Python引号语法错误，修正后才执行，未把空输出计通过。

下一步必须先取得可归因的候选身份或有效的确定性复现，再决定修复；不关闭strict_ownership、不忽略未知活进程、不扩大超时、不把interrupted加入预期。若已有已确认启动身份足以判断归属，应核对是否存在冗余原生参数读取错误，但当前还不能据此断言全部问题已定位。
