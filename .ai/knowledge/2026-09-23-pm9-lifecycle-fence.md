# PM9 生命周期发送围栏补审

日期：2026-09-23。状态：confirmed（L0反例与修复），proposed（L1–L3）。来源：真实HTTP/SQLite/受控Google transport，原始设计DATA-LIFE-01/02/07；报告 `docs/project-management/implementation/pm9/lifecycle-fence-follow-through.json`。

旧 unknown 值发送可被同物理Sheet改绑绕过：改绑202、新generation、随后新值推送，而旧unknown仍存在。新预览和旧预览提交的四反例先失败，改绑目标/原来源及解绑的既有 require_source_idle 加 structural=True 后4通过；独立审查无P1/P2。它不改变读/领取/普通发送路径，也不提供永久失权逃生入口。

原系统UUID阻断测试改为先获取有效预览再制造未知发送，保留提交拒绝的直接断言，单项通过；整组回归单独记录。旧c2 CI因新生产候选被替代，不能算L0验证。

连接只有新增/删除、无主体证据修订；普通put_binding无条件新generation，因此LIFE-01/02分别有实现缺失。L1原位重授权、L2同物理源主体替换、L3发送者退出证明及未知隔离的规格/切片已准备并请求一次新确认；未获批前不实现新能力。C/R/D1授权及L0安全修复继续。243有断言/8未定位、202partial/49planned/0verified，releaseAccepted=false。
