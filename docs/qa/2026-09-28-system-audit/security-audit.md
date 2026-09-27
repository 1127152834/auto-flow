# AutoFlow 安全边界与后端架构审计

- 日期：2026-09-28。
- 状态：confirmed（下述实际复现与源码事实）；Electron 导航的实际影响为待验证。
- 源码基线：`33ae3aa49600840b1700c83723408c494dc201a8`，审计期间未修改业务代码；已有工作区修改保留。
- 范围：本机 HTTP 认证、Electron IPC/导航、凭据命名空间、共享文件路径边界、脚本权限隔离。不是完整渗透测试、依赖漏洞数据库扫描或跨平台验收。
- 环境：当前 macOS；真实 TCP HTTP、真实临时文件、真实 SQLite 迁移和 macOS Keychain。没有用 mock 替代这些依赖，没有读取既有用户凭据或生产数据，没有外发数据。

## 结论

发现 **3 项已真实复现的安全/隔离缺陷、1 项已真实复现的功能缺陷，以及 1 项仅源码确认、动态影响待验证的 Electron 防御缺口**。

本地自动化允许执行用户脚本、读写用户选择的文件、连接内网和启动局域网共享，这些能力本身不列为漏洞。以下缺陷针对已经声明或代码中已经实施的工作区、共享根目录和可信界面边界。

| 编号 | 优先级 | 发现 | 置信度 | 证据状态 |
|---|---|---|---|---|
| SEC-01 | P1 | 共享目录普通静态 GET 绕过路径约束，经符号链接读取共享目录外文件 | 高 | 真实 HTTP 与真实文件复现 |
| SEC-02 | P1 | 重名上传生成新路径后不再校验，跟随悬空符号链接在共享目录外创建文件 | 高 | 真实 multipart HTTP 与真实文件复现 |
| SEC-03 | P1 | 不同工作区的同名 Studio 凭据共享一个系统键，互相覆盖、删除 | 高 | 两个真实 SQLite 库与唯一新建 Keychain 条目复现 |
| FUNC-01 | P2 | 文件共享文档预览依赖缺失模块，合法请求返回 500 | 高 | 真实 HTTP 复现 |
| SEC-04 | P2 | 主窗口缺少导航拦截，敏感 IPC 不检查发送页面 URL | 源码事实高；实际利用链未知 | 未执行导航、提权或 token 转移测试 |

P1 表示应在向真实业务共享目录、多个工作区推广前修复；不是在无前置条件下远程利用的结论。P2 表示明确防御或功能缺口，仍应进入修复计划。

## SEC-01：静态文件回退绕过共享根目录

源码：`apps/backend/src/autoflow/infrastructure/sharing/file_share.py:437-439`。

调用链为 `NetworkShareHost.perform(start_file_share)` → `start_file_share()` → `FileShareHandler.do_GET()`。专门的 `/download/`、`/preview/` 等路径会解析真实路径并检查是否位于共享根目录，但其他 GET 直接调用 `SimpleHTTPRequestHandler.do_GET()`。共享内的符号链接因此绕过前述约束。

触发前提：用户启动目录共享；共享目录中已有指向目录外文件的符号链接；请求者能访问该共享端口。生产启动器在同文件 `808` 行绑定 `0.0.0.0`，实际可访问范围仍受系统防火墙/网络限制。本次测试只绑定 `127.0.0.1`，没有开放局域网端口。

真实结果：同一个真实链接 `/linked-report.txt` 返回 **200，正文等于共享目录外的 QA 专用文件**；`/download/linked-report.txt` 返回 **403**。这直接证明相邻分支的安全边界不一致，不需要竞态或读取用户文件。

建议：让普通静态 GET/HEAD 使用同一根目录校验；拒绝解析后越界的链接；避免仅修 `/download/` 单一路由。若支持共享目录内的可变链接，还需避免检查与打开之间的路径替换竞态。

