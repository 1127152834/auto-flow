# Android旧批次兼容与真实权限拒绝

日期2026-09-24；状态confirmed；来源生产旧后端a92f0688/当前后端真实HTTP、SQLite迁移和Mac/Lima/ReDroid，证据docs/qa/android-management/2026-09-24-legacy-upgrade.md及2026-09-24-backup-permission.md。

旧BatchCreate没有sourceDeviceId，当前HTTP默认null，精确比较导致升级后原请求409。0f6f8fac只在批次比较归一化缺失/null；不改持久原记录，不放开新temporary，不忽略真实source ID或true磁盘确认变化。真实旧0019数据库迁移am01后，临时实例身份、卷、配置、数据保留且历史重放202。SQLite回归RED2→GREEN6，Android540通过。完整门禁和独立复审以最终验收报告实际结果为准。

备份目录真实UF_IMMUTABLE拒绝写入返回EPERM→持久needs_verification，无发布/残留staging；解除后同请求不能自动重放，新请求成功，源数据保留且测试自有资源清空。只修改自有临时目录并恢复标志。

旧版本升级通过不等于同发布入口停用/重新启用桌面组合链通过；Mac仍锁屏，十实例容量/GApps条件仍缺。不得把本次新RED追认为缺失的历史RED。

最终补验：全后端4124passed/26skipped/2warnings，780.28秒，exit0；独立复审Critical/Important/Minor均0；OpenAPI/build重验通过。前端1050源码/测试文件与78bf8c92的5689passed全量结果hash完全一致。
