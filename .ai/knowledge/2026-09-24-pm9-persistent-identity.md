# PM9 持久环境身份未保留

日期：2026-09-24；状态：confirmed反例，修复方案proposed。来源：原始执行/环境设计§8.3与本机真实打包probe。

2026-09-24 持久环境身份反例（confirmed实现缺失，I1–I3 proposed）：当前cb040daf ARM打包真实HTTP/SQLite/worker在保存登录后修改Profile与重置seed，固定和输入关联恢复均signed-in，但UA/locale/timezone变为新Profile，原生seed由21807变42845。identityPreserved/seedPreserved均false，不是验收通过。仓库未保存实际身份包，恢复与维护读取当前Profile；维护仅代码证据。34项原资源/环境测试通过仍不覆盖此条件；4映射/251引用通过。XE-C02/C11/G04/A20补implementation_missing，249有断言/2未定位、206partial/45planned/0verified不变，按需求去重缺口241生产/19实现/8测试/24外部。新增I1–I3规格与计划待确认；保留首轮重复绑定409夹具错误。无生产修改、不重复全量/构建；releaseAccepted=false。详见persistent-identity-audit.json。

探针从既有project-runtime-smoke.mjs缩减，继续使用生产worker和独立临时workspace；仅本地fixture站点，不碰用户浏览器或实网账号。公开Profile编辑、重新生成seed后依次固定/输入恢复，同一保存环境Cookie存在但实际身份错误。probe exit0只说明测量完成，JSON显式false；提交的probe已再次执行并保留原始观测和哈希。

根因跨保存、Task资源与人工维护；仅覆盖worker seed不足。I1提议版本化身份包随内容发布、旧身份缺失显式阻断，I2统一权威组装/代次，I3真实链验收。涉及持久化格式与旧环境兼容，按AGENTS架构规则等待用户确认，不把目标自动继续当作确认。
