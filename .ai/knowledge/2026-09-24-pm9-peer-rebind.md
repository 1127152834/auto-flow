# PM9 同行改绑与当前代次领取

日期：2026-09-24；状态：confirmed，本机子范围。来源：DATA-CLAIM-09原始规则、公开HTTP/SQLite/真实浏览器worker断言；Google transport和凭据为受控夹具。

2026-09-24 同行改绑补证（confirmed局部）：公开A→B→A身份列替换产生新代次/epoch；异namespace时断网和完整本地拉取均拒绝领取。修复完整拉取后两真实worker各冻结正确当前代次/原值，人工继续各写一版本和一pending意图，零远端写入、旧失败批次不重启。最终相关3 passed/7 deselected/2 warnings（32.46秒），Ruff通过；CI原选择collect34/45且含新用例（非运行）。仅关闭DATA-CLAIM-09已列明的test_missing，保留生产/外部缺口；总计249/2、206partial/45planned/0verified，缺口计数241生产/16实现/9测试/24外部（可重叠）。本片无生产修改、不重复全量和打包；新原生运行仍待认证，releaseAccepted=false。详见peer-rebind-follow-through.json。

首次错误为断言将展示DTO的writable与快照DTO的fieldName直接比较；改为严格字段ID/值映射，负向日志保留，不称产品RED。Ruff要求轮询lambda显式绑定循环变量，修改后重跑三项相关真实worker均通过。

审查裁定：已列明的同行移除、改绑、namespace和当前代次场景现有直接断言，故只删除DATA-CLAIM-09的test_missing分类；不声称穷尽所有排列，完整生产链和外部门禁保留。生产仍1c676965，旧全量3493/ARM包22截图与旧CI均不包含新测试；后续认证恢复后仅触发一次最新候选all矩阵。报告含测试和原始日志SHA256。
