# AM2 入口停用与恢复发布补丁演练

- 日期：2026-09-24；状态：本次前端补丁演练 confirmed，T12.4 仍 partial。基线5210e388，加当时四份前端候选变更，[结果及哈希](2026-09-24-forward-entry/result.json)记录准确范围。
- 操作只发生在随机创建的 detached checkout；原业务分支没有停用入口。复用根目录和desktop局部已安装依赖，没有新增依赖、永久feature flag、生产发布或数据库downgrade。
- 本脚本不访问数据库、不操作设备；组件测试使用真实AndroidPage和既有测试HTTP边界，不是Electron实机。

```sh
uv run --project apps/backend python docs/qa/android-management/scripts/forward-entry-rehearsal.py --allow-rehearsal --output docs/qa/android-management/2026-09-24-forward-entry
```

最终实际exit 0，`status=passed/ownedCheckoutRemoved=true`：[脚本](scripts/forward-entry-rehearsal.py)、[脚本哈希](2026-09-24-forward-entry/script-hash.json)、[驱动输出](2026-09-24-forward-entry/driver-passed.log)。缺少授权标志时实际[exit 2](2026-09-24-forward-entry/cli-guard.log)。

| 步骤 | 实际输出 |
| --- | --- |
| 原源码入口可用 | [1 passed / 35 skipped，2.31s](2026-09-24-forward-entry/enabled-before.log) |
| 未停用就要求入口不存在 | [RED：1 failed / 35 skipped，2.30s](2026-09-24-forward-entry/disabled-red.log)，明确失败于镜像管理标题仍存在 |
| 应用停用补丁 | [GREEN：1 passed / 35 skipped，2.32s](2026-09-24-forward-entry/disabled-green.log)，镜像/模板入口移除，实例管理与打开按钮仍可用，挂载无写HTTP请求 |
| 停用版本类型检查与构建 | [exit 0](2026-09-24-forward-entry/disabled-build.log)，renderer 34.27s |
| 反向检查并恢复源码补丁 | git apply reverse check/apply均exit 0；AndroidPage前后SHA-256相同 |
| 恢复版本组件、类型与构建 | [1 passed / 35 skipped，2.38s](2026-09-24-forward-entry/restored-green.log)；[类型/build exit 0](2026-09-24-forward-entry/restored-build.log)，renderer 36.04s |
| 内容与清理 | 四份候选源码未变，44份原有迁移Python文件内容未变；自有checkout删除成功 |

[实际停用补丁](2026-09-24-forward-entry/disable-am2-entry.patch)只删除AndroidPage中的两个import和ImageManager/TemplateManager挂载，保留AM1实例管理及后端；[组件断言](2026-09-24-forward-entry/component-check.tsx)和[本次候选补丁](2026-09-24-forward-entry/candidate.patch)供复现。补丁是针对该固定源码的发布演练产物，未来应用前仍须git apply --check和重新验证；不能直接拿它宣称当前用户应用已停用。这里的“反向”只恢复前端源码，不执行数据降级。

首次演练漏链接desktop局部依赖，在类型检查得到8个`TS2307 @hookform/resolvers/zod`，没有完成恢复构建：[首次结果](2026-09-24-forward-entry/first-run/result.json)、[失败输出](2026-09-24-forward-entry/first-run/disabled-build.log)。已清理该临时checkout后，补齐已安装依赖链接，从新的checkout完整重跑；未修改产品代码或降低检查。首次RED本身仍是有效的入口断言失败。

独立只读复审无剩余Critical/Important；复审读取时第二次恢复构建尚在进行，最终exit 0和清理由主代理随后读取进程与结果核实。报告明确仅证明四份候选源码和44份原有迁移文件内容，不能推出真实数据库、旧实例或完整源工作区都已验证。

T12.4仍不能单靠该脚本关闭。前向数据库迁移、旧实例恢复和引用保护已有[6项迁移回归](2026-09-24-observation/migrations.log)及[真实自定义镜像/旧实例固定ID链](2026-09-24-custom-image.md)；本次没有在同一发布切换链执行真实数据库/旧实例保留，也没有因Mac锁屏跳过后声称真实桌面发布通过。完整阶段门禁、最终全分支审查和这些证据的统一核对仍需继续。
