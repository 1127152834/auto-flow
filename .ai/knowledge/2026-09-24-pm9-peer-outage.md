# PM9 同行身份异常移除后恢复验证

日期：2026-09-24；状态：confirmed，本机真实worker子范围。来源：DATA-CLAIM-09原始设计、公开HTTP/SQLite/浏览器/worker断言，Google transport与凭据为受控夹具。

复用shared_tables和start_real，不改生产代码。另一项目完整扫描重复身份后，通过公开DELETE移除绑定；剩余项目拉取失败仍返回configurationError且零Task/lease/浏览器，本地数据和成功来源时间保留。移除重复并完整拉取后仅剩一peer的身份凭据有效，新批次冻结原值/ref/版本、人工继续写入一版本及一pending意图；旧失败批次保持失败且不重启，资源释放，远端无写入。

原/tmp测试浏览器已不存在，首轮setup失败发生在业务断言之前；保留日志，不称产品RED。通过现有ensure_binary将同CI固定145.0.7632.109.2恢复到独立工作区缓存后最终1 passed/8 deselected/2 warnings（10.63秒）；Ruff通过；原CI选择表达式实际collect33/44、11deselected并包含新用例。

生产仍1c676965；前3493项全量和22截图ARM包不包含新用例，不能追认本测试已由旧CI覆盖。当前GitHub CLI认证401，PR连接器可写但无Actions触发工具，用户恢复或手动触发待回复。完整改绑/代次/namespace联合、打包实网、签名和实机仍待验收，台账状态不变，releaseAccepted=false。详见peer-outage-follow-through.json。
