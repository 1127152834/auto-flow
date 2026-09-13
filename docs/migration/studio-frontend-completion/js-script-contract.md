# F1/F3 JavaScript 前端请求与回传合同

2026-09-14，状态：本有界合同与消费实现已验证；全部F1/F3尚未完成。依据已确认F0–F6计划，来源为冻结WebRPA main.py request_js_script_sync/js_script_result、executors/basic.py JsScriptExecutor及BasicModuleConfigs的同步脚本说明。

保留 main(vars) 同步计算语义；不支持 Promise、DOM。通过专用 Web Worker 执行，使停止和30秒上限能终止脚本，避免阻塞Studio。Worker并非安全沙箱，不提供权限隔离承诺。变量用副本传入，输出必须能无损表达为JSON；undefined顶层返回值按null，非有限数字、循环对象及其它非JSON值明确失败。服务仅同步已存在变量，resultVariable可创建。

事件 execution:js_script 增加workflowId/nodeId用于关联；保留requestId/code/variables。GET /api/events/js-requests/{requestId}返回pending/claimed/completed/failed/expired及claimId（无脚本和变量）。领取命令js_script_claim携带requestId/claimId；仅pending可首次领取。结果命令js_script_result必须携带同一claimId，明确success/result/variables或error。继续使用现有稳定commandId与查询接口，同ID不同内容409。

前端先查询状态并领取，确认后才启动Worker。同一请求在本次页面生命周期只执行一次。重连查询已提交命令，不重放脚本；新页面遇到已领取请求不能抢领执行，记录现场无法恢复并要求停止。完成或停止后的迟到结果拒绝。停止取消Worker；命令响应不确定时只查询原标识，不生成新命令重试。

Mock只负责事件、领取与结果校验、确认后调度下一节点；脚本计算发生在真实前端Worker，不是自动化后端。后续正式服务需要实现该领取合同；旧服务未实现时明确失败，不绕过确认直接执行。

验收：内存/HTTP同协议，领取幂等、错误身份、格式错误、成功变量映射、脚本失败、停止与迟到回传；Worker同步结果、禁止异步/DOM、非JSON、超时/取消；浏览器UI编辑脚本、运行、结果可见，保持Mock标识。正式Electron和未测平台单列。
