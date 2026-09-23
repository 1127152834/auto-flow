# PM9 当前三平台矩阵

日期：2026-09-23。状态：confirmed（三平台 CI），发行验收 pending。

来源/验证：Actions [35822065171](https://github.com/1127152834/auto-flow/actions/runs/35822065171)，候选 `1b2979ea40bf1420068972985677367e27ca4b27`，三个 checks job 均 success；各 job 完成日志的回归汇总、真实 worker 汇总、打包运行 JSON、安装包构建行。精确平台数值和边界见 `docs/project-management/implementation/pm9/ci-final-follow-through.json`。

Windows 实际 worker 1004 条/100723 ms，观察速率 598 条/分钟；固定 60 秒的 1000 条合成仓储输入另行通过，不能混称 worker 达标。Windows 五路万行写入 670182 ms、0 次明确 busy 重试；未设新的性能门槛。两类 PM9 原生 probe job 为 skipped，不把 checks 内的原生测试等同于 probe 或物理实机验收。当前 ARM 隔离 DMG 安装另有独立证据；Google/OAuth、完整物理安装、签名及 S4/L/M 缺口不因矩阵成功消失。`releaseAccepted=false`。
