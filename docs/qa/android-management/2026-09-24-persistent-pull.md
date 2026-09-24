# 重启后持久未知镜像拉取恢复

- 日期：2026-09-24，基线 `30ffd12f` 加[候选哈希](2026-09-24-persistent-pull/candidate-hashes.json)。状态：软件与真实 HTTP confirmed；桌面 Mac 锁屏 blocked；AM2 整体仍 partial。
- 规格：AM-R04。先完成[有界计划](../../superpowers/plans/2026-09-24-android-persistent-pull-recovery.md)，保留原三份 Studio 脏文件。Operation 数据模型及迁移无变化；新增现有 GET operations 的 action/state 可选筛选，OpenAPI 客户端同步生成。

## 实际行为

镜像页按工作区/服务实例读取待核实拉取并分页展示；重建页面仍可找到旧编号。核实仅由用户点击触发，使用原 requestId/operationId；成功后刷新目录和待核实列表。列表不可读、读取中或仍有未知记录时暂停新拉取。本地响应丢失仍冻结编号及引用；只有明确的 `422 VALIDATION_ERROR` 前置校验拒绝释放输入，不能把普通 4xx/404 当未执行。服务实例切换通过 scoped query key 和组件重建隔离旧记录。

后端 items、total 和 cursor 都应用同一 workspace/device/action/state 范围；其他工作区、其他操作类型或其他状态的游标返回 422。游标记录被核实后失效时，页面可重新读取返回首页。

## RED → GREEN 和命令

```sh
uv run --project apps/backend pytest apps/backend/tests/contract/test_android_management_operations.py apps/backend/tests/integration/test_android_management_operations.py -q
npm exec --offline --yes --package=node@22.23.2 -c 'npm run openapi:generate'
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- src/renderer/domains/android && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
uv run --project apps/backend python docs/qa/android-management/scripts/image-pull-interruption-smoke.py --allow-image-pull --output docs/qa/android-management/2026-09-24-persistent-pull/real-result.json
```

- 后端最初测试误用了不存在的 recover_interrupted 方法（测试搭建错误，不算有效 RED）；改为现有 recover_running 后，真实 [RED 1 failed / 27 deselected，0.48s](2026-09-24-persistent-pull/backend-red.log)，total 实际4而期望2。修复后[34 passed / 1既有warning，6.43s](2026-09-24-persistent-pull/backend-green.log)。
- 前端入口与读取失败保护[RED 2 failed / 8 skipped，3.47s](2026-09-24-persistent-pull/frontend-red.log)。首轮关联测试[3 failed / 166 passed](2026-09-24-persistent-pull/fixture-failure.log)，根因是三个独立HTTP fixture对新增分页查询错误地返回数组；补齐实际契约对象，没有放宽产品断言或隐藏错误。
- 独立审查发现422拒绝仍冻结输入；新增[RED 1 failed / 11 skipped，1.17s](2026-09-24-persistent-pull/422-red.log)，仅修复明确未接受的校验错误，再补断线继续冻结及动态游标恢复回归。
- 最终[14文件/171 passed，7.12s](2026-09-24-persistent-pull/final.log)，typecheck/lint/OpenAPI/build全部exit0，renderer构建36.58s。后端修改文件Ruff及compileall exit0。最终增量只读复审无剩余Critical/Important；审查没有声称实机页面通过。

## 真实 macOS / Lima 证据

[实际 JSON](2026-09-24-persistent-pull/real-result.json)、[输出](2026-09-24-persistent-pull/real.log)：独立随机工作区，真实拉取固定官方RepoDigest，目录回执提交后强杀本次服务，HTTP得到RemoteProtocolError。重启后GET筛选列表total=1且原operationId一致；重提原请求不执行pull；显式verify原编号成功，未知列表total=0。两次服务进程合计catalog pull=1，基础tag的本地Id未变，只取消本工作区新登记，既有镜像内容保留，没有创建设备。

这是已完成拉取回执窗口的真实中断与列表发现；不是下载途中断网，也不是Electron页面自动化。分页/跨工作区用真实SQLite+HTTP合同验证，页面重建/分页用组件验证；不把这些等同Mac实机UI。

## 未完成与风险

- AM-R12创建、拉取、备份的磁盘空间预检仍是Important软件缺口，下一任务处理；现有ENOSPC清理仅是失败保护。
- 当前完整前端5656/后端4048的旧报告只覆盖各自先前源码；本次为上述171/34定向门禁，不把旧全量报告当本次全量。
- Mac锁屏继续阻塞真实页面；下载途中断网、同一发布链数据库/旧实例保留、十台容量、GApps条件和全分支最终验收仍保持原状态。102步骤85passed/14not_run/3blocked不虚增。
