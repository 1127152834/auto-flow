# 批次逐项结果与镜像未知拉取核实

- 日期：2026-09-24；基线5210e388加本轮[四份候选源码](2026-09-24-item-results-image-recovery/candidate-hashes.json)。状态：软件与完整前端门禁 confirmed，真实桌面 blocked。
- 规格复核确认原T13.4“逐项结果已通过”范围过宽：此前只有批次总状态与失败名。本轮补齐实际冻结结果；T09页面也补接已有POST核实契约。没有增加后端接口、数据库schema、依赖或工作流入口。

## 行为与 RED → GREEN

1. 批次结果直接使用服务端冻结的 `result.items`，逐项显示名称/ID、成功、排队、容量等待、设备等待、已准入、结果未知、失败或取消，以及已有错误和重试来源。筛选到零台仍保留原批次条目，不按当前设备列表重建结果。
2. `accepted` 显示“已准入，执行中”，不误报未知；提交和新批次入口继续冻结。真正 needs_verification 仍只通过显式核实处理，取消范围不变。
3. 镜像用户点击核实后先GET原请求；若needs_verification，调用现有 `api.verify(operationId, {requestId: 原编号})`。核实失败保留该操作和原编号，重试核实不重放pull；成功刷新目录。
4. 连续拉取时优先核实当前冻结请求，成功只清除匹配的ref。A成功后B响应丢失，核实B失败再重试仍使用B，不能用A的成功结果释放B。

实现前[4 failed / 42 skipped，3.50s](2026-09-24-item-results-image-recovery/initial-red.log)，分别证明缺逐项结果、accepted误报、未知拉取未调用POST（含重试场景）。首次关联回归[1 failed / 66 passed](2026-09-24-item-results-image-recovery/superseded-accepted-assertion.log)是旧测试将accepted当成未知；依据后端实际语义改为检查执行中/取消条目，保留禁止新批次和不重放断言，没有删除未知安全测试。

独立复审再发现连续拉取身份问题；新增[1 failed / 7 skipped，1.62s](2026-09-24-item-results-image-recovery/second-request-red.log)，实际GET参数为A而期望B。两行身份选择/匹配修复后，最终[Android 14文件 / 166 passed，7.39s，类型与lint通过](2026-09-24-item-results-image-recovery/focused.log)。最终独立只读复审无剩余Critical/Important，范围限本次四文件。

```sh
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- src/renderer/domains/android && npm run typecheck && npm run lint'
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- --maxWorkers=1 && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
```

[完整前端门禁](2026-09-24-item-results-image-recovery/full.log)实际exit 0：424文件/5656 passed，750.46s；类型、lint、OpenAPI与构建通过，renderer 34.98s。后端产品源码未变；[真实回执中断与HTTP核实](2026-09-24-image-pull-interruption.md)已经验证该接口的持久性与原编号保护，但不等于新页面已实机通过。上一提交完整后端4048passed/26skipped仍仅用于其未变后端范围。

## 保留的边界

- 真实页面逐项呈现、取消/新批次及镜像核实受Mac锁屏blocked，需手动解锁后运行；组件测试不代替桌面证据。
- 后续只读审查确证应用重启后历史未知拉取缺少页面发现入口，属于待实现Important软件缺口；新修复解决当前页面冻结请求的核实，不宣称整个T09完成。桌面镜像内容删除、下载途中网络中断、T14/T16前台与隐藏页实测仍待运行。
- 早前结构/脚本测试还产生一份无关capabilities.json差异，已确认由inventory脚本生成，恢复到本轮开始的HEAD字节；[差异留档](2026-09-24-item-results-image-recovery/script-generated-capabilities.diff)。三份原有Studio脏文件继续保持原哈希、不纳入提交。
- 全分支最终验收、十台容量、GApps条件及历史RED缺证保持单独状态，完整目标未完成。
