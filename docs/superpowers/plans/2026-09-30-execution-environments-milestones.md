# 执行环境扩展（指纹浏览器管理与安卓设备平台）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本计划为任务级，按依赖滚动细化。** E1 在整改 M1 合并后细化为步骤级；E2 在整改 M4 合并后细化；E3–E5 在整改 M6 通过退出评审后细化；E6 是研究轨道，随时可做，只交付知识文档与脚本。每次细化都要按当时的代码核实文件路径与接口，经用户确认后再执行（`AGENTS.md`：架构改动需规格与计划获批）。

**Goal:** 让 CloakBrowser 公开版内核在批量场景下可控、可体检、可迁移，并把安卓做成与浏览器平级的通用执行环境（AVD 为主、ReDroid 保留），iOS 以 ADR 形式明确不做。

**Architecture:** 以整改 M4 的身份为中心：浏览器身份与设备身份共用代理粘性分配、地区校验、健康与处理台账。执行层新增两类"执行环境提供者"端口：`BrowserEnginePort`（E1，CloakBrowser 唯一实现）与 `AndroidRuntimePort`（E3，由现有 `domain/android/ports.py::AndroidRuntime` 演进，ReDroid-on-Lima 与 AVD 两个适配器），派发器通过资源端口租借，容量统一按内存预算计。所有能力"测试通过才显示"，兼容性"只来自证据"。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy + Alembic（迁移前缀 `ee1_`…`ee5_`）、`cloakbrowser==0.5.9`（升级走 R1-03 清单）、Playwright、Android SDK（emulator / platform-tools / 系统镜像）、scrcpy、adb、uiautomator2（R4-03 ADR 确认后）、React 19 + 整改 M5 设计系统、vitest、pytest。

**Spec:** [docs/superpowers/specs/2026-09-30-execution-environments-design.md](../specs/2026-09-30-execution-environments-design.md)

## Global Constraints

- 默认内核渠道为 `public`；不接入"登录后的最新免费版"。若将来接入，该渠道在派发器中强制并发 1（R1-02）。
- `cloakbrowser` 包版本升级前必须完成 `docs/references/cloakbrowser-upgrade-checklist.md`（R1-03）。
- 版本落后提示：Chrome 版本历史服务每 24 小时最多请求一次、本地缓存；离线时不提示、不报错；N ≥ 4 用警告样式（R1-05）。
- Camoufox 接入触发条件（只写 ADR，不实现）：公开渠道停止发布超过 6 个月、或落后稳定版 ≥ 8 个大版本、或出现并发限制（R1-06）。
- 被身份或模板引用的内核版本不可删除（R1-07）。
- 体检不访问第三方网站；外部检测页只截图、不解析（R2-01、R2-02）。
- 身份包加密：scrypt 派生密钥 + AES-GCM；代理凭据默认不导出（R2-05）。
- 不修改 IMEI、序列号、基带等硬件标识；不以绕过 Play Integrity / 应用反作弊为目标改造系统（非目标）。
- 内存预算：AVD 每台默认 3 GB，ReDroid 每台 1.5 GB，与浏览器共同受整改 M1 内存水位保护（R3-07）。
- 能力（相机、麦克风、定位、Google Play、音频、快照）只有在"运行时声明支持"且"该运行时 × 系统镜像组合已通过对应验收测试"时才显示为可用（R3-03）。
- 界面只用整改 M5 统一后的令牌、组件与 lucide 图标；安卓页面不再使用独立样式（R3-08）。
- 删除、重置设备需二次确认并写明会丢失的数据；Windows 上不自动更改系统虚拟化设置。
- 截图、录屏、检测页截图等产物放运行产物目录或 CI 产物，不入库。
- 整改期间安卓 / iOS 冻结（用户决定 4）：E3 及以后不得在整改 M6 通过退出评审前开工。

## Review Focus

1. **离线或版本服务返回异常数据**：版本落后提示静默不显示，内核页、身份页、启动流程全部正常（E1 Task 4 测试：断网、超时、返回非 JSON、返回主版本号小于本地内核）。
2. **身份包在另一台机器导入时种子已被占用**：拒绝或按用户选择重新生成，不产生两个同种子身份，也不部分写入（E2 Task 5 测试：冲突 + 导入中途失败回滚）。
3. **设备代理中转在设备运行中断开**：设备内出口 IP 检查失败时任务归为基础设施失败，不回落到本机直连网络（E3 Task 5 测试：中转进程被杀后设备流量被阻断而不是直连）。
4. **adb 连接在节点执行中途断开或设备被用户手动关闭**：当前任务按基础设施失败结束、设备状态刷新为"已停止/失联"，行按台账规则重试，不出现卡死的运行（E4 Task 1 故障注入测试）。
5. **群控中从设备屏幕分辨率与主控不同**：按比例换算坐标；"按元素同步"找不到元素时该从设备标记失败并可接管，其余继续（E5 Task 1 测试：1080×2400 主控 + 720×1600 从设备）。

