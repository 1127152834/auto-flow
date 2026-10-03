# M2B Task 7：流程签名、绑定与可重入迁移（步骤级）

- 日期：2026-10-03；状态：confirmed（本机 Windows 验证）
- 规格：[M2 规格](../specs/2026-09-30-remediation-m2-business-model-reliability.md) R2-18 至 R2-22（R2-23 已在 2721dc06 完成）；AC2-07/08

## 现状（实施前核实）

- 工作流用 `{PROJECT_INPUTS['<inputId>']['values']['<inputFieldId>']}` 引用输入，绑死某个自动化的 inputId/inputFieldId。
- `project_automations.workflow_id` 有唯一约束；创建时省略 workflowId 会生成专属工作流，给出 workflowId 则关联已有工作流。
- 变量解析只支持 `name['a']['b']` 方括号路径。

## 设计

1. **签名**（`domain/workflows/signature.py`）：文档 `content.signature = {inputs:[{key,name,fields:[{key,name,type,required,sensitive,sample?}]}], outputs:[]}`。
   key 稳定（新建建议英文；旧中文 key 保留），name 可改；校验唯一与字符集。
2. **引用**：`{input.<组key>.<字段key>}`、`{input.<组key>}`（整组对象）、`{$record.<字段key>}`（主处理输入）。
   变量解析增加这三种点路径；旧 `PROJECT_INPUTS[...]` 继续可用，直到 M6 迁移门禁。
3. **绑定**（R2-20）：沿用 inputPlan 输入（bindingId = inputId，mode/required/relations/代次/筛选排序不变），
   输入新增可选 `signatureInput`，字段绑定新增可选 `signatureField`。
   启动时若工作流有签名：每个签名输入须恰好被一个输入绑定；必填字段须绑定；缺失时 422，错误指出缺失的签名输入/字段；
   文档里的新式引用必须存在于签名。
4. **敏感**（R2-21）：签名字段 `sensitive` 驱动；对应引用的值进入运行的敏感集合，输出/错误/预览按既有敏感规则遮蔽。
5. **迁移**（R2-22，可重入）：对每个"自动化—工作流"，以自动化输入别名/字段别名生成签名 key；能唯一确认的
   `PROJECT_INPUTS` 引用改写为新式引用并写入绑定；别名不合法/重复、引用找不到、工作流被多个自动化使用等情况只报告不改写，
   旧格式仍可执行。`GET /api/v1/migrations/signature-report` 只读报告；`POST /api/v1/migrations/signature` 执行，重复执行无变化。
6. **复用**：移除 `workflow_id` 唯一约束（迁移 `rm2_workflow_reuse`），允许多个自动化关联同一工作流；
   旧式引用绑定某个自动化的 id，被其他自动化启动时按现有规则明确拒绝。
7. **界面（最小）**：自动化输入编辑器在工作流有签名时选择"对应流程输入/字段"；Studio 插入引用时优先新式引用。

## 不做

- 表达式函数库、批量旧节点转换（M6）；删除旧解析（M6 门禁）。

## 验证

单元：签名校验、引用解析、敏感判定、迁移改写/歧义/可重入。集成：两自动化复用同一签名流程绑定不同表都能运行；缺字段拒绝；
改字段显示名不影响引用；旧格式未迁移仍能运行；迁移报告与重放。前端：绑定选择与校验提示。

## 实施结果（2026-10-03）

- 签名与引用：`domain/workflows/signature.py`、`variables.py`（`input.*`/`$record.*` 点路径，整组敏感按字段判定）。
- 绑定：`inputPlan.inputs[].signatureInput`、`fieldBindings[].signatureField`（规则与 HTTP 契约），启动校验
  `PROJECT_SIGNATURE_UNBOUND/TYPE_MISMATCH/INVALID`、未声明引用 `PROJECT_INPUT_REFERENCE_INVALID`，错误指出缺失的流程输入/字段。
- 敏感（R2-21）：签名 `sensitive` 进入运行敏感集合，`$record`/整组引用同样遮蔽。
- 复用：迁移 `rm2_workflow_reuse` 去掉唯一约束；同一项目多个自动化可关联同一工作流（工作流所属项目查询取一条）。
- 迁移（R2-22）：`application/workflows/signature_migration.py`，同时支持规范形（content）与 Studio 扁平形文档；
  `GET /api/v1/migrations/signature-report`、`POST /api/v1/migrations/signature[?workflowId=]`；重复执行无变化；
  被多个自动化共用且仍有旧引用的工作流只报告不改写；记录身份/版本类引用保留旧格式并计入 remaining。
- 保存兼容：旧编辑器/导入文件保存时不带 `signature` 会保留已有签名，显式 `null` 才删除。
- 界面：自动化输入编辑器按签名选择"对应流程输入/字段"并提示缺失；工作流目录返回签名；
  Studio 变量与"复制引用"对已绑定字段给出 `input.<键>.<字段>`，项目数据面板提供"转换为流程输入"（有未保存修改时拒绝）。
- R2-23：见 2721dc06。

## 验证

- 后端：`test_workflow_signature.py`（8：绑定缺失/类型不符/改显示名/复用两表/迁移改写与可重入/共用只报告/Studio 形/保存保留）、
  `tests/unit/workflows/test_workflow_signature.py`（4：解析、引用、上下文、运行遮蔽）、迁移 head 与模型一致性。
- 前端：InputPlanEditor 绑定、project-input-panel 转换与新式引用。

## 剩余

- Studio 内尚无手工编辑签名的界面（签名由"转换为流程输入"或迁移生成）；手工编辑与输出签名（outputs）留到 M5 体验整改。
