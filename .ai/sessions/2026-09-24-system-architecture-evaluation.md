# 系统架构评估与执行引擎优化建议

- 日期：2026-09-24
- 状态：confirmed（用户已确认评估范围与最优先方向）；proposed（建议切片尚未启动）
- 来源：用户提出"以外部架构师身份评估 manage9 与未合入分支，给出系统缺什么与未来优化方向"
- 视角：外部架构师/设计师，2026-09-24 进入
- 主分支：`codex/project-management-pm9`（HEAD `6d0d5e0b`），其上 R1–R2 已推进到变量/字符串/列表字典/数学/工具/基础网页/页面加载/高级浏览器节点/Tab 切换/Telegram/邮件/网络共享

## 已确认事实

- 后端 5844 个 `.py`（68 领域 + 143 应用），前端 995 个 `.ts/.tsx`；382 后端测试（139 集成 + 116 单元 + 78 契约），244 前端测试文件
- `pm9/verification.json`：后端 3159 passed / 15 skipped；前端 5445 passed；CloakBrowser 四节点生产链 8 项 passed / 49s；全图未覆盖
- 三平台 CI：macOS arm64 通过、Win x64 与 macOS Intel 在 Actions 35507610003 进行中
- 实机：`darwin-arm64` DMG 已构建但未签名/未公证/未手装；`darwin-x64` 与 `win32-x64` 状态 `not-verified`
- `packages/ui` 是空骨架（4 个 `.gitkeep`），实际 UI 在 `apps/desktop/src/renderer/shared/components/ui`
- 架构规格 `docs/architecture/README.md` 把 `packages/ui` 列为目标，与现实脱节

## 未合入分支现状

| 分支 | 内容 | 关系 |
|---|---|---|
| `codex/android-management-complete` (9-23) | Android 项目持久化批量记录 HTTP | 未合入 |
| `codex/android-management-am1-20260919` | AM1 实施授权；T01 准备因执行环境阻塞 | 未合入 |
| `codex/laya-lab` (9-23) | Laya 决策实验 | **已合入 HEAD** |
| `codex/studio-backend-wip-20260918` | Studio 后端 checkpoint | 历史归档 |
| `codex/architecture-baseline` | PM8 + Studio + Android 规划合并点 | 已作为 manage9 起点 |

## 现状评估（系统还缺什么）

### 结构性缺口

- **两套执行循环并存**：项目 worker 用旧 `WorkflowExecutor`（`apps/backend/src/autoflow/providers/browser/project_workflow_worker.py`），节点白名单仅 4 个（`open_page`/`input_text`/`click_element`/`get_element_info`），`run_validation.py` 仅线性链；Studio 用新版 `WorkflowRuntime`（`apps/backend/src/autoflow/application/workflows/runtime.py`）。规格自身已点名（`docs/superpowers/specs/2026-09-20-pm9-production-runtime-integration.md` §当前断点）。
- **`packages/ui` 空壳**：与架构规格长期不一致。
- **跨进程 capability 协议未稳定**：worker 缺受限 capability request/result 消息，`application/project_data/capabilities.py` 未进入协议。
- **全局资源引用保护不完整**：删除 Profile/内核/代理/模型只查运行时占用，未查项目静态引用（`application/profiles/service.py:95` 注释）。
- **文档-代码漂移**：至少 7 处 memory 显式声明 superseded，`.ai/sessions/` 已 194 个摘要。

### 功能性缺口

- **R3（End/人工/环境复用）未接入**：`pm9-integration-spec.md` §4。
- **R4（发行链 + 三平台实机）未完成**：`pm9/verification.json#platforms`。
- **Android 真实设备管理未启动**：AM1 因环境阻塞停摆，`android-am1-authorized.md` §2。
- **真实 Sheets 全链路未执行**：仍处于 fake executor 驱动（PM4 验收边界）。
- **1000 logs/min、内存增长、全 UI 交互体积未验**。
- **用户手测全部缺失**：PM8 收尾 "M-01…M-13"。

## 优化建议（按优先级）

### P0：执行引擎双循环合一（用户最优先）

- R1（进行中）：四节点生产兼容链，`bootstrap/workflows.py::configure_project_workflow_runtime` 接入 `WorkflowRuntime`，验证源码+打包共用同一 JSONL 协议
- R2（进行中）：项目数据 + 完整图，受限 capability RPC、数据读写、幂等
- R3：End/人工/环境复用，复用 `environments/retention.py::end_task` 与 `environments/manual.py`，等待 worker 浏览器真实关闭
- R4：发行链，三平台同版本完整链、Sheets 实网结果、失败后续/归档恢复/安全删除
- 额外建议：
  - 拆 `project_workflow_worker.py` 中的节点能力与项目上下文边界（抽出 `project_runtime_runner.py`）
  - capability 协议白名单（`data.query` / `data.write` / `env.save` / `manual.request` 等固定名）
  - Run timeline 可重放（visitId + attempt + input/output digest + capability request/result）

### P1：多平台发行与实机验收

- `scripts/release-evidence-collect.mjs`：macOS arm64/x64 + Win x64 的 codesign 验证 / 安装 / 启动 / smoke / 报告输出
- 必须等 R1–R3 通过才有意义

### P2：前端组件化与 `packages/ui` 落地

- 反向迁：`shared/components/ui` 中确认稳定的 5 个高复用控件 → `packages/ui` workspace
- 顺序：盘点 → 建 workspace → 切业务引用 → 旧路径 `@deprecated` 一代再删

### P3：Android 完整接入

- 第一步：仅做代码归并与契约对照（不动业务），形成 compatibility matrix
- 第二步：等 AM1 环境阻塞解除，本机 Apple Silicon + 隔离 ReDroid 跑真实设备管理

### P4：质量工程长期投资

- 测试金字塔：核心类单元覆盖率提至 80%+
- 可观测性：统一 Run timeline view
- 错误恢复演练：每月 `docs/drills/<date>.md`
- 文档一致性：`scripts/check-ai-consistency.mjs`

## 取舍说明

| 取舍 | 建议 |
|---|---|
| 双循环合一 | 做；放弃统一只扩白名单是长期积债 |
| `packages/ui` 立即启用 | 暂缓；P0–P1 后再迁 |
| Android 先归并 | 是；不涉及业务 |
| 发行证据自动化 | 做；放 P1 不抢 P0 |
| 文档一致性 CI | 做轻量校验，不强制阻断 |

## 用户拍板结果

| 问题 | 用户选择 |
|---|---|
| P0 双循环合一怎么走 | **按 PM9 R1–R4 现有切片继续**（不单独出技术方案） |
| Android 代码归并是否并行 | **保持隔离不归并**（两个 Android 分支维持独立工作树） |
| 文档-代码一致性 CI | **纳入但不阻断**（warn-only） |

## 推荐执行节奏

1. 继续 PM9 R1→R4，不插入新切片
2. PM9 验收后启动 P1 + P2
3. Android 分支保持隔离，AM1/AM2+ 按各自计划推进
4. P4 文档一致性脚本纳入 CI warn-only，以独立 PR 形式穿插

## 剩余风险与待用户拍板

- 风险：所有结论基于 `git log` / `find` / `.ai/` 与 `docs/` 的静态证据，未在 R1–R4 真实执行链路下重跑
- 已拍板完毕：本评估任务完成，评估结果已沉淀至 `.ai/sessions/2026-09-24-system-architecture-evaluation.md`
