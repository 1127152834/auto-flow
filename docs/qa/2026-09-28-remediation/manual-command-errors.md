# A-01 补充：人工命令失败回放

日期：2026-09-28；状态：confirmed；置信度：高；对应提交：本文件所在提交。

当前源码重新发现：resumeManual/finishManual 首次 CAS 冲突返回409并保存失败 operation，使用同一幂等键重试却直接返回 result=None，HTTP202掩盖已确定失败。到期检查发生在幂等回放之前，也可能覆盖已存在的原判定。

最小修复：复用 retention 的 `_reject_replayed_failure`，先返回原持久结果/错误，再对新请求检查到期；原错误保存 HTTP status、code、message、details。不换键重发，不改人工状态和执行器语义。调用方包括两个人工 HTTP 入口，既有查询 operation 保持。

有效红灯：`manual-replay-red-valid.log`，两个真实迁移SQLite/HTTP用例首次409，第二次错误202。修复后 `manual-replay-fixed.log` 相关19项通过；两个新增断言检查原code/message/details与HTTP状态保持、人工项仍waiting。requestId是每次HTTP请求的身份，不要求相同。`manual-replay-red.log` 保留编写测试期间缺retainEnvironment字段的422，不计为产品失败证据。

`manual-replay-ruff.log`、`manual-replay-types.log`：定向检查通过。这里的“真实”只指真实SQLite和HTTP，不含浏览器人工继续。没有将当前 resume_queued 摘要认定为实际CoreRun恢复；End错误后的人工状态持久收敛及真正运行接入仍在A-01未完成范围。
