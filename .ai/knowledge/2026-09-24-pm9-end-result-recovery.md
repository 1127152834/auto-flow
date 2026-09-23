# PM9 End 原结果与关联修复

日期：2026-09-24。状态：in_progress（缺陷及定向结果confirmed，新包/全量待结果）。来源：现有生产脚本、End/Save账本、TaskEndPanel和运行日志。

已有脚本已经验证过保存成功后仅修复不重跑、不增代次、不改Run历史；XE-C10台账仍只指向合同夹具，须按实际证据补映射。DATA-E2E-02还缺记录来源的真实登录修改/再保存/新代次恢复组合。

本轮发现：组件只依赖本地mutation结果，重开页丢修复入口；误把外层End ID发给只接受保存ID的修复接口；默认replaceAllowed=true且回退到全部输入会遗漏新建目标。已按既有End范围增加只读恢复契约，恢复内部保存ID和原目标，明确替换授权，保持原失败操作与当前关联阶段分离。修复冲突后再提交必须使用最新响应版本，已有RED证明旧版本2被再次发送，现已修复。

记录目录 `.tmp-tests/pm9-end-link-repair-2026-09-24/`。初始后端GET405、刷新组件无修复按钮、recordTargets缺失/默认强替换、修复版本未更新均有RED。定向25后端/10前端通过；首轮后端全量在发现更多同链缺陷后主动SIGINT取消（精确核对PID与工作区），该轮及取消时pytest清理异常不能算产品通过或产品失败结论。候选稳定后重新运行。

首轮打包失败诊断：backend:build成功，但package:dir仅electron-builder，不执行electron-vite build；out/renderer中缺少新恢复/授权文本，截图仍旧cleaned提示无入口。该轮不能当作新前端回归结果。补显式npm run build后重新package，并核对实际asar前端内容，再跑完整桌面。原desktop/22图及日志保留。

新包desktop-final完整通过26截图，两张End修复/重开图已目视核对；输入环境g1/session1→实际网页修改9→End更新g2→第三Task恢复g2/session9，原RecordRef/完整记录不变，旧代次发布拒绝。原失败Run/End保持failed、仅child关联phase完成，不增加环境/代次/节点。该包早于下面两项最终审查修复，不能替代最终候选重验。

独立只读审查发现两个P2：多目标逐个冲突会回退之前已确认的版本；child已保存但parent outcome仍空时仍显示保存入口。分别以组件RED复现（1失败/4通过、2失败/5通过），以按记录身份累计revision及当前child phase判定修复；未知/失败查询也禁止保存。复审无新P1/P2。第一次相关回归13通过/1失败是Task页面公共夹具漏新增GET产生第二alert；补null契约后原断言不变，最终14通过/2文件/3.40秒，类型与lint通过。

最终前端显式build/package已完成；后端完整回归仍运行，前端全量/最终桌面重验继续。GitHub CLI Actions访问恢复，旧35902129697仍是旧源码结果；将在固定候选后单次调度新矩阵。251条212partial/39planned/0verified，249有断言/2未定位；releaseAccepted=false。当前专项报告end-link-repair-follow-through.json记录精确范围和未完成检查。
