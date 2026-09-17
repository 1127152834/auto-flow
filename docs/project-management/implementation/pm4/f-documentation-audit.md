# PM4-F 公共文档与覆盖账本审计

日期：2026-09-16
前一视觉候选证据提交：`b4dabf28b8be3ce5bbee5c321c9f2801dc328ea8`
前一视觉候选产品源码：`c911b6acfc21b622904357ec126baba2bccb4b2f`
当前文档基线：`f07bb83b46041fcc5ede7a957809834046872014`
交付状态：`delivered`；验证状态：`partially_verified`
边界：**管理侧通过，真实执行核心接入待验收**

## 1. 权威证据与版本边界

| 证据 | 结果 | 版本与边界 |
|---|---|---|
| `pm4/qa-runs/f-QHALLW/result.json` | 当前源码的第二自动化、有限/不限调度、停止、三类候选态、日志搜索 Enter 和数据传递管理链通过 | 产品源码/HEAD `f07bb83b`；source SHA-256 `71623bf3…`；真实 Electron、FastAPI、SQLite、领取和项目数据能力；executor=fake，browser/studio=notExecuted |
| `pm4/qa-runs/f-4QcXFG/visual-review.json` | 前一提交候选 `passed`；19 张截图；强制结构通过；每屏最低分 85 | 产品源码 `c911b6a`；顶部导航、暖灰/黏土棕、细网格表格、小圆角、三类候选态、日志搜索 Enter、1440×1024 与 200% 缩放通过；不能替代当前源码截图复审 |
| `pm4/verification.json` | PM4 机器核验汇总 | 当前源码/HEAD `f07bb83b`；当前管理链已通过，视觉复审和阶段全量检查均已通过；PM3 管理端前后端定向回归通过，真实执行核心 PM3 QA 未执行 |
| `docs/migration/project-data-directory-qa/run-A6Nzd9/result.json` | PM2 数据目录/记录回归通过 | 真实 renderer UI、HTTP 与 SQLite；具体注入边界以该报告为准 |
| `docs/migration/pm2-detail-qa/run-5r0BCW/result.json` | PM2 文件与详情回归通过 | 10,000 行导入 7,211ms，第二页 169ms；系统文件面板结果为测试注入，renderer UI、IPC 证明、HTTP、SQLite 与 workbook I/O 为真实 |

历史 V1/A/B/C 文档继续保留：`v1-verification.md`、`a-verification.md`、`b-verification.md`、`c-verification.md`。`f-dJVKnL` 为历史候选；`f-4QcXFG` 是已完成视觉复审的前一提交候选；`f-QHALLW` 是当前源码业务 E2E 权威。历史失败目录和前一候选不能覆盖当前源码业务事实。

## 2. 最终管理链事实

1. Electron UI 创建项目、人员/邮箱/账号三张表、必要字段、人员/邮箱记录和业务状态。
2. Electron UI 创建首个自动化及两个 `independent + required` 输入。
3. 有限三次运行复用同一人员，领取三个不同邮箱，显式将邮箱改为已使用并新增三个账号。
4. 不限次数运行完成两个任务后由 UI 主动停止；领取门关闭，累计五个邮箱已使用、五个账号，账号无重复。
5. Electron UI 创建第二个账号读取自动化，将账号表设为唯一必填输入并启动任务。
6. 第二自动化读取第一自动化新增的账号；任务页展示不可变原始输入和真实读取事实，账号总数保持五条。
7. 响应丢失使用原操作身份找回，未重复新增。

这组事实证明管理页面、接口、SQLite 数据、领取、数据操作、运行投影和恢复闭环；它不证明生产工作流执行核心或真实网页动作可用。

## 3. 契约与交付包

| 契约/包 | 已交付事实 | 保留边界 |
|---|---|---|
| PM4-A / XE-C04 | 输入关系、必要/可选、候选回溯、typed lease、全组原子提交、候选续查及错误分类；F 跨包链复验有限/不限领取 | Sheets 物理来源排他身份在 PM6；真实生产执行核心未验收 |
| PM4-B / XE-C08 | 冻结读取授权下的记录读取/查询返回稳定快照；查询不自动授予写权；第二自动化读取已提交账号 | fake executor 调用真实 capability 端口；生产核心调用未验收 |
| PM4-B / XE-C09 | 本地记录、状态和字段显式操作；动态 lease、CAS、稳定引用、幂等结果和 Task 写游标 | 环境关联在 PM5、Sheets 在 PM6；生产核心调用未验收 |
| PM4-C | 有限/不限、并发容量、失败策略、暂占/耗尽、停止门闩、释放、恢复、撤权和工作区隔离 | 三类候选态管理页已通过；PM3 管理前端定向回归通过，真实执行核心 PM3 QA 未执行 |
| PM4-F | 第二自动化、候选版本跨包 E2E/全量工程检查、PM2 回归、19 屏视觉审查和手测说明；候选后两项 lease 保护修复完成定向回归 | 当前源码 PM4-F 管理链已重跑通过；19 张截图同视口视觉复审和阶段全量检查均已通过；PM3 管理端前后端定向回归通过；真实执行核心 PM3 QA 未执行；真实执行核心、浏览器、Studio、Windows/packaged 和用户手测未执行 |

