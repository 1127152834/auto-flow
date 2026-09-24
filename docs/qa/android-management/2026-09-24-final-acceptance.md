# 安卓模拟器管理快速验收结果

- 日期：2026-09-24；结论：**完整验收不通过，当前 partial**；置信度：高。
- 用户最新要求最快检查验收，本轮冻结功能扩展，运行安卓范围验收、工程门禁、迁移检查、最终分支限时审查及真实桌面快速检查。未完成项目直接列明，不继续展开新方案。
- 基线 `b51fac4f` 加[候选源码哈希](2026-09-24-final-acceptance/candidate-hashes.json)。原三份 Studio 未提交文件保持原哈希，未纳入提交。迁移仍为 `am01_management_operations → 0019_recording_commands`（head → parent），没有空迁移。

## 完成项及实际验证

| 范围 | 本次实际结果 |
| --- | --- |
| 后端 Android 全部合同/单元/集成 | **477 passed，2 warnings，35.14s，exit0**；[输出](2026-09-24-final-acceptance/backend-android.log) |
| 其中备份/runtime/restore/cleanup定向 | 158 passed，1 warning，14.73s；包含于上一行，不相加；[输出](2026-09-24-final-acceptance/backend-focused.log) |
| Android 前端全部 | **14文件 / 177 passed，8.36s，exit0**；[输出](2026-09-24-final-acceptance/frontend.log) |
| 工程门禁 | typecheck、lint、OpenAPI check、build全部exit0；renderer 38.27s；同上日志。后端Ruff/compileall exit0（首次三处测试import排序已修正） |
| 迁移 | **6 passed，1.30s，exit0**；[输出](2026-09-24-final-acceptance/migrations.log) |
| 全分支限时只读审查 | 未发现新增Critical；前端未知请求跨动作覆盖已修复并复审关闭；AM-R12未完成保留Important；[审查范围](2026-09-24-final-acceptance/reviews.md) |
| 真实备份磁盘准入 | 自建64MiB磁盘仅剩2MiB时，预检拒绝且归档调用 **0次**；释放后估计与实际均 **18,595,840字节**，成功归档1次；[JSON](2026-09-24-final-acceptance/real-disk-result.json) |
| 真实传输取消/清理 | 写入122,880字节时取消，持久needs_verification，无发布或staging残留；原请求不重放，源探针保留；自建设备/卷均missing，私有磁盘卸载删除。不是填满用户系统盘 |
| 真实桌面快速检查 | Mac已解锁；启动独立空工作区，最终构建完成后重新加载，实际页面显示实例/批量/镜像/未知拉取/模板/维护及真实运行环境可用。无效拉取被拒绝后输入可修正。数据库设备及操作均0，未提交修正后的拉取；自有Electron已退出；[记录](2026-09-24-final-acceptance/desktop-smoke.json) |

已交付的基础生命周期、环境诊断、统一状态、控制、保留/删除/恢复、镜像/模板、批量、应用和维护功能继续按各阶段既有证据保留，本次没有重新冒称全部功能已实机走完。[模块索引](README.md)、[AM1](am1-verification.md)、[AM2](am2-verification.md)、[AM3](am3-verification.md)、[AM4](am4-verification.md)。

本轮新增备份空间预检采用原GNU tar参数在客体内流式计数；停机、归属及锁校验之后，在stage之前检查实际宿主目标文件系统。归档/manifest按分配块向上取整，并预算尚缺目录；未知估计或探测失败明确拒绝。预检取消记录failed/BACKUP_PREFLIGHT_CANCELLED，开始写入后取消仍needs_verification。页面仅对三个明确磁盘拒绝释放请求；响应丢失先核实原回执，未知期间禁止新备份/恢复动作。

RED证据：[初始9失败](2026-09-24-final-acceptance/backend-red.log)、[预检取消1失败](2026-09-24-final-acceptance/cancel-red.log)、[目录预算1失败](2026-09-24-final-acceptance/directories-red.log)、[磁盘拒绝后新尝试3失败](2026-09-24-final-acceptance/ui-red.log)、[核实失败终态后新尝试1失败](2026-09-24-final-acceptance/ui-cancel-red.log)、[未知跨动作2失败](2026-09-24-final-acceptance/unknown-cross-action-red.log)。

## 不通过项、阻塞项与风险

1. **Important / 软件未完成：AM-R12创建和镜像拉取缺少操作前磁盘准入；宿主与VM两套可用空间数值未展示。** 备份预检已补齐，不能代表这两条路径完成。该项不是外部blocked。
2. **not_run / 部分实机验收未完：**完整批次取消/新批次/筛选保留交互、未知拉取跨桌面重启核实、镜像内容删除、下载途中断网、T14/T16前台/隐藏页测量及同一发布切换链数据库/旧实例保留。历史HTTP、组件、前端补丁演练仅证明各自范围。Mac锁屏阻塞本次已解除，相关完整桌面流程改为待执行，不再沿用当前locked说法。
3. **blocked / 外部条件：**十台最低配置需要8192MiB，当前VM实际 `MemTotal=8306655232` bytes（约7922MiB）、6CPU，低于门槛；GApps专用镜像/账号/商店链条件仍未齐备。
4. **最终全仓全量门禁未在最后候选上重跑。** 本次按用户加速指令先给快速失败结论；已知规格硬缺口使完整签收不成立。旧4048后端/5656前端等全量报告属于旧源码，不能冒充当前全量通过。
5. 预检是容量估计，不保证期间外部写入、文件系统额外元数据或卷内容变化不会引发ENOSPC；保留失败清理和结果未知保护。预检取消的Event集成测试不冒充远端tar强杀退出验证。

## 可复现命令

```sh
# 在 apps/backend
uv run pytest tests/contract/test_android*.py tests/unit/test_android*.py tests/integration/test_android*.py -q

# 在仓库根目录
uv run --project apps/backend pytest apps/backend/tests/integration/test_android_m4_migration.py apps/backend/tests/integration/test_migration_heads.py -q
npm exec --offline --yes --package=node@22.23.2 -c 'npm test -w @autoflow/desktop -- src/renderer/domains/android && npm run typecheck && npm run lint && npm run openapi:check && npm run build'
uv run --project apps/backend python docs/qa/android-management/scripts/disk-full-smoke.py --allow-device-mutation --scrcpy-archive /Users/zhangtiancheng/.autoflow/android-runtime/scrcpy-macos-aarch64-v3.3.4.tar.gz
```

当前只记录验收结论，不宣布AM1–AM4完整目标完成，不合并或发布。