---

## E1 内核渠道与版本治理（依赖整改 M1；M1 合并后细化为步骤级）

### Task 1: 渠道策略与 ADR

- Files:
  - Create: `.ai/decisions/YYYY-MM-DD-kernel-channel-policy.md`（R1-02 不接入登录版；若接入则强制并发 1；R1-06 Camoufox 触发条件）
  - Modify: `apps/backend/src/autoflow/providers/kernel/catalog.py`（`KernelRelease` 增加 `concurrency_note`：`public` → "官方未写并发限制，版本较旧"，`licensed` → "按授权套餐"）
  - Modify: `apps/backend/src/autoflow/adapters/http/kernel_schemas.py`、OpenAPI 生成物
  - Modify: `apps/desktop/src/renderer/domains/kernels/*`（按渠道分组、默认 `public`、显示并发说明）
- Interfaces:
  - Produces: `KernelRelease.channel: Literal["public","licensed"]`（已有 edition 字段按现名保留）、`KernelRelease.concurrency_note: str`
- Tests: `tests/unit/providers/kernel/test_catalog_channels.py`（两种渠道的说明文字、默认渠道）；前端 `kernels` 页面分组测试。

### Task 2: 升级评审清单

- Files: Create `docs/references/cloakbrowser-upgrade-checklist.md`，条目：公开渠道发布语义、`fingerprint` 种子范围、启动参数（`--fingerprint`、`humanize`、`human_preset`、`geoip`、`locale`、`timezone`）、并发限制、平台资产命名；每条写"如何核实"（读包源码的哪个文件 / 跑哪个脚本）。在 `AGENTS.md` 依赖升级规则处加一行链接。
- Tests: 无代码；由 Task 7 退出评审核对清单存在且被 `pyproject.toml` 注释引用。

### Task 3: 公开版并发实测（R1-04，结果决定 E1 是否继续）

- Files: Create `apps/backend/tests/golden/test_g2_public_kernel_concurrency.py`（参数化并发 2 与机器推荐值，使用公开渠道已安装内核；未安装时 skip 并说明）；结果写入 `.ai/knowledge/YYYY-MM-DD-cloakbrowser-public-concurrency.md`（内核版本、并发数、耗时、是否出现会话数限制错误）。
- Gate: 若出现会话数限制，E1 停止，把结论与"继续公开版 / 购买 Pro / 提前评估第二内核"三个选项交给用户决策。
- Tests: G2 在并发 = 推荐值下完成，无限制错误（AC-E1-1）。

### Task 4: 版本落后提示（R1-05）

- Files:
  - Create: `apps/backend/src/autoflow/providers/kernel/chrome_versions.py`（获取稳定版主版本号；24 小时缓存文件放工作区缓存目录；任何异常返回 `None`）
  - Create: `apps/backend/src/autoflow/domain/kernels/version_lag.py`（纯函数）
  - Modify: 内核列表与身份详情接口增加 `majorVersionsBehind: int | null`
  - Modify: 前端内核页、身份详情：N ≥ 4 警告样式
- Interfaces:
  - Produces: `latest_stable_major(now: datetime) -> int | None`、`major_versions_behind(kernel_version: str, stable_major: int | None) -> int | None`
- Tests: `test_version_lag.py`（落后 0 / 3 / 4 / 8；本地版本更高返回 0；解析失败返回 None）；`test_chrome_versions.py`（24 小时内只请求一次、断网 / 超时 / 非 JSON 返回 None 且不抛出——Review Focus 1）；前端离线时不渲染提示。

### Task 5: 内核抽象 `BrowserEnginePort`（R1-06）

- Files:
  - Create: `apps/backend/src/autoflow/domain/browser_engines/ports.py`
  - Create: `apps/backend/src/autoflow/providers/browser/cloakbrowser_engine.py`（把 `providers/browser/worker.py` 中组装启动参数的逻辑移入，worker 调用它；行为不变）
  - Modify: 身份模板（整改 M4 后为 `domain/identities` 模板）的内核字段为 `{engine: "cloakbrowser", edition, version}`；迁移 `ee1_engine_field.py` 为旧数据补 `engine`
