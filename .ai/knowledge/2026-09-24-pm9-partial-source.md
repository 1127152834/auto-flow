# PM9 不完整来源读取不得伪装记录耗尽

- 日期：2026-09-24；状态：confirmed 本机定向/全量，ARM新包confirmed，三平台pending。
- 来源：DATA-CLAIM-09/10 原始规则与新增 HTTP/SQLite 反例。首次读取第二值视图失败后，原实现 noMatch 而非 configurationError；已有完整缓存对照通过。失败日志 `.tmp-tests/pm9-partial-source-2026-09-24/red.log` 保留。
- 根因：来源身份校验仅在枚举具体记录时调用，空缓存路径绕过。将已有来源身份/代次/同行/发送围栏判断提取为 `_verified_sheets_source`，候选扫描之前与记录lease解析共同使用；保留逐记录mark检查。不增加缓存TTL、不变更API或执行器。
- 验证：claims/system身份42项，最终必要/可选×有无完整缓存及合法空表6项，真实worker2项通过；Ruff/mypy408通过。真实公开批次首次断网configurationError且零Task/浏览器/lease，完整读取后持续断网仍可运行；双worker反向写保护通过。相同源码1c676965串行完整后端3493 passed/80 skipped/2 warnings（778.49秒）；后端构建/ARM打包通过，完整桌面验收passed/22截图（原有全链，不是实网Sheets断网UI）。具体计数、耗时和哈希见 `partial-source-follow-through.json`。
- 现有两轮CI缺少此生产修复，继续保留不取消；候选稳定后另做必要的新源码验证，不将旧结果升级为新候选通过。
- DATA-CLAIM-09/10状态不升级。绑定/同行变化真实worker联合场景、打包真实Google/OAuth、签名和实机条件仍未满足；releaseAccepted=false。
