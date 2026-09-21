# 来源业务格式错误保留：待确认契约

日期：2026-09-22。状态：proposed。来源：DATA-TABLE-02/STATE-08/SH-05、真实 HTTP/SQLite + FakeSheetsTransport 的 number 映射文本反例。

当前 Sheets 新行被严格本地值校验以 422 拒绝；Excel 相同处理已读代码、未实测。当前已有坏业务值的状态操作测试使用显式数据库 fixture，不冒充来源保留验收。D1 规格/切片见 docs/superpowers/specs/2026-09-22-pm9-source-business-validation.md：只保留安全 Scalar 的普通业务格式问题，身份与写入/执行契约继续严格，问题基于当前字段派生、不增加错误账本。此 DTO/来源发布/UI 联合能力超出已批准 C/R 附录，等待确认；C/R 当前验证与草稿 PR 收尾继续。
