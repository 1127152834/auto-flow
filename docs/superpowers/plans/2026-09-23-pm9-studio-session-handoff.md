# PM9 W1–W3 实施切片

日期：2026-09-23。状态：proposed，等待规格确认。依据：[W1–W3规格](../specs/2026-09-23-pm9-studio-session-handoff.md)。基于632caf6d，不改主目录、不合并、不发布。

| 顺序 | 垂直切片 | 复用入口 | 验证与交付 |
|---|---|---|---|
| W1a | 可选项目目标与单会话打开/确认契约 | shared/automation-studio、preload、StudioWindowController、现有project automation及workflow读取服务 | 先反例：重复打开/迟到回执/错误项目或workflow/工作区更换；主进程和契约检查 |
| W1b | 项目详情编辑入口、关联抬头和返回、带未保存保护的载入 | AutomationDetailPage、StudioApp、WorkflowOpenDialog、现有draft protection | 组件→页面；真实打包Manager选指定自动化、编辑并条件保存；失败保留旧草稿；验证独立文档所有权不改变 |
| W2a | 绑定会话复用项目批次启动和原操作恢复 | 现有project automation运行配置、批次HTTP、操作账本 | 保存失败不启动；响应丢失查原键；权限/冻结版本不由renderer替代；真实worker只一次执行 |
| W2b | 两窗口共用Task证据与人工状态 | TaskDetail及证据/人工组件、现有API/事件游标 | 实际waiting→同Run继续→End；两窗口相同ID/终态，关闭重开不新增Run，不扩展跨进程恢复 |
| W3a | 单一会话presentation切换与失败回退 | 原窗口控制器、离开协调、现有Studio组件/主题作用域 | 同文档CSS共存先验证；明确快照字段和代次；取消/装载失败/过期确认保持原会话可编辑 |
| W3b | 停靠/弹出UI及平台收口 | Manager布局、Studio宿主、既有平台适配器 | 编辑历史/viewport/选择保持、Run继续不重放、工作区切换受控；最终完整回归+单次三平台CI；实机缺项明确保留 |

每片目标30–90分钟形成可检查增量，较大的W3按a/b拆分；没有界面/运行证据不得宣称完成。代码前先锁定具体契约和现有消费者；能复用原服务/组件就不另建Session后端或执行器。中间定向测试，候选稳定后才全量验证，避免每片重跑三平台全矩阵。

批准前可继续：现有独立窗口复用、关闭取消/保存/重开、同服务和无重复Run的打包测试；其证据与W1–W3实现缺口分开记录。外部实网、签名与物理平台条件另见PM9 completion-gaps。
