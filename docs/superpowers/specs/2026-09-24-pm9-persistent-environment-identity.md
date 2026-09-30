# PM9 持久环境身份 I1–I3

日期：2026-09-24；状态：proposed，等待确认。依据：原始 execution-and-environment.md §8.2/8.3、XE-C11/XE-G04/XE-A20；生产源码 cb040daf，审计基线 1ad92af4。

## 用户目标与已确认问题

恢复固定或输入关联环境时，Cookie/持久内容与保存时的身份参数、seed、内核必须一起恢复；当前 Profile 编辑/重置不能隐式改变原身份。新建来源仍使用批次冻结的 Profile，人工维护与任务恢复必须遵守同一身份规则。

真实 ARM 打包 HTTP/SQLite/worker/browser 探针先保存登录环境，再公开修改 Profile 的 UA、locale/timezone 并重置 seed。固定与输入关联恢复均 signed-in，但实际网页身份变为新 Profile；原生浏览器 argv 的 seed 也变化。此证据说明现有登录恢复验收不足以证明身份保持，不能标通过。详见 persistent-identity-audit.json；首轮重复绑定同一工作流的409为探针夹具错误，单独保留。

当前代码：ProjectEnvironmentRow 仅存 profile_id；实例 identity_package 仅写 source/profileId；ResolvedEnvironmentSource.identity_package 只含引用元数据。ProjectRunResourceResolver 再调用当前 Profile.freeze，WorkflowBrowserResources.acquire 不消费保存身份；人工维护 EnvironmentBrowserManager 同样读取当前 Profile。仅在 worker 覆盖 seed 会漏掉维护、内核与旧环境兼容，不能作为根因修复。

## 最小方案及取舍

采用随已保存内容发布的版本化身份包，复用现有环境、实例、保存操作和资源快照，不引入第二执行器或新的历史环境版本产品。为 ProjectEnvironmentRow 增加可空 identity_package JSON；复用实例已有同名列。旧值为空表示缺失证据，不能拿迁移时的当前 Profile 补造历史身份。

候选文件旁增加由宿主生成、浏览器不可作为权威修改的身份元数据，并纳入保存摘要/核验。实例内数据库身份为权威；staging时从数据库写候选元数据，不信任浏览器目录内同名文件。publish_update/create_ready 同一数据库提交保存 contentGeneration/digest/identity_package；中断重放从原候选/操作核对同一包，不从当前 Profile 重建。候选元数据损坏、版本未知或与数据库冲突均拒绝启动/发布，保留原事实。

建议 V1 最小形状：

```json
{
  "schemaVersion": 1,
  "profileId": "uuid",
  "kernelId": "edition:version",
  "frozenConfiguration": {
    "profileSpec": "现有无凭据 ProfileSpec 完整快照",
    "fingerprintSeed": 123,
    "createdAt": "ISO时间",
    "updatedAt": "ISO时间"
  }
}
```

profileSpec 使用现有字段和校验，不发明第二套指纹配置。seed、UA、locale/timezone、viewport、内核和其他身份/资产参数使用保存值。headless 与既有运行预算允许按当前任务明确配置；代理仍按原有显式覆盖链执行，无覆盖使用保存的策略引用。代理池成员/端点冻结属于待确认P1–P3，I不声称一并完成。License与代理凭据按引用从凭据服务读取，包中不得保存秘密或浏览器存储正文。geoip或未设置字段必须记录明确的动态策略与可证明的实际值，不能把空值称为已固定身份。外部扩展/资产内容的完整冻结仍按原台账保留缺口，I不凭保存路径引用宣称内容不变。

拒绝两种替代：每次恢复读取当前Profile（已实证错误）；只保存seed或只在worker覆盖（漏掉UA/内核/维护路径）。不从Chrome内部文件或canvas结果猜原始身份；canvas未变化也不证明seed一致。

## 选择、占用和恢复契约

- newFromProfile：沿用批准的批次冻结资源；预约实例时把同一无凭据包与Task/Run提交，不重新读取Profile身份字段。
- fixedEnvironment/inputEnvironment：从权威选定内容代次取得身份包，Task资源、实例、environmentRef三者一致。输入环境在领取时固定当前已保存代次；固定环境也不得出现资源引用g1但工作目录恢复g2。代次变化按既有复验/冲突路径处理，不能偷偷换源。
- 新 Task 可以依据公开规则选择新发布代次；已准备 Task 的身份和目录不可被后来Profile修改或环境发布替换。不把“冻结”误实现为永远锁住所有后续Task的旧环境代次。
- worker与人工维护共享同一已校验身份组装函数；平台差异继续在现有适配器。当前 Profile 仅用于引用存在性、允许的操作参数与凭据/使用守卫，不能覆盖保存身份。校验和启动使用保存的内核；不因当前Profile换内核而静默升级保存来源。
- 保存/另存继承实际实例身份，更新时与内容一同CAS发布；旧候选不得把身份或内容任一半覆盖新代次。关联修复不重写身份、不重复保存、不重跑网页。

## 旧环境兼容与界面

这是需要确认的行为变化。迁移不删除或修改原目录/当前代次；缺身份环境仍可列出、查看已有内容信息和按既有规则处置，但恢复/新维护启动明确409 ENVIRONMENT_IDENTITY_UNVERIFIED，不回退当前Profile。

仅当原save→instance→CoreRun资源请求的完整、同代次权威链仍存在且能证明实际运行包时，允许受控回填；不能由相同profileId、最近Profile或浏览器Cookie推导身份。首切片不自动回填无法证明的旧记录。缺少历史依据时只解释所缺条件；新增“采用当前Profile/建立新身份”产品流程不在本附录内，不能悄悄替用户选择。

环境详情/来源选择显示身份版本、保存内核及明确的“原身份资料缺失，无法恢复”状态。API只公开必要的非秘密摘要；不把完整内部快照或密钥放到列表/日志。组件与真实HTTP状态一起交付；导出/删除仍遵守原占用与权限，不以身份缺失绕过它们。

## 验证与退出

I1：版本/字段校验、旧库迁移、saveAs/update原操作恢复、两阶段崩溃、候选篡改、旧候选CAS、不可证明旧环境拒绝且不损坏目录。I2：两种来源及维护真实启动UA/locale/timezone/seed/内核；Profile修改/重置后原身份保持；Task资源与内容同代次；缺内核/非法身份零浏览器且无泄漏。I3：真实打包三种路径、关联修复、完整回归/三平台；现有新建Profile冻结正向继续成立。

验收要求以新probe中的 identityPreserved=true、seedPreserved=true 及严格字段/代次断言为子条件；探针完成或signed-in不算通过。没有真实平台/内核条件时保留待验。不得自动升级251条状态，releaseAccepted=false，草稿不合并发布。
