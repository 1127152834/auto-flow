# PM9 已绑定工作流去向审计

2026-09-24 AU-08已有绑定去向勘误（confirmed实现缺失，W1c proposed）：HTTP/真实SQLite诊断证明重复关联409且仅保留原自动化，但错误未给出原projectId/automationId，前端也无定位入口；不是只有缺测试。既有11项契约/仓库测试通过（2依赖警告/1.62秒）不证明该条件。新增可重复诊断、错误分类及W1c契约/界面/并发与失效目标验收切片，随现有W方案等待确认；未修改生产代码，不重跑全量/打包/流水线。251条状态、241生产/19实现/8测试/24外部计数不变，releaseAccepted=false。见binding-destination-audit.json。

来源：`SqlAlchemyProjectAutomations.create`、`AutomationDetailPage`、AU-08原设计；运行命令与SHA256见 `docs/project-management/implementation/pm9/binding-destination-audit.json`。探针退出0只表示诊断完成，destinationProvided=false必须保留为缺失事实。首次create状态码和外部脚本导入路径错误只属于夹具修正。

W1c不开放Studio全部节点、不改变工作流所有权、不删除唯一性保护。批准后最小动作是先写同/跨项目重复绑定及并发契约反例，再复用现有结构化错误和离开保护贯通界面。I1–I3持久身份反例、其他已提出架构与外部原生/实网条件继续未闭合。
