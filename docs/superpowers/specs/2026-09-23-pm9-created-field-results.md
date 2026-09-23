# PM9 新字段返回引用与后续写权限

日期：2026-09-23。状态：proposed；原始业务目标已批准，本文新增的冻结授权字段和动态值映射契约尚未批准。来源：`data-and-state-rules.md` §8.1（DATA-SCHEMA-02/09）、`data-flow-and-contracts.md` FLOW-A14、`pm9/created-field-results-follow-through.json` 的当前 ARM 打包反例。

## 已证明的缺口

T1 能新增字段，T2 旧契约仍能运行；但 T1 随后写新增字段被 CAPABILITY_SCOPE_DENIED 拒绝。把将来的 fieldId 预先放入静态 tableGrant 又会在批次准备以 CAPABILITY_FACTS_INCOMPLETE 拒绝。原有 modifyField 能查询本 Task 的成功 add/ensure 账本，记录写入没有对应来源授权。变量解析只解析字典的值，不能通过返回引用构造动态字段键。

这属于实现缺失。不能把失败归咎于 Google 授权，也不能把“静态 fieldId 可预先授予不存在字段”或“同 Task 新建字段全部自动可写”作为修复。后者会绕过子流程节点的声明权限。

## 最小契约

继续使用现有 `project_data` 节点、ProjectOperationRow、project_command_id、PreparedContent、事件执行上下文和 TaskCapabilityScope；没有新执行器、数据库表或 HTTP 写入口。

消费者节点的 `tableGrant` 增加可选 `fieldResultSources: string[]`，内容为冻结文档中明确的 addField/ensureField 生产者 nodeId。缺省为空，原文档语义不变；tableId、datasetGeneration、operations、静态 fieldIds 和 readPurposes 继续保留。第一片消费操作是 createRecord/updateRecord；其他操作仍按其原有字段授权，不顺带扩大。

`arguments.values` / `arguments.changes` 的静态 UUID 键保留原行为。消费者可以使用精确的返回字段表达式作为键，例如：

```json
{
  "tableGrant": {
    "tableId": "<source-table>",
    "datasetGeneration": "<current-generation>",
    "operations": ["updateRecord"],
    "fieldIds": [],
    "readPurposes": [],
    "fieldResultSources": ["ensure-receipt"]
  },
  "arguments": {
    "recordRef": "{row['ref']}",
    "changes": {"{receipt['field']['ref']['fieldId']}": "R-001"},
    "expectedContentRevision": "{row['contentRevision']}"
  }
}
```

这里只扩展项目 create/update 的字段值映射，不改变共享 Studio 变量解析器的字典键语义。运行准备核对表达式根变量与所声明生产者的冻结 variableName 一致；模糊多生产者、无法证明变量来源或表代次不一致时拒绝，并定位消费节点。解析后的键必须为 fieldId，重复键或动态/静态键碰撞明确拒绝，不能后值覆盖前值。

## 权威校验与作用域

1. 准备阶段验证每个来源节点存在、操作为 addField/ensureField、声明表/代次与消费者一致，消费者已声明原 create/update 操作；允许尚未产生的字段结果，不允许任意未存在静态字段。
2. worker 解析实际值，父进程独立从冻结消费者配置取得允许的来源。worker 自报来源、字段名或 UUID 均不是权限证明。
3. 父进程使用来源节点已持久提交的成功访问和 `project_command_id(runId, generation, nodeVisitId)` 查询既有 ProjectOperationRow。操作必须为 succeeded 的 addField/ensureField，project/task/run/generation 全部匹配，result.field.ref 与请求字段和冻结目标精确一致。ensure 的 created=false 也以该次明确成功的操作为凭据，不按同名字段猜测。
4. 只为当前消费者、明确操作、表和实际消费的字段生成临时 scope，不能修改整个 Task 的永久静态 grant，不能把来源访问等同记录写 lease。仓库继续校验当前代次、任务运行态、记录占用、内容版本、字段校验、出站意图和原命令幂等。
5. 调用/循环/并行上下文必须符合共享 Runtime 的显式变量可见性：相同调用和循环内可消费已成功的前序结果；跨调用仅经已声明子流程输入/输出，跨分支仅经已声明合并输出传播。生产者访问必须在消费者之前，且其调用路径与分支身份有持久证据。不能因 nodeId 相同取另一次调用、兄弟分支或旧迭代结果。无法证明的引用保持拒绝并留作未完成子条件，不宣称整个返回引用能力完成。
6. 其他 Task、外部人工新增字段、旧执行代次、旧数据代次、已删除再建字段，以及被篡改的变量结果不能继承此权限。字段删除、类型变更和活动依赖继续走既有保护。

## 用户入口与行为

复用 ProjectDataConfig 的字段配置，增加“使用前序新增/确保字段结果”的明确来源选择。只展示可证明可见的生产者，序列化上述冻结来源和字段表达式；预检错误定位来源/消费节点。显示真实返回字段，不要求用户手写 UUID。旧工作流继续按原静态字段方式运行。

已有数据提交后，后续动态字段写失败仍保留先前修改和原失败事实。重试查询原 operation，不再次创建字段、再次写入或重放网页。schema/source/字段校验不会因新引用方式降低。

## 验收与取舍

必须同时证明：首次创建后写入、同键同定义返回已有 fieldId 后写入、异型同键冲突、T2 旧契约并存、原输入不改形、原命令恢复、字段返回被替换拒绝、旧 Task/代次拒绝、子流程声明传播、并行/循环上下文隔离，以及有界冲突不部分写。

直接扩大所有 tableGrant.fieldIds、放行尚不存在静态字段、把任意业务字段名解释成 UUID、删除父进程权限检查均不采用。新增合同须先确认；此提案不包括 L1–L3、M1–M3 或 Windows 既有文件写入，`releaseAccepted=false`。
