# 项目管理 PM9 发行验收

- 日期：2026-09-20；状态：进行中，**未达到 PM9 发行退出条件**。
- 分支：`codex/project-management-pm9`；有效代码已先合并到 `codex/architecture-baseline@8e5564e0` 并推送。
- 验证入口：[本轮机器报告](../project-management/implementation/pm9/verification.json)、[251 项覆盖核对](../project-management/implementation/pm9/coverage-audit.json)、[执行卡](../superpowers/plans/2026-09-20-project-management-pm9.md)。

## 本轮实际证据

macOS arm64 生产 HTTP 与 Electron 管理链分别在源码和打包应用中运行。界面真实创建项目；同一生产 API 断言覆盖表/字段/记录、长中文文本、CAS、原请求恢复、归档恢复和邻项目安全删除。重启同一隔离工作区后核对记录仍在；六个项目页签等待真实空态/数据加载后截图。原生窗口 200% zoom 无文档级水平溢出；Studio 第二窗口与主窗口连接同一认证服务。这些检查不冒充每个控件的完整视觉/键盘验收。

本机 PyInstaller sidecar、Electron 应用目录和 `AutoFlow-0.1.0-arm64.dmg` 已构建。没有 Developer ID 签名、公证或手工安装验证；`.app` 运行通过不等于 DMG 安装体验通过。

复用万行测量程序，但将本次输出写入 PM9，不覆盖 PM2 原报告：10,000 行 / 3 列、50 页真实 SQLite/HTTP 读取、Excel 导入导出与前导零均通过，来源文件 SHA-256 保持不变。单次本机导入约 2.67 秒、全页读取约 2.10 秒；这不是一般性能承诺，尚无 1,000 日志/分钟和内存增长结果。

## 可复跑命令

```sh
node scripts/smoke-project-management.mjs --output-dir /tmp/pm9-api
node scripts/smoke-project-management-desktop.mjs --output-dir /tmp/pm9-desktop
npm run backend:build
npm run package:dir
node scripts/smoke-project-management.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/Resources/backend/autoflow-backend --output-dir /tmp/pm9-packaged-api
node scripts/smoke-project-management-desktop.mjs --executable apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/MacOS/AutoFlow --output-dir /tmp/pm9-packaged-desktop
```

Windows/Intel 路径由 CI 根据实际产物定位；不要在其他架构硬套上面的 arm64 路径。两脚本拒绝 QA sidecar/开发 URL 环境注入，只在各自新建的临时工作区写入；报告不包含认证 token。`smoke-project-management.mjs` 由过时的 PM1 桌面脚本更新为可复用生产 HTTP 链，桌面入口为新增的 `-desktop.mjs`；PM1 历史报告原样保留。

## 尚未关闭的条件

- 项目生产执行器只支持四个线性浏览器节点；PM4–PM8 的项目数据/End/人工完整闭环尚需接入。[具体架构与 R1–R4 计划](../superpowers/specs/2026-09-20-pm9-production-runtime-integration.md)待确认，不以隔离执行器和单元测试代替。
- 原真实浏览器项目测试的共用 HTML 已被 Studio B1 改成另一组选项，导致旧选择器超时；本轮新增独立项目 HTML，并更新测试中已更名的项目 worker 状态入口。修正后 8 项真实 CloakBrowser 测试通过，覆盖四节点执行、批次与服务重建；夹具失败不记为产品缺陷。
- Windows x64 / macOS Intel 使用 GitHub Actions；配置已加入同一生产管理链、固定参考源码检出和证据上传。[当前三平台运行](https://github.com/1127152834/auto-flow/actions/runs/35507610003)正在执行 `10dc916c`，尚无最终结论；实机结果仍待验收。初次运行暴露的时区与 Blob 测试夹具问题已在 Node 22 / UTC 下复现修正，相关 10 项通过。
- 全图生产链、授权 Sheets 实网组合、原生文件面板/凭据、平台异常退出、千日志/分钟与内存测量、完整视觉及人工安装检查仍不齐。

历史覆盖仍为 48 功能、178 场景、25 契约/门槛，PM9 本轮没有批量提升这些条目。任何一条新管理冒烟通过，都不能将整个模块标记为发行完成。
