# 基础骨架验证记录

日期：2026-09-11。范围：基础实施计划任务 1–7，未迁移旧项目业务代码。

## 本机结果

- 平台：macOS 26.4.1 / Apple Silicon arm64。
- 运行时：Python 3.11.13、Electron 41.10.3；桌面 smoke 也使用 Node.js 22.17.1 执行。
- Python 单元测试：14 通过；Ruff、mypy 通过。
- 桌面测试：17 通过；TypeScript、ESLint、Electron Vite build 通过。
- Node 脚本测试：7 通过；OpenAPI 生成一致性检查通过。
- 真实 Electron 开发启动和打包启动：renderer 显示服务已连接；强制结束桌面宿主后 sidecar 随父进程退出。
- 本机 PyInstaller onedir、Electron 目录产物和未签名 DMG 已生成。
- npm audit：0 个漏洞（检查时结果，不代表永久保证）。

## 产物

- `apps/desktop/dist/mac-arm64/AutoFlow.app`
- `apps/desktop/dist/AutoFlow-0.1.0-arm64.dmg`
- bundled sidecar：`AutoFlow.app/Contents/Resources/backend/autoflow-backend`

## 全局审查后的修复

- 将开发 sidecar 启动接入 uv 后端环境，消除对全局 `python` 的依赖。
- 通过明确注入的 renderer origin 配置 CORS；预检可通过，业务请求仍需 instance token。
- 补齐 macOS 窗口关闭/重新激活行为，保持单一 sidecar 生命周期。
- Python 监控宿主 PID，覆盖宿主崩溃或强制终止；Windows 使用进程句柄，macOS 使用进程存活检查。
- 后端测试使用临时路径，避免 `/tmp` 硬编码导致 Windows 失败。
- smoke 产物模式与外部地址模式互斥，退出清理设置最终期限。
- 构建工具归入开发依赖；Electron/Vitest 更新到审计通过版本。

## 验证边界

Windows x64 与 macOS Intel 已配置 CI，但本次没有远端 job 结果，不能声称这两个平台已运行通过。
DMG 为内部测试产物，未签名、未 notarize。后端测试存在两条上游弃用提示，不影响当前结果。
当前仅有健康/恢复基础界面；业务模块与 WebRPA 能力移植属于后续阶段。