- Interfaces:
  - Produces:
    - `EngineRef = TypedDict("EngineRef", {"engine": Literal["cloakbrowser"], "edition": str, "version": str})`
    - `class BrowserEnginePort(Protocol): def launch_options(self, ref: EngineRef, identity: IdentityLaunchSpec) -> dict[str, Any]: ...; def executable(self, ref: EngineRef) -> Path: ...`
- Tests: 对照测试：同一身份迁移前后生成的启动参数逐字段一致（`--fingerprint={seed}`、`expertArgs`、`locale`、`timezone`、`geoip`、`humanize`）；迁移在夹具工作区上重放。

### Task 6: 被引用内核不可删除（R1-07）

- Files: `application/kernels/service.py`（删除前查询身份与模板引用；返回 409 与引用者列表）、`adapters/http/kernels.py`、前端删除对话框显示引用者。
- Interfaces: Produces `kernel_references(version: str) -> list[KernelReference]`（`{kind: "identity"|"template", id, name}`）。
- Tests: 有引用时拒绝并列出；无引用时删除成功；并发"删除 + 新建引用"时以数据库事务保证不出现悬空引用。

### Task 7: E1 验收

- AC-E1-1、AC-E1-2 逐条勾选；更新 `.ai/plans` 索引与 `docs/PROJECT_STRUCTURE.md`；独立退出评审。

## E2 浏览器身份补强（依赖整改 M4、M5 5C 与 E1；M4 合并后细化为步骤级）

### Task 1: 本地探针页与一致性规则（R2-01）

- Files:
  - Create: `apps/backend/src/autoflow/providers/browser/probe/probe.html`、`probe.js`（采集 UA、平台、语言、Intl 时区、屏幕、hardwareConcurrency、deviceMemory、WebGL 厂商 / 渲染器、`navigator.webdriver`、WebRTC 候选 IP；只从本地回环地址加载）
  - Create: `apps/backend/src/autoflow/domain/identities/checkup_rules.py`（纯规则）
  - Create: `apps/backend/src/autoflow/application/identities/checkup.py`（按身份完整配置启动、读探针、从代理出口测 IP 与地理位置——复用整改 M4 Task 6 的出口检测与 10 分钟缓存）
  - Modify: 身份接口增加 `POST /identities/{id}/checkup`；前端身份详情"体检"卡片
- Interfaces:
  - Produces: `ProbeValues`（dataclass，上述字段）、`evaluate_checkup(probe: ProbeValues, exit_geo: ExitGeo, identity: IdentitySpec) -> list[CheckupItem]`，`CheckupItem = {rule, status: "pass"|"warn"|"fail", detail}`
- Tests: 规则单元测试覆盖：时区与出口地区不一致、语言与地区不一致、WebRTC 暴露非出口 IP、webdriver 为真、UA 与平台矛盾；集成测试用本地 SOCKS 夹具注入两种故障（AC-E2-1）；一致配置全部 pass。

### Task 2: 外部检测页（R2-02）

- Files: 身份详情"用此身份打开检测页"（预置 CreepJS、BrowserScan、Pixelscan 链接，可在设置中编辑）；打开后截图登记为运行产物。
- Tests: 截图作为产物登记而非写入仓库；不解析页面内容（代码审查项）。

### Task 3: 指纹快照与漂移（R2-03）

- Files: `ee2_fingerprint_snapshots.py`（表：identity_id、taken_at、source、normalized_json、digest）、`domain/identities/fingerprint_diff.py`（规范化：去掉时间类字段）、批量运行首个网页节点前采快照（派发器钩子）、批次监控汇总"本批有 N 个身份指纹发生变化"。
- Interfaces: `normalize_probe(p: ProbeValues) -> dict[str, Any]`、`diff_snapshots(prev: dict, cur: dict) -> list[FieldChange]`
- Tests: 两次无变化不提示；更换内核版本后列出变化项（AC-E2-2）；快照写入失败不阻断运行（记警告）。

### Task 4: Cookie 导入导出（R2-04）

- Files: `domain/identities/cookie_formats.py`（JSON：Playwright 与常见扩展格式；Netscape 文本；双向转换）、`application/identities/cookies.py`（导入写入该身份登录环境的新代次；导出当前代次）、前端导入预览（域名与条数）。
- Tests: 各格式往返一致；非法行报告行号不整体失败；导出再导入到新身份后夹具站点 `/account` 已登录（AC-E2-3 前半）。