XE-C02/C05 的 PM3 历史实现没有因 fake executor 验证而升级为生产核心数据能力。`coverage.json` 中 PM4 里程碑使用 `delivery_status=delivered` 和 `status=partially_verified`；跨 PM5/PM6/PM7/PM8 的规则没有被提前标为 verified。

## 4. FX 样例映射

| Fixture | PM4 证据 | 尚未覆盖的跨阶段边界 |
|---|---|---|
| FX-01 | 同一人员释放后连续用于有限三次，并在不限链再次使用；由 UI 停止 | 环境绑定属于 PM5 |
| FX-02 | 人员 + 邮箱多表输入，邮箱显式改状态，账号新增；第二自动化读取新增账号 | 真实生产执行核心和真实浏览器动作未执行 |
| FX-03 | A 的同表角色、sameRecord、typed lease 合并与回溯自动反例 | 未作为最终 Electron 独立画面执行 |
| FX-04 | B 的 Task 自写推进版本、人工新值冲突、响应丢失幂等和前序事实不回滚反例 | 部分冲突只由自动集成验证 |
| FX-05 | 不属于 PM4 | PM5 planned |
| FX-06 | 不属于 PM4 | PM6 planned |
| FX-07 | 不属于 PM4 | PM5/PM7/PM8 planned |

## 5. 候选版本工程与视觉检查

- 后端：当前源码 1,597 passed、8 skipped；Ruff 通过；mypy 260 个源文件通过。
- 前端：298 个测试文件、3,273 项测试通过；OpenAPI、typecheck、lint、build、test:structure 通过。
- 脚本：补齐被 Git ignore 的 WebRPA 冻结清单单文件后，test:scripts 64/64 通过。
- 回归：`smoke-project-data` 与 `smoke-pm2-detail-flows` 通过，证据见第 1 节。
- 视觉：19 张截图，强制结构通过，逐屏最低 85；三类候选态与日志搜索 Enter 已通过；无整图平均分替代单屏验收。

当前源码已重新运行全量后端测试与相关前端、脚本检查。当前业务 E2E `f-QHALLW` 使用源码 `f07bb83b`，source SHA-256 为 `71623bf3d45b28912bdafdd9e97cbef119f246c05ad307bc4d98eabf6c4758cb`；其 19 张截图同视口视觉复审已通过。前一视觉候选 `f-4QcXFG` 使用产品源码 `c911b6a`，source SHA-256 为 `e09446d047edd73f832476a491aef5b42a926a41872de51da696b57a32c33c0d`；权威证据没有记录独立构建制品 SHA-256，不进行推测。

候选后有两项数据保护修复：`d3a397cf` 使人工删除在影响预览和最终事务中阻止 `held/reconciling` lease，82 项主测试及 15 项相关回归通过；`f07bb83b` 使 Excel 重新导入在预览、接受和最终发布中阻止当前数据代次的活动 lease，7 项新增测试及 117 项相关回归通过。另有 PM3 管理后端定向回归 139 项通过，伴随 2 个既有依赖弃用 warning；前端定向回归 16 文件/121 项通过。当前源码 PM4-F 管理链、19 张截图同视口视觉复审和阶段全量工程检查均已通过，管理侧 F 当前源码退出条件齐全。

## 6. 仍待验证

- PM3 管理前端定向回归已通过 16 文件/121 项，管理后端定向回归 139 项通过；`qa-project-management-pm3.mjs` 会启动真实 CloakBrowser/生产执行核心，按本轮边界未执行。
- 真实生产执行核心、CloakBrowser、Studio 联合运行。
- Windows、其他 CPU 架构和打包应用。
- 用户按 `manual-test.md` 执行的手动验收。

因此 PM4 管理功能可以标记 delivered，验证保持 partially_verified；当前源码管理链、同视口视觉复审和阶段全量检查均已通过，管理侧 F 退出条件已经闭合。真实执行核心 QA 仍未运行，因此不能声明生产执行门槛满足或生产工作流/全平台可用。

## 7. 文档静态检查

本次只检查公共文档：`coverage.json`、`verification.json` 及所引用结果 JSON 可解析；内部 Markdown 链接与四组权威证据路径存在；48 项功能/178 条验收场景/25 项契约与门槛/30 个交付包的编号集合不变且无重复；五个明确未交付条目没有 PM4 证据；`git diff --check` 通过。静态检查不替代业务测试。
