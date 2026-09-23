# PM9 Windows 受管截图二进制读取

- 日期：2026-09-23；状态：confirmed（失败日志与代码缺陷、本机修复），Windows修复后原生验收pending。
- 来源：Actions35811305102/job107023291046，manual-evidence-reconnect真实截图元数据available而GET内容409；Python3.11 os.open官方文档要求Windows O_BINARY。
- 根因与修复：公共ProjectRunEvidence.artifact_content未设置O_BINARY，文本模式会转换CRLF/0x1A，使PNG大小/摘要校验失败。加平台提供标志，缺失取0，全部归属/路径/大小/摘要守卫保留。原ASCII b"png"契约fixture改为含PNG头/控制字节的内容，已有HTTP逐字节验证保留。
- 验证：16项契约/集成4.63秒；Mac真实worker/TCP/SSE/PNG场景1项17.49秒；Ruff/mypy407通过，独立审查无P1/P2。原生Windows结果另行记录，不先声称通过。
- 范围：仅应用受管Run产物读取；没有开放任意路径既有文件覆盖/追加/读取S4。releaseAccepted=false。
