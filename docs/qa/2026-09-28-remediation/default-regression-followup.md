# QA-01 默认回归续验

日期：2026-09-28；状态：confirmed（限定下述范围）。来源：当前完整 pytest 的原始日志/XML、实际入口代码和针对性复测。置信度：高。

本次完整默认后端：4267 passed / 5 failed / 44 skipped，1327.04 秒；见 backend-full-current.log 与 XML。这轮开始于元数据后续修正之前，因此不是最终稳定版本验收。44 跳过包括43个需要真实浏览器的用例和1个显式付费模型用例；后续真实浏览器补跑另计。

| 失败 | 分类、根因与处理 | 修复证据 |
| --- | --- | --- |
| required fields / scope 两项 | 本轮新增 project_data 后两处遗漏的216数量断言。改为217，并额外断言原生节点身份及项目数据参数规则；不只改数字 | backend-full-followup-fixed.log |
| CSV差分两项 | 历史源仅表头和空表头返回一条记录是 N-01 已批准修复。保留冻结源的完整旧包络断言，同时完整断言目标返回0行。其余差分仍逐字比较 | 同上；真实 worker 的 N-01 证据仍见 nodes.md |
| project proxy location worker退出 | 两轮组合均在收到成功/清理包络后0.5秒等进程退出超时。入口模块在worker分派前导入整个 sidecar 应用，所有worker/脚本承受无关应用装配导入 | worker-entrypoint-before.log 红；after.log 15通过；原0.5秒门槛未改 |

入口最小修正只有将 create_app 导入移入正常 sidecar 分支；现有调用行为与异常启动不发ready断言保留，新鲜 Python 子进程验证 worker 入口不导入 sidecar。组合259项通过（backend-full-followup-fixed.log），包括原来五个失败的所属测试文件。

probe_worker_exit.py 使用真实worker管道、合成代理服务，仅测进程退出，不证明供应商操作。默认生产3秒预算下三次从 finished 到全部清理的样本：修正前0.450/0.593/0.474秒，后0.223/0.197/0.239秒；这包含清理耗时，不能解释为纯解释器退出耗时或性能承诺。原测试仍用0.5秒，保持成功断言、输出断言和回收断言，没有延时放宽。

Ruff 从 CI 相同 apps/backend cwd 运行通过；根目录直接调用ruff会对first-party分类不同，失败记录 worker-followup-ruff.log 保留，正确入口见 worker-followup-ruff-correct-cwd.log。普通mypy入口检查见 worker-followup-mypy.log。OpenAPI check通过。最终全量和打包仍在进行，不将定向通过扩写为完整默认通过。