## SEC-02：重复文件名上传绕过最终路径检查

源码：`apps/backend/src/autoflow/infrastructure/sharing/file_share.py:259-277`，关键未校验的新路径在 `273-277` 行。

上传先检查原始 `file_path`，遇到重名文件后循环生成 `report_1.txt` 等名称，然后直接 `open(..., 'wb')`。`Path.exists()` 对指向不存在目标的符号链接返回 false，因此循环会把该链接当成空闲文件名，`open()` 再跟随链接创建目录外目标。

触发前提：共享允许写入；根目录中已有 `report.txt` 和 `report_1.txt`，后者是指向共享目录外不存在文件的悬空符号链接；请求者向 `/api/upload` 上传同名 `report.txt`。单靠此 HTTP API 是否能够预先创建该符号链接未证实，也不作为本结论的前提。

真实结果：HTTP 返回 **200 / success=true**，共享目录外的专用目标文件被创建，内容与本次上传完全相同。本次证明的是目录外文件创建，未证明能够覆盖已存在的任意目标文件。

建议：在最终候选名称确定后重新检查路径，使用不会跟随符号链接的排他创建策略并在文件已存在时重新选名。只增加初始路径检查无法修复此分支。

## SEC-03：工作区凭据命名空间串扰

源码：

- `apps/backend/src/autoflow/application/workflows/credentials.py:198-221`：系统存储键仅为 `studio-credential:sha256(name)`，读、写、删除共用这个键。
- 同文件 `40-48` 行：新增/更新先读取同名系统条目并合并，再写入当前工作区的元数据。
- `apps/backend/src/autoflow/bootstrap/app.py:348-349`：凭据元数据使用当前工作区的 `session_factory`。
- `apps/backend/src/autoflow/infrastructure/credentials/system.py:11`：系统 service 名固定为 `dev.autoflow.credentials`。

触发前提：同一 OS 用户使用两个工作区，并在两个工作区创建相同名称的 Studio 凭据。这是正常工作区使用路径，不需要恶意输入或并发。

真实过程：使用两个临时 SQLite 数据库，运行全部真实迁移；使用当前生产 `StudioCredentialService` 和 `SystemCredentialStore`；凭据名为本次新生成 UUID，写入前确认该键不存在。

1. A 工作区保存测试凭据。
2. B 的元数据列表初始为空；B 保存同名但不同的测试值。
3. A 解析出的值已变成 B 的值。
4. B 删除该凭据后，A 的元数据仍存在，A 解析结果变为 `{}`。

影响：自动化可能在错误账号上执行，或因另一个工作区删除凭据而失效。源码还显示新增同名凭据会合并全局旧条目；本次未额外验证跨字段合并的影响。

建议：以稳定工作区身份参与凭据键，或使用存于元数据的独立随机凭据 ID。迁移应识别旧共享键的多工作区冲突，不应直接批量删除旧键；工作区移动或重命名也不能改变其凭据身份。

## FUNC-01：共享预览模块没有迁入

源码：`apps/backend/src/autoflow/infrastructure/sharing/file_share.py:581-584` 导入 `.file_preview.get_preview_content`，当前 `infrastructure/sharing/` 中不存在 `file_preview.py`。

真实结果：共享内现有普通文件的 `/preview/report.txt` 请求返回 **500**，错误正文包含缺少 `autoflow.infrastructure.sharing.file_preview` 的信息。执行会在判断支持的文档类型前失败，因此问题不限于本次测试文件的扩展名。未额外执行 Office 文档渲染。

建议：接入已有可用预览能力，或让不支持的预览明确返回能力不可用；不要保留必然导入失败的端点。

## SEC-04：Electron 主窗口导航和 IPC URL 缺口（未动态验证）

源码事实：

