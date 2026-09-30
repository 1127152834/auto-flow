# Laya 实验室退役

- 日期：2026-09-30。
- 状态：confirmed（实现、定向回归、构建与真实桌面检查完成；首次失败与复查结果均保留）。
- 来源：用户要求“实验室模块里的 laya 功能完全删除”，明确舍弃该能力。
- 范围：有界功能删除，直接在唯一保留的 `codex/architecture-baseline` 分支实施。

## 实施

- 实验室仅包含 Laya：删除其页面、组件、API 包装、实验记录访问代码、示例、结果与模拟动作，移除全局导航及 `lab` 路由类型；旧 `#/lab` 沿既有未知路由规则回到总览。
- 删除后端路由、DTO、应用服务、模型下载/加载/推理运行时与生命周期注册，同时从无副作用 OpenAPI 导出和生成客户端类型移除契约。
- 从依赖与 PyInstaller 收集中移除 Laya 及专用推理组件；用现有锁文件离线解析依赖，不升级其余依赖。OCR 和语音所需的共享依赖保留。
- 不清除旧 localStorage 实验记录或已下载权重，不修改数据库迁移；本次无新增功能、依赖或替代实现。
- 历史实现决策、计划与参考资料标记 superseded；历史 QA 证据保留。

## 验证

- 删除前回归：前端旧路由/导航两条断言失败，后端旧 status 仍返回 200 而非 404；确认检查能捕获遗留入口。
- 静态检查：Ruff、mypy（545 个源码文件）、strict gate（893/893，new=0）、TypeScript、ESLint、OpenAPI check、结构检查 4 项和根脚本 111 项通过；源码、锁文件和打包配置的 Laya 入口扫描为 0。
- 依赖：离线更新锁文件只有 120 行删除；移除 laya、transformers、safetensors 及其无其他消费者的 CLI/渲染依赖，共 8 个包。运行环境确认三个专用推理包均不可导入，其余版本未升级。
- 前端生产构建通过。首次后端启动/关闭定向回归 19 passed / 1 failed（host 关闭超过 3 秒）；首次媒体/语音/真实识别回归 26 passed / 2 failed（project match 等待超时、ocr_stop 超过 15 秒）。原有时限均未修改。
- 首次隔离桌面检查在 60 秒就绪条件上超时，未计为通过。机器当时负载较高；失败事实保留，不把负载相关性当作已证明的根因。
- 前端全量：454 个文件，5961 passed / 4 failed；失败集中于未修改的 DataTableDetailPage（3 项）和 BatchDetailPage（1 项）。这两个文件与 navigation.test.tsx 使用 `--maxWorkers=1` 复查共 70 项全部通过，未修改断言或超时；不将定向复查表述为全量无失败。
- `npm run backend:build` 通过；归档不包含 Laya 或顶层 transformers/safetensors 包（其余库中同名 transformers 子模块仍按各自用途保留）。
- 第二次隔离真实 Electron 检查通过：健康接口 200，Laya status/predict 接口 404，OpenAPI 无实验室路径，全局导航仅保留六个现有业务入口，旧 `#/lab` 回到总览，页面显示本地服务正常。临时测试目录已清理。
- 后端合并定向复查 48 passed / 1 依赖弃用警告（167.13 秒）：覆盖 OpenAPI/退役接口、health/main、sidecar shutdown、环境启动装配、媒体执行器、语音契约、Studio 与 Project 真实识别 worker；原测试时限未修改。本次未重跑后端全部测试。
- `npm run smoke:sidecar -- --executable apps/backend/dist/autoflow-backend/autoflow-backend` 通过；新打包后端能启动并通过认证健康检查。
- `git diff --check` 通过。仅提交本次退役改动，不改既有未跟踪资料或其他工作树，不推送远端。源码可从 Git 历史恢复。