### Task 5: 身份包导出 / 导入（R2-05）

- Files: `application/identities/package.py`（打包：元数据、种子、地区、内核版本、代理绑定引用、瘦身后的登录环境；可选代理凭据）、`infrastructure/crypto/package_cipher.py`（scrypt + AES-GCM，文件头含版本与 KDF 参数）、导入冲突处理（拒绝 / 重新生成种子）。
- Interfaces: `export_identity(identity_id, passphrase, include_proxy_credentials=False) -> Path`、`import_identity(path, passphrase, on_seed_conflict: Literal["reject","regenerate"]) -> ImportResult`
- Tests: 错误口令报"口令错误"而非解析异常；篡改密文被 GCM 拒绝；种子冲突时拒绝且数据库无残留（Review Focus 2，导入在单事务内，登录环境先写临时目录后原子移动）；另一工作区导入后种子、地区、登录状态一致（AC-E2-3 后半）。

### Task 6: 行为风格（R2-06）

- Files: 身份字段 `humanPreset: "off"|"default"|"careful"`；`cloakbrowser_engine.launch_options` 映射到 `humanize` / `human_preset`。
- Tests: 映射单元测试；同一身份多次运行使用同一预设。

### Task 7: 移动网页身份（R2-08 调研 → R2-07 实现）

- Step A（调研，先做）：核实 CloakBrowser 公开版是否支持移动 / 安卓平台指纹参数；写入 `.ai/knowledge/YYYY-MM-DD-cloakbrowser-mobile-fingerprint.md`，附验证脚本与探针页输出。
- Step B（实现）：身份模板"移动网页"类型，设备描述（UA、视口、像素比、触屏、isMobile）来自 Playwright 设备描述或 Step A 确认的内核参数；界面固定标注浅层伪装说明（规格 R2-07 原文）。
- Tests: 探针页读到的 UA、视口、触屏与模板一致；标注文字存在。

### Task 8: E2 验收

- AC-E2-1 至 AC-E2-3；更新 `.ai` 与目录文档；独立退出评审。

## E3 安卓设备平台（依赖整改 M6；M6 通过退出评审后细化为步骤级）

### Task 1: `AndroidRuntimePort` 与 ReDroid 适配器（R3-01）

- Files:
  - Modify: `apps/backend/src/autoflow/domain/android/ports.py`（`AndroidRuntime` 演进为 `AndroidRuntimePort`，保留旧名别名一个版本；新增 `capabilities()`）
  - Create: `apps/backend/src/autoflow/providers/android/redroid_lima/`（把 `providers/android/mac_runtime.py`、`management.py`、`stream.py` 按适配器组织，行为不变）
  - Modify: `bootstrap` 按运行时类型注册适配器
- Interfaces:
  - Produces: `RuntimeCapabilities = {googlePlay: bool, camera: bool, microphone: bool, location: bool, audio: bool, snapshots: bool, maxRecommendedInstances: int}`；`AndroidRuntimePort` 方法：`create / start / stop / snapshot / restore / delete / adb(args, timeout) / open_stream_session / capabilities`
- Tests: 现有安卓测试全部通过（回归基线先记录通过数）；端口契约测试以假适配器运行。

### Task 2: AVD 运行时（R3-02）

- Files:
  - Create: `apps/backend/src/autoflow/providers/android/avd/sdk_manager.py`（固定版本清单 `avd-sdk-manifest.json`：emulator、platform-tools、系统镜像的下载地址与 SHA-256；下载校验失败删除临时文件）
  - Create: `providers/android/avd/runtime.py`（`-no-window` 启动、端口分配、`adb wait-for-device` 与开机完成检测、scrcpy 接入）
  - Create: `providers/android/avd/host_checks.py`（Windows 检测 WHPX 并给出开启说明；Mac 检测 arm64；不自动修改系统设置）
- Tests: 清单摘要校验；端口分配无冲突；宿主检查在两平台的提示文案；集成测试标记 `avd`（需真机环境，CI 手动触发）；AC-E3-1 在 Mac 与 Windows 各跑一遍（记录在验收记录）。

### Task 3: 能力如实标注（R3-03）

- Files: `domain/android/capability_matrix.py`（运行时声明 ∧ 组合验收记录 → 可用 / 不可用 + 原因）、验收记录存 `ee3_capability_verifications.py`、前端能力徽标。
- Tests: 声明支持但无验收记录 → 不可用并写明"尚未验证"；验收失败 → 不可用并写明失败现象。

