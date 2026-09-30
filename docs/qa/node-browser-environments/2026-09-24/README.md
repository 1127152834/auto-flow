# 节点浏览器环境验收

日期：2026-09-24。状态：本地功能验收完成，完整发布验收未通过；releaseAccepted=false。

## 真实桌面链

命令：`AUTOFLOW_B1_KERNEL_DIR=<已安装内核目录> node scripts/smoke-node-browser-environments.mjs`。

隔离用户目录、生产 sidecar HTTP、正式 Electron Studio 和真实 worker；创建临时验收项目，不访问用户项目 q。脚本从实际界面保存项目默认模板，配置打开网页节点的模板、代理与内核，保存文档后回读，再从界面启动并确认 Run completed。模板代理、内核未被反向修改。

- [项目默认设置](project-environment-defaults.png)：右侧卡片移除，默认模板保存后可回读。
- [打开网页节点](open-page-environment-fields.png)：三个资源属性由节点维护，顶部无浏览器选择器。
- [真实运行完成](node-browser-run-completed.png)：Run 与内核信息见 [desktop-result.json](desktop-result.json)。

## 边界与未通过项

- 本机 macOS ARM64 源码构建证据；不是签名安装包、Windows/Intel 实机或 OAuth 证明。
- 实例内核不兼容迁移仍明确拒绝；旧环境缺少可证明的身份包时不猜测恢复。
- 子流程内部首次初始化不在本轮开放范围；子流程使用父任务已初始化的实例。禁用的远程协作未扩展。
- 全仓库 mypy 65 项 Android 相关错误：在干净的 15088ecb 源码再次运行得到同样 65 项，本轮不扩展修改 Android 实现。
- OCR 停止用例要求小于 3 秒，本轮实测约 3.3 秒；干净的 15088ecb 同一用例约 3.27 秒，同样失败。原断言保留。
- 三平台在现有 CI 验证节点初始化与真实 worker，再继续原完整门禁；不因本功能测试通过而称整个 CI 或 PM9 通过。

## 审查修正

独立审查覆盖 15088ecb..1527848e，确认两项 P2：延迟初始化后失败截图取不到当前页面，以及 AI 装载丢失版本标记。已补反例并修复。真实 Electron 验收另外发现 Studio／维护错误查询项目 Task 工作目录，改为宿主显式传入各自受控目录；项目任务继续使用原权限与占用校验。

导入、导出、撤销、AI 装载及模块备份保留版本。跨版本浏览器节点合并拒绝，要求先显式迁移；旧文档不会随保存悄悄升级。

## 远端候选验收

代码候选 `27e93a40` 已推送至 [草稿 PR #2](https://github.com/1127152834/auto-flow/pull/2)，[三平台 CI #118](https://github.com/1127152834/auto-flow/actions/runs/35978138740) 已执行：Windows 与 Apple Silicon 的节点初始化、真实 worker 和清理专项均通过。Windows 完整任务在 test:scripts 步骤失败，Apple Silicon 在 mypy 步骤失败，Intel 在依赖安装阶段失败、未进入浏览器专项；各平台最终状态和公开步骤见 verification.json 与 ci-results.json。Windows 脚本失败缺少可读的认证日志，原因待查，不归因为既有问题，也不宣称验收完成。

Intel 安装阻断在当前代码及干净的 `15088ecb` 同样复现：`uv sync --locked --group build --python-platform x86_64-apple-darwin --dry-run` 报 `mediapipe==0.10.35` 没有 Intel macOS wheel 或源码发行包。本轮未改变依赖清单/锁文件，也未删除依赖来伪造平台通过。远端详细日志需要有效 GitHub 登录，目前仅核验公开步骤结果；不把本地 mypy 诊断数量当成已读取远端日志。

远端 baseline 尚为 `c6e02427`，本地此前已合并到 `1bc6b24d`；草稿 PR 包含继承历史，本轮实现审查范围从 `15088ecb` 开始。未推送共享 baseline、合并或发布。文档更新使用 `[skip ci]`，上述结果仅对应明确记录的代码候选。
