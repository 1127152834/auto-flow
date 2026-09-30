# 多对象清理在首项提交后硬中断

- 日期：2026-09-24；状态：confirmed（本项），完整模块验收仍 partial。
- 来源：[可运行脚本](scripts/cleanup-interruption-smoke.py)、[实际结果 JSON](2026-09-24-cleanup-interruption-result.json)。
- 在新的临时工作区中通过生产 BackupStorage 创建两个真实未发布归档目录；另建受控目录外的保留探针。它们都是本轮合成文件，不使用用户备份或设备。

```text
uv run --project apps/backend python docs/qa/android-management/scripts/cleanup-interruption-smoke.py --allow-device-mutation
exit 0: status=passed
```

认证 HTTP 生成两对象冻结预览后关闭后端。独立子进程通过生产 ASGI 路由、SQLAlchemy 仓储和文件清理服务执行预览，在第一项真实删除且第一条成功结果已提交时发送 SIGKILL，退出 `-9`。故障钩子只位于真实仓储写入之后，不替代删除或提交；中断时是 ASGI TestClient，重启/重放/核实/新预览均使用独立认证 HTTP 后端。没有模拟设备、运行时或删除成功响应。

| 检查 | 实际结果 |
| --- | --- |
| 中断点 | 两个冻结候选、一个已提交成功条目；第一个目录确实消失，第二个目录仍在。 |
| 原请求 | `d34be486-a8a9-4b4c-9167-721cdcf6c57b`。 |
| 重启查询 | 父 Operation `needs_verification`。 |
| 原请求重放 | 返回 `running`，没有误报 succeeded；未执行对象文件字节不变，没有自动继续删除。 |
| 按原请求核实 | HTTP 503 `ANDROID_VERIFICATION_UNAVAILABLE`，保持未知且不删除第二项。 |
| 明确新预览 | 对剩余对象重新预览、用新请求清理，返回 succeeded，目录实际消失。 |
| 非目标数据 | 受控备份目录外的探针内容不变。 |
| 最终清理 | 两个本轮暂存目录均不存在；`ownedTemporaryFilesDeleted=true`。 |

首轮 QA 核实步骤误用新 requestId，生产正确返回 409 `ANDROID_REQUEST_CONFLICT`，该轮未记为通过且两个暂存目录已清理。改为契约要求的原 requestId 后完整重跑得到上表结果，未修改生产保护规则。

本证据证明多对象清理的中断不会被已完成首项掩盖。它不证明无持久归属来源的旧客体文件可安全删除；此类文件继续排除，符合禁止推断外部资源归属的边界。