### Task 4: 设备生命周期（R3-04）

- Files: `application/android/devices.py` 扩展克隆、快照 / 恢复、重置；删除 / 重置二次确认接口（返回将丢失的数据清单后需确认令牌）；沿用 `application/android/backups.py`。
- Tests: 无确认令牌的删除被拒绝；快照恢复后安装的 APK 与文件一致；ReDroid 路径回归。

### Task 5: 设备身份与代理（R3-05）

- Files: 身份增加可选 `deviceId` 关联；`providers/android/proxy_relay.py`（宿主侧每台设备独立中转，复用 `providers/browser/proxy_relay.py` 的实现方式）；设备启动后在设备内测出口 IP 并与身份地区比对；地区（语言、时区、定位）与设备型号 / 屏幕模板写入设备配置。
- Tests: 设备内出口 IP 等于代理出口（AC-E3-2）；地区不一致拒绝启动任务并说明；中转进程被杀后设备流量被阻断而非直连（Review Focus 3）；代码中无 IMEI / 序列号修改（审查项）。

### Task 6: 操控（R3-06）

- Files: scrcpy 音频可选开启、剪贴板同步、文件传入 / 导出、APK 与 XAPK / APKS 安装（`application/android/apk.py` 扩展分包安装）、应用列表与卸载。
- Tests: 分包安装夹具（含 split APK）；剪贴板双向；文件路径穿越被拒绝。

### Task 7: 容量（R3-07）

- Files: `domain/android/capacity_rules.py` 改为按内存预算（AVD 3 GB、ReDroid 1.5 GB，可在设置中调整）；接入整改 M1 的内存水位；设备管理页"本机还可启动约 N 台"。
- Tests: 浏览器与设备混合占用下，超过水位时拒绝新启动并给出原因；N 的计算单元测试。

### Task 8: 界面（R3-08）

- Files: `apps/desktop/src/renderer/domains/android/*` 按"我的设备 / 系统库 / 设备工作台 / 运行环境"重组，只用整改 M5 设计系统组件；移除独立样式文件。
- Tests: 页面测试；守门 `paletteClasses` 与 `secondIconLibraryFiles` 仍为 0；视觉回归。

### Task 9: E3 验收

- AC-E3-1、AC-E3-2；更新 `.ai`（把 `2026-09-19-android-management-scope.md` 中与本规格冲突的部分标记 superseded）；独立退出评审。

## E4 安卓接入执行引擎（依赖 E3 与整改 M2 台账、M6 统一执行引擎）

### Task 1: `androidDevice` 环境策略（R4-01）

- Files: `domain/project_automations/rules.py`（环境策略 `androidDevice`：固定设备 / 按身份绑定设备 / 设备池）、资源端口租借设备（与浏览器同一租借接口）、失败分类（adb 断开、设备失联 → infrastructure）。
- Tests: 三种策略的解析；设备被占用时排队；故障注入：节点执行中 adb 断开 → 任务结束、设备状态刷新、行按台账重试，无卡死运行（Review Focus 4）。

### Task 2: 元素定位选型 ADR 与驱动（R4-03）

- Files: `.ai/decisions/YYYY-MM-DD-android-automation-driver.md`（uiautomator2 与 Appium 对比：部署体积、速度、Windows 支持、许可证；结论）；`providers/android/automation/driver.py`（按文字、资源 ID、描述、类名、XPath 定位；拿不到元素时截图识别兜底）。
- Tests: 用设置应用做定位契约测试；兜底路径测试。

### Task 3: 移动端节点（R4-02）

- Files: 约 12 个节点执行器（启动 / 停止应用、点击、滑动、输入、按键、等待元素、读取文本、截图、找图点击、OCR 点击、安装应用、按描述操作〔可选，使用模型管理中的视觉模型〕），每个声明输出契约（整改 M6 Task 3）；模块目录"移动端"分组。
- Tests: 每个执行器单元测试 + 输出声明测试；目录清单测试更新。

### Task 4: 设备内 Chrome（R4-04，先调研）

- Step A：调研 `adb forward tcp:<port> localabstract:chrome_devtools_remote` + Playwright `connect_over_cdp` 的稳定性与可用 API，结论写入 `.ai/knowledge`。
- Step B（可行时）：网页节点在 `androidDevice` 环境下经转发接入设备 Chrome；不可行时在规格中记录并改用移动端节点操作 Chrome。
- Tests: 夹具站点表单提交通过（G5 后半）。