- `apps/desktop/src/main/index.ts:79-80,188-193` 创建并加载主窗口，没有注册 `will-navigate` 拦截或 `setWindowOpenHandler`；全目录检索显示这两项仅在 Studio 窗口实现。
- `apps/desktop/src/main/ipc/automation-studio.ts:91-92` 对 Studio 明确实施上述限制。
- `apps/desktop/src/main/index.ts:61-62,258-262` 的运行时上下文、sidecar 状态和路径 IPC 只校验窗口 ID/main frame，不校验 frame 的 URL。
- `apps/desktop/src/preload/index.ts:69-87` 暴露能力 API，包含 `getSidecarStatus()`；`main/sidecar/supervisor.ts:22` 的 ready 状态包括实例 token。

潜在前提：存在能让主窗口加载非受信页面的导航路径。代码缺少共同的可信页面约束，但本轮 **未证明产品现有数据输入能够产生这条导航路径，也未证明导航后的 IPC 调用、token 读取或 HTTP 操作成功**。不能将其描述为已复现的任意远程代码执行。

建议：复用 Studio 的外部导航/新窗口拒绝行为，并在集中 IPC 授权处校验预期应用页面来源。后续在明确允许的隔离桌面环境补充真实导航与能力撤销验收。

## 已检查的正向边界

以下除共享 `/download/` 的 403 外均为源码检查，不等价于通过完整动态安全验收：

- `autoflow/__main__.py:64-65` 拒绝非 `127.0.0.1` sidecar host；Electron supervisor 使用随机端口和 32 字节随机实例/host token。
- `bootstrap/app.py:702-724` 对 `/api/` 验证实例 token；`/internal/` 需独立 host token，并拒绝有 Origin 的请求。Webhook 是有意例外，应按其配置的 header/param 校验审查，不能直接称为认证绕过。
- CORS 只配置 renderer origin，不是通配符。`file:` renderer 对应 `null` origin 本身不代表自动获得 token。
- Electron 两种窗口均开启 context isolation/sandbox，并关闭 node integration；Studio 拒绝导航和新窗口。
- `SystemCredentialStore` 要求操作系统 keyring backend；没有看到凭据不可用时回退明文文件的逻辑。
- `infrastructure/process/workflow_subprocess.py:38-41` 的 worker 环境过滤实例/host token；没有把合法 Python/JS/命令节点本身视为漏洞。
- 共享下载路径的符号链接越界负向检查真实返回 403，说明问题是遗漏的相邻路径，而非所有文件访问都未保护。

## 证据、清理与限制

- [`security/real_share_probe.py`](security/real_share_probe.py)：已执行的真实共享服务探针；[`security/real-share-results.json`](security/real-share-results.json) 保存结果。三个缺陷结果分别为静态读取 200、目录外创建成功、预览 500；受控下载路径返回 403。
- [`security/real_credential_probe.py`](security/real_credential_probe.py)：已执行的真实双工作区/Keychain 探针；[`security/real-credential-results.json`](security/real-credential-results.json) 只保存布尔结果；迁移日志为 [`security/real-credential-migrations.log`](security/real-credential-migrations.log)。不保存名称、秘密值或现有条目。
- 共享测试在 `finally` 中关闭 HTTP 服务、关闭 socket 并等待线程；临时根目录退出后自动清理。
- 凭据测试在 `finally` 中只删除本次新建的唯一 UUID 键；删除后实际回读为不存在，结果 `unique_test_key_removed=true`。两个临时数据库已清理，连接池已 dispose。
- 收到停止进一步跨边界动态验证的协调指令后，仅整理已取得的证据和源码。未创建或启动 Electron 导航测试脚本或 Electron 测试进程，没有继续做凭据操作。
- 已完成的两项探针工具调用均返回退出码 0；这只表示预期缺陷被成功复现，不表示产品安全检查通过。
- 未执行：Windows/macOS Intel/发行包、真实用户凭据、互联网或局域网攻击链、依赖 CVE 扫描、DoS/资源耗尽、全量文件格式、真实 Electron 导航后的能力测试。上述未知项目不能计为通过。
