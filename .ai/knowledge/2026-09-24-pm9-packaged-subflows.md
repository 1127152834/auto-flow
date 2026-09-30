# PM9 打包子流程公开 HTTP 联合验收

- 日期：2026-09-24
- 状态：confirmed（已通过打包 sidecar 子范围）；完整桌面结果和后续 CI 以专项报告为准
- 来源：`scripts/project-runtime-smoke.mjs`、正式 ARM 打包 sidecar / HTTP / 真实 worker / CloakBrowser
- 生产源码：`69baeeb295d3cf2e10ceba945d00bfd138907a50`；本轮仅补验收脚本与证据，没有修改业务实现

旧 S1 真实 worker 的冻结/取消测试在进程内包裹 worker.run 和 capability handler。它能证明相应源码边界，但不能单独证明打包公开命令链。新场景复用现有运行脚本，通过真实人工等待形成确定时序，不替换生产 handler，不改 SQLite 或执行内容。

1. 批次两个 Task 均先进入人工等待；在首个等待时通过 `/api/workflows/{id}` 修改子节点原文档并确认 revision 增加，再经人工继续接口恢复。两个 Task 分别调用同一子图两次，四条记录仍是 frozen-first/frozen-second，没有使用新源文本；每次调用有独立 nodeVisitId，父 privateValue 不被子 privateValue 覆盖；根 End 将每个 Task 的两个返回记录关联到各自环境。
2. 子图写第一条记录后进入人工等待，通过公开父批次 stop 命令取消。Task 为 cancelled、人工项为 cancelled；已提交记录保留且未关联环境，后续写节点与根 End 均没有 attempt。
3. 父节点有字段 B 写权限且成功提交，子节点只声明字段 A，却试图写 B。真实 worker 的子节点返回 CAPABILITY_SCOPE_DENIED；仅父节点的一条记录保留，End 未执行。证明子节点不会借用同 Task 的父节点较宽字段授权。

原 run 验收助手假设所有节点只能访问一次，不适用于正常重复子调用。改为默认仍精确一次，只有本场景声明的 child-private/child-write 必须精确两次，并校验声明访问不能缺失；各 Task 另检查两个唯一 visit 和成功状态。人工 stop 与 resume 分开计数，不把取消误记为继续。

范围限制：这是实际打包 HTTP/worker 命令链，不是新增子流程 GUI 入口。生产代码未变，当前69baeeb2矩阵35886627514继续，未因附加断言重启；该矩阵没有包含新增打包脚本断言。其他资产、Profile/代理组合、外部授权、实机及完整发行门禁仍保留，不升 verified。原S1受控撤销测试仍负责“已在途迟到写入被拒绝”的直接断言，新公开stop场景证明等待点撤销后不发起后续写入，二者不混称。

最终完整ARM桌面通过（21张截图，含最终精确访问计数断言），原始报告 `.tmp-tests/pm9-desktop-subflows-2026-09-24/project-desktop.json`。完整打包sidecar API/服务重启报告 `.tmp-tests/pm9-packaged-subflows-final-2026-09-24/project-api.json`。101脚本、4映射校验通过，覆盖状态不变。当前三平台35886627514继续验收69baeeb2生产代码；本轮没有业务代码变更，不重复已有全量后端/前端构建。