### Task 5: 录制（R4-05）

- Files: 设备工作台录制（点击同步抓元素树，优先生成元素定位节点，坐标作后备）。
- Tests: AC-E4-2。

### Task 6: 试跑与批量（R4-06）与黄金场景 G5

- Files: Studio 试跑选择设备；批量每行一台设备或设备池；共用运行结果页、任务时间线与失败归组；`tests/golden/test_g5_android.py`（20 行：设置中搜索并读结果 + 设备内 Chrome 提交表单）。
- Tests: AC-E4-1。

### Task 7: E4 验收

- AC-E4-1、AC-E4-2；独立退出评审。

## E5 群控与兼容记录（依赖 E4）

### Task 1: 群控（R5-01）

- Files: `application/android/group_control.py`（主控事件捕获、按屏幕比例换算、可选按元素同步、从设备失败隔离与接管）、设备工作台群控面板。
- Tests: 1 主 3 从同步 20 步（AC-E5-1）；不同分辨率换算与找不到元素时的单设备失败（Review Focus 5）；一台断开其余继续。

### Task 2: 兼容记录（R5-02）

- Files: `ee5_compatibility_records.py`（包名、版本、运行时、系统镜像、状态：能安装 / 能启动 / 能登录 / 能正常使用 / 被拦截、现象、截图产物引用、来源：人工 / 疑似）；批量运行中启动失败或已知拦截提示自动记"疑似"；设备创建页与设备池选择显示目标应用记录。
- Tests: AC-E5-2；疑似记录未确认前不影响显示为"已验证"。

### Task 3: E5 验收

- AC-E5-1、AC-E5-2；独立退出评审。

## E6 厂商系统实验（研究轨道，随时可做，不改产品代码）

### Task 1: 按研究文档 A–E 阶段执行（R6-01）

- Files: `docs/research/android-manager-2026-09-30/experiments/`（每阶段一份记录：环境、步骤、结果、截图产物链接）、可复现脚本放 `scripts/research/android-vendor/`。
- 产出：`.ai/knowledge/YYYY-MM-DD-android-vendor-rom-findings.md`。

### Task 2: 候选晋级（R6-02）

- 只有"同一镜像组合跑通用户实际动作"的候选才写新规格进入 E3 系统库，并标注为实验；本任务只产出规格草稿交用户审批。

## iOS 决策

### Task 1: iOS ADR（R7-01、R7-02）

- Files: Create `.ai/decisions/YYYY-MM-DD-ios-not-supported.md`：理由（Simulator 不能装 App Store 应用；Corellium 为商业产品；Chromium 伪装 iOS Safari 差异过大）；重新立项条件（明确业务需求 + 接受实体 iPhone）；届时参考 WebDriverAgent、go-ios、pymobiledevice3、Zebrunner mcloud。
- 可随本计划获批立即提交（纯文档）。

## 自检记录

- 规格覆盖：R1-01→E1-T1；R1-02→E1-T1；R1-03→E1-T2；R1-04→E1-T3；R1-05→E1-T4；R1-06→E1-T5（ADR 在 T1）；R1-07→E1-T6；R2-01→E2-T1；R2-02→E2-T2；R2-03→E2-T3；R2-04→E2-T4；R2-05→E2-T5；R2-06→E2-T6；R2-07/R2-08→E2-T7；R3-01…R3-08→E3-T1…T8；R4-01→E4-T1；R4-02→E4-T3；R4-03→E4-T2；R4-04→E4-T4；R4-05→E4-T5；R4-06→E4-T6；R5-01→E5-T1；R5-02→E5-T2；R6-01/R6-02→E6-T1/T2；R7-01/R7-02→iOS-T1。
- 验收覆盖：AC-E1-1→E1-T3；AC-E1-2→E1-T1/T4/T6；AC-E2-1→E2-T1；AC-E2-2→E2-T3；AC-E2-3→E2-T4/T5；AC-E3-1→E3-T2/T4；AC-E3-2→E3-T5；AC-E4-1→E4-T6；AC-E4-2→E4-T5；AC-E5-1→E5-T1；AC-E5-2→E5-T2。
- 文件路径按 2026-09-30 的代码核实（`providers/kernel/catalog.py`、`domain/android/ports.py`、`providers/android/mac_runtime.py`、`providers/browser/proxy_relay.py` 存在）；整改后会移动的路径（身份、派发器、资源端口）在细化时重新核实。
