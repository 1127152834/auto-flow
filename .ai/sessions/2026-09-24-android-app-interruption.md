# Android APK执行中断真实验收

- 日期：2026-09-24；状态：confirmed（本文场景），整体active/partial。
- 基线：8520a655，隔离worktree；唯一迁移head am01_management_operations，三份Studio脏文档保护。无生产代码变更。
- 来源：[真实报告](../../docs/qa/android-management/2026-09-24-app-interruption.md)和仓库opt-in QA脚本。首次观察器漏过安装窗口，实际安装成功但不计中断通过；修正观察器后两轮真实新安装/覆盖安装故障成功。
- 两种故障：客体实际cmd package install已运行、APK完整上传、无完成标记，短暂停住该客户端以固定边界，然后只杀身份匹配SSH或本轮HTTP自有进程树，再恢复客体客户端。未注入产品回执。
- 最终两台原应用数据不变、versionCode1086仍存在，重启核实503/needs_verification、重新取得控制409；旧包存在不能当作本次成功。三轮5台容器/卷均生产核实missing，未知场景通过归属核验后的QA夹具销毁清理，不冒充产品恢复idle/删除验收。
- 应用契约/APK/控制回归32passed、2warnings in0.27s；脚本Ruff/help/缺授权exit2通过。沿用8520a655全量门槛，不重复声称本轮重跑。
- T07.3通过，当前102步骤84passed/15not_run/3blocked；T07历史RED缺证、T15桌面确认、精确布局、镜像断线、回退/规模指标和外部条件仍未完成。
