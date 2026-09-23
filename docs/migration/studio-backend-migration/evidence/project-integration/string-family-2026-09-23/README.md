# 项目任务纯文本节点族（2026-09-23）

- 范围：`regex_extract`、`string_replace`、`string_split`、`string_join`、`string_concat`、`string_trim`、`string_case`、`string_substring`。八个节点均属现有 213 节点范围，Studio 执行器已从冻结 WebRPA 迁入；本批只打开项目任务目录，不新增执行器或资源协议。
- 源码行为对照：`tests/differential/workflows/test_b4_data_structure_executor_parity.py` 146 项通过，覆盖原版输入、输出和错误分支。
- 项目真实 worker：一条八节点顺序流程完成正则、替换、分割、连接、拼接、去空白、大小写和截取；八项输出与持久事件逐一相符，未请求浏览器资源，worker 清理完成。对应 `test_project_task_executes_string_family_in_real_worker`。
- 关联 `test_project_data_worker.py`、`test_project_run_start.py`、`test_project_graph_executor.py` 共 47 项通过；Ruff、mypy 与 OpenAPI 一致性检查通过。项目任务目录从 57 增至 65 个已接入入口，Studio 范围仍为 213 个。
- 边界：当前只核销后端项目任务接入；正式 Electron 中八节点组合及最新冻结包尚未实测，不能由 worker 用例代替。其他纯数据族和 213 节点整体状态不随本条关闭。
