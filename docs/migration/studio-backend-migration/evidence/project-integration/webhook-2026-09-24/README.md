# 项目 Webhook 触发接入（2026-09-24）

能力：`node:webhook_trigger`。分类：AutoFlow 必要适配。复用冻结 WebRPA `backend/app/executors/trigger.py#WebhookTriggerExecutor` 已迁入的 `external_http.py` 执行器、原 `workflow_worker` 命令总线、现有项目交互回执与外部 HTTP 路由；没有新增服务器、执行器或数据库迁移。来源及许可证继续由原迁入文件和能力台账追溯，源码使用授权不扩展为商业或公开发布授权。

## 已验证的用户行为

项目已保存流程可以等待 HTTP 触发，验证请求头和参数，将请求数据及原版自动参数变量交给后续节点。子工作流复用同一受管通道，日志带真实子流程作用范围。任务完成、停止或超时后不再接受触发，worker 和运行占用均清理。

- 同一等待请求的并发提交只投递一次；响应丢失后再次调用不重复执行当前步骤。未收到 worker ACK 时返回明确 503，不能把持久化 accepted 回执当作已执行。
- 项目运行之间、项目与独立 Studio 之间若同时等待同一个 webhookId，返回 409，不任意选择接收者。不同循环轮次是原版新的等待，不承诺跨轮次的业务幂等。
- 沿用原四方法、请求体 1 MiB、方法/头/参数验证、自定义响应、默认变量名和自动参数覆盖顺序。外部路由继续不要求 sidecar token，使用节点配置验证；GET 同样会唤醒流程，因此纳入现有停写门槛。
- 验证规则和待处理请求不进入公开交互列表或日志。原版标准认证头过滤沿用；普通自定义请求数据仍作为节点结果，不能将此描述为任意用户数据自动脱敏。

## 测试证据

| 证据 | 结果与边界 |
| --- | --- |
| registration-red.log | 首先证明项目目录未注册 Webhook |
| startup-race-red.log | 23 项通过后，完整 app 停写测试撞到后台调度启动短暂占用；测试改为有界等待门槛空闲，未覆盖或削弱生产计数 |
| delivery-red.log | 先证明传输失败未映射为 Webhook 的未确认错误；修复在现有项目交互边界 |
| integration.log | 首轮最终 26 项通过，31.25 秒；含真实 TCP/SQLite/worker、并发重复、响应丢失、停止/超时、无 ACK、传输失败和停写 |
| regression.log | 扩展子流程后的关联 54 项通过，59.49 秒；含真实项目 TCP/SSE/worker、原 Studio HTTP/worker、输入和 JS 命令、冻结原版差分 |
| admission.log | 48 项项目图输出/准入/目录检查通过，3.57 秒；默认变量、自定义名、空名、敏感变量及实际输出值均有断言 |
| ruff.log / mypy.log | 受影响源码 lint、10 个生产文件类型检查通过 |
| openapi.log / structure.log | OpenAPI 无变更，目录 4 项通过 |
| native-status.json | 本轮 CUA 仍报告 Mac 锁定，未冒称正式 UI 通过 |

分组用例存在重叠，不能累计为唯一用例数。新增真实网络测试使用临时 SQLite、回环 TCP 和实际子进程；受控 transport/状态测试单列于命令测试，不等同原生或正式 Electron 验收。没有修改用户数据库或正在运行的主应用。

## 复现

```sh
apps/backend/.venv/bin/python -m pytest apps/backend/tests/integration/test_project_webhook.py -q
apps/backend/.venv/bin/python -m pytest apps/backend/tests/integration/test_project_interaction_commands.py apps/backend/tests/integration/test_project_interactive_worker.py apps/backend/tests/differential/workflows/test_b6_webhook_trigger_parity.py apps/backend/tests/unit/workflows/test_external_http_executors.py apps/backend/tests/contract/test_workflow_runs_api.py::test_external_webhook_resumes_real_worker_without_sidecar_token -q
```

项目网络测试也接受 `AUTOFLOW_TEST_PROJECT_WORKER=/path/to/autoflow-backend` 验证冻结 worker。父进程仍从源码运行，不能据此声称完整冻结 sidecar 或正式 Electron 入口通过。

## 剩余门槛

项目目录由 188 增至 189/213，24 个入口未注册（包含画布工具）；交互两节点、识别四节点及本节点已实现但正式项目 UI 未完成，仍为 31 项项目接入门槛。该数不等于整体剩余数量。原 22 外部/原生节点、项目生命周期/统计/数据和平台门槛继续分别核销。Mac 锁定仅阻塞原生界面；Windows/macOS Intel 未测。本批未新增产品冲突，默认资源＋显式覆盖、213 范围和14通知排除保持不变。

## 集中快速验收（用户执行方式调整后）

冻结构建160.47秒完成，macOS arm64 unsigned目录包已生成。包内10个完整生产模块与源码一致，包内后端与冻结后端SHA-256一致（`packaged-code.log`、`build-artifacts.json`）。包内真实worker五场景全部通过，25.34秒（`packaged-worker.log`），含子流程、并发提交、响应丢失、停止和超时。父进程仍为源码，未冒称完整冻结sidecar/UI。

用户要求加快集中检查后再次获取CUA状态，Mac锁定已解除；此前锁屏是历史证据，当前正式UI转为待执行，正在使用现有项目交互正式包验收脚本。没有新增生产功能，也不因速度要求省略未验收项。

### 集中验收结果

正式包交互核心链路通过：[formal-project-interaction-electron-u5TFvu](../formal-project-interaction-electron-u5TFvu/result.json)。真实项目UI编排保存、正常关Studio并重开、输入21、原JS Worker返回42且count仅一次、正常关闭主窗口保留脚本、日志/输出持久化、关闭Studio后主窗口恢复均通过。此项核销此前锁屏未能验证的核心链路；原生文件选择、取消/停止组合及其它节点仍按原门槛处理。没有用destroy或直接改Store代替操作。

两次失败证据 `formal-project-interaction-electron-xzQzvh` 和 `formal-project-interaction-electron-BZSuSe`保留。前者脚本使用旧入口名称；后者漏声明count，原版basic.py明确只回写已存在变量。仅修测试：详情按钮“打开 Studio”、真实UI声明数字count=0并新增保存断言；保留21:42:1及次数、生命周期断言，未改生产变量语义。

台账核销快照见acceptance-snapshot.json：213节点的既有后端证据204通过、9待原生验收，639用例槽位630通过/9待验收。这是既有证据核销，不表示本轮全部重跑。项目目录189/213独立记账，未注册24入口中包含画布工具；项目整体不得因此宣称完成。
