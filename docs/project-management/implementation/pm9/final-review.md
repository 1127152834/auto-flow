# PM9 独立审查与处置

日期：2026-09-20；状态：confirmed；来源：独立只读审查 `8e5564e0..4cd7f85c`、本机回归与真实浏览器验证。审查结论原为 needs changes（4 P1 / 3 P2），以下是逐项修复记录，不冒称进行了第二次独立审查。

| 问题 | 处置与证据 |
|---|---|
| 人工成功终结后循环继续 | 共享 Runtime 停止迭代与 done 调度；覆盖成功、失败、超时终结 |
| 并行循环串用 loop_stack | 项目准备阶段拒绝包含循环或人工节点的并行根/扇出；普通并行图仍开放。解除限制须先隔离共享控制状态 |
| End 提前越过未完成循环 | 循环整体结束后才进入 executed；有界共享调度测试验证 body/body/End 顺序 |
| 人工 RPC 阻塞 worker 退出检测 | 同时监控进程退出；撤权提交后取消人工项。真实子进程测试和真实浏览器 manual-loss 验证 interrupted/cancelled |
| previewFieldChange 授权无法通过 | UI 和协调器映射至既有 modifyField 权限；后端清单与真实配置控件回归 |
| 后一人工检查点覆盖前一项重试定位 | 按 manualItemId 查询检查点；真实连续人工节点重放旧 key 返回原 operation |
| 数据嵌套引用不能用于浏览器动作 | 复用原动作，文本解析交给共享 resolver，只解析一次；保留前导零、字面花括号与追加行为 |

附加发行问题：Windows 旧代码页 JSONL 通过显式 UTF-8 修复（强制 ASCII 管道先失败后通过）；Windows TerminateProcess 与进程退出竞争需在权限拒绝后确认进程已退出，不能直接丢失清理事实。负载在 Windows runner 上超过 180 秒，测量预算改为 600 秒并减少轮询，不把较慢结果伪报为达到吞吐目标。

独立审查 Declined to judge：最终同提交 Actions、安装签名/公证/实机、实网 Sheets、未接入的其他 Studio 节点、历史覆盖数字。本机补验和 CI 另列在 verification.json；这些项目不能靠审查口头认可升级。

2026-09-21 范围追补：审查后的原生进程探测、Windows 文件提交、平台夹具与固定速率负载改动，由执行账本中的定向测试和最终候选 CI 验证，未进行第二次独立审查。
