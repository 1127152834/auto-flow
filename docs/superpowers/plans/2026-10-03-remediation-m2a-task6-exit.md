# M2A Task 6：配置 schema 与 M2A 退出

- 日期：2026-10-03；状态：confirmed（本机 Windows 验证；macOS 由用户手动验证）
- 规格：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-11、R2-12；计划：[M2 计划](2026-09-30-remediation-m2-business-model-reliability.md) Task 6

## 做了什么

1. **R2-11 配置 schema**：`application/workflows/config_schema.py` 从执行器源码推导"实际读取的配置键"
   （`config.get/[]/in`、`helper(config, "k")`、键元组循环、跨模块 helper 递归）。
   - 运行时只读生成快照 `config_schema_snapshot.py`（推导约 1.3 s，不放进每次运行）；
     Studio 读生成的 `domains/workflows/generated/executor-config-keys.json`。
     `python -m autoflow.bootstrap.executor_schema_export [--check]` 生成/校验两份；单元测试保证与源码一致。
   - 现存"面板有、后端不读"的键冻结在 `config_schema_debt.py`：`PANEL_ONLY_KEYS`（来自字段清单）
     与 `EDITOR_DEFAULT_KEYS`（新建节点自带的默认键）。两个测试做精确比对，只能减少；新增即失败。
   - 预检：项目运行在节点开始时、Studio 在运行前，对"执行器不读、也不是面板已知字段"的键发警告（不阻止运行）。
     新建任何节点都不产生警告（前端测试逐类型验证）。
2. **R2-12**：统一"出错时"控件已覆盖全部入口，删除 M1 隐藏开关 `featureFlags.nodeRetryPolicy`
   及其背后的旧重试/超时动作控件和块视图旧弹窗；旧文档行为不变（旧键仍只作为迁移候选）。
   旧设置提示改为指向"出错时"里的转换建议。
3. **G3 xfail 转正**：黄金场景 harness 明确 `executionMode=realWrites`（调试选择批次默认是预览，
   预览不进入生产台账——这是 R2-30 的正确行为）；丢响应提交后台账为 `needs_review`。

## AC 逐项（M2A 范围）

| AC | 证据 | 结果 |
|---|---|---|
| AC2-01 | 退避/预算/隔离：`test_record_ledger_claims.py`、`test_record_ledger_rules.py`；一万行 native-batch-v1 吞吐归 Task 11 | 规则通过；一万行规模见 Task 11 |
| AC2-02 | `tests/golden/test_g3_form_entry.py`（真实 CloakBrowser，含 needs_review）、`test_record_ledger_claims.py` 三种领取模式 | 通过（golden 4 passed） |
| AC2-03 | `test_record_ledger_projection.py`（End 业务失败→skipped，批次继续） | 通过 |
| AC2-04 | `test_node_error_policy_runtime.py`、`test_side_effects_and_failure_category.py` | 通过 |
| AC2-05 | `test_batch_circuit_breaker.py`、`test_circuit_breaker.py` | 通过 |
| AC2-06 | `test_record_ledger_claims.py`（隔离仅限身份可信主行，Sheets 门禁不放宽） | 通过 |
| AC2-10 | `test_config_schema.py`、`unknown-config-keys.test.ts`、`catalog-field-contract.test.ts` | 通过；存量债务冻结只减不增 |
| AC2-11 | `test_project_run_data_start.py`、`test_record_ledger_claims.py` | 通过 |
| AC2-12 | `test_record_ledger_rules.py`、`test_record_ledger_repository.py` | 通过 |
| AC2-13 | `test_record_ledger_projection.py`、`test_processing_units_http.py` | 通过 |
| AC2-14 | `test_record_ledger_claims.py` | 通过 |
| AC2-15 | `test_error_policy.py`、`common-advanced-config.test.tsx`、`test_batch_circuit_breaker.py` | 通过 |

上表测试集合本机：`205 passed`（2026-10-03）。

## 本机未覆盖 / 剩余风险

- 本机已知环境失败（与本改动无关）：Windows 无符号链接权限的用例、缺失 `reference/WebRPA` 冻结源、
  face_recognition 未安装导致的 strict-type 条目、`RuntimeDiagnostics` 日期断言。
- 推导是静态分析：通过 `**config` 整体透传等方式读取的键可能漏报（只会少报警告，不会误报）。
- 债务清单里的键（如 allure `resultsDir/clean`、OCR `language`）按整改规则 1 仍需"读取并测试"或从界面移除。
