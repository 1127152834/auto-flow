# 浏览器管理整分支最终审查

- 日期：2026-09-12。
- 状态：confirmed，第一轮最终只读审查完成；2 Important、3 Minor，等待修复复审。
- 代码基准：`1b18a587a11afabac5f44cd5806278cfe9612a05` → `b5e2832a3e8e73c8452a811167523e9c943a59e7`。后续 `9adb3a7`、`dd86e72` 为报告/证据归档，没有改变本报告所引生产代码。
- 唯一功能基准：`docs/superpowers/plans/2026-09-12-browser-management.md`、`docs/prototype/browser-management/browser-management-interactions.md`；实施裁决以 `progress.md` 和 `docs/migration/browser-management-decisions.md` 为准。
- 结论：**修完 Important 后再合并/交付；当前不能标为最终 PASS。置信度：高。** 没有发现 Critical。这里的“交付”是本次模块交付，不代表 Windows/Intel 或商业 License 已验收，也不代表未签名目录包成为发行安装器。

## 审查范围与优点

这次按风险分段查看最终源码、相关差异和测试，不把 405 文件审查包一次性读入，也不声称逐行重新审完全部生成类型、并行模块和历史文档。重点覆盖了配置 domain/schema/service/repository/form/hooks、内核 provider/worker/operations/安装目录/default/License、HTTP/SSE、ApiProvider/App、host reveal、settings quiesce 与 supervisor 退出边界。已读取逐任务记录、平台验收报告和归档的公开内核下载/取消 JSON。代理、模型、设置和总览是用户另行授权成果，未将其存在归为范围扩张。

- 配置 API 使用生成 DTO，camelCase 转换和 RHF/Zod 表单字段基本一致；viewport=null、代理模式清空无关 ID、公开版 Stable、资源失效校验与复制新指纹都有对应实现及测试。
- React 领域组件通过共享客户端访问业务 API。内核只有表单内 Modal 入口，没有独立内核导航；同工作区连接更换不会通过 React key 销毁编辑树，mutation 明确禁用自动重试，认证恢复没有重放写请求。
- 安装使用独立 worker、任务 staging、OS 安装锁、路径归属验证和原子发布；已有安装不被取消/失败覆盖。默认项用 revision 条件写，删除与默认/安装共用互斥，License 下载与退出存在明确互斥边界。
- 凭据留在系统存储及 worker stdin；host-only 内核路径解析与 IPC 对引用、来源窗口、loopback 地址、真实目录边界再次验证。没有发现 renderer 获得任意路径打开或取密能力。
- 已有测试覆盖真实数据库、worker 子进程、取消/强杀、启动补偿、HTTP 契约和 UI 状态；本机真实公开版下载/取消及 packaged Electron CRUD 证据比单纯 mock 验证更充分。

## 规格符合性与架构判断

| 检查项 | 判断 |
| --- | --- |
| 单主内容区、全局导航、四横向标签、嵌套内核弹窗 | 符合；没有重引入旧侧栏或独立内核页面 |
| 配置 CRUD、复制、重新生成指纹、分页/搜索/代理过滤 | 主路径符合；复制冲突字段关联有 M1 |
| 内核下载、取消、状态展示、失败后重试 | 主路径存在；目录缺少活动版本时取消入口丢失，有 I2 |
| 默认项 revision、安装/删除互斥、失效引用 | 核查路径未发现新的阻塞缺陷 |
| 进程生命周期及崩溃恢复 | 单 worker 监管及恢复已有覆盖；SSE 与正常退出组合存在 I1 |
| SSE/HTTP 状态合并 | 已核实终态不被旧 POST/cancel 覆盖、cached-only ID 保留及旧实例事件废弃；未发现新阻塞项 |
| 断线保留草稿、不重放写操作 | 实现主要符合；操作结果不确定时的离线文案有 M2 |
| 真实商业 License 与三平台发布 | 不能判为已验证：没有 License，Windows/Intel 等待对应运行证据 |

总体分层符合批准架构。本报告没有提出换框架、增加通用事件平台或重构整个共享壳；下述问题可在现有边界内修复。

## 问题

### Critical

无。

### Important

#### I1. 常驻 SSE 阻塞正常退出，host 最终只能强制终止 sidecar

- **定位：** `apps/backend/src/autoflow/adapters/events/kernels.py:40`；相关装配 `apps/backend/src/autoflow/__main__.py:57`、`apps/backend/src/autoflow/bootstrap/app.py:156`；桌面调用链 `apps/desktop/src/main/index.ts:102`、`apps/desktop/src/main/sidecar/supervisor.ts:167`。
- **触发：** 浏览器页面已挂载后直接从应用菜单/Cmd+Q 退出。`KernelManagerDialog` 即使关闭也保持挂载和 SSE 订阅；`before-quit` 阻止窗口关闭，先等待 `settings.shutdown()`。后端 SSE 是无限流，Uvicorn 的现有连接等待发生在 lifespan shutdown 之前，并且没有设置 graceful-shutdown 超时，所以 `kernel_worker_manager.shutdown()` 尚未执行。桌面 3 秒超时后走 SIGKILL。
- **影响：** 正常退出稳定退化为超时强杀；正在下载时跳过正常 worker 取消、任务落终态与 staging 清理，转而依赖父进程消失监测和下次启动恢复。现有恢复能降低后果，但不能替代正常退出清理。没有把它夸大为已证实的数据损坏或永久 orphan worker。
- **本轮实测：** 隔离真实源码 sidecar，成功收到 `/api/v1/kernels/events` 初始快照；保持流打开并发送 SIGTERM，等待 3.5 秒仍不退出；关闭该流后立即结束，Python subprocess returncode 为 `-15`。检查已安装 Uvicorn `Server.shutdown` 源码确认它先等待连接/任务，再调用 lifespan shutdown。此复现没有启动下载 worker，也没有运行真实 Electron Cmd+Q；桌面强杀分支及其清理后果由上述源码调用链确认，不声称本轮观察过 worker 遗留。
- **建议修复：** 在正常终止开始时结束 SSE，或明确设置有界连接排空并为应用 shutdown/worker 清理留足预算；也可在 host 等待 sidecar 前可靠停止 renderer 流。不要只延长 host 的 3 秒超时。补真实进程测试：保持 SSE 打开→请求正常退出→不靠 SIGKILL 完成；另覆盖活动 worker 的退出后 PID、staging 和持久任务状态。
- **置信度：高。**

最小复现命令（仓库根目录执行；只用临时目录，不下载内核）：

```sh
uv run --directory apps/backend python - <<'PY'
import os, subprocess, tempfile, json, httpx
with tempfile.TemporaryDirectory(prefix='autoflow-final-review-') as root:
    env = {**os.environ, 'AUTOFLOW_INSTANCE_TOKEN': 'review-token',
           'AUTOFLOW_HOST_TOKEN': 'review-host-token'}
    p = subprocess.Popen(
        ['python', '-m', 'autoflow', '--port', '0', '--instance-id',
         'review-sse-shutdown', '--data-dir', root],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        ready = json.loads(p.stdout.readline().removeprefix('AUTOFLOW_READY '))
        with httpx.Client(trust_env=False, timeout=5) as client:
            with client.stream('GET',
                f"http://127.0.0.1:{ready['port']}/api/v1/kernels/events",
                headers={'x-autoflow-token': 'review-token'}) as response:
                lines = response.iter_lines()
                print(response.status_code, next(lines), next(lines))
                p.terminate()
                try:
                    print('exit with stream open:', p.wait(timeout=3.5))
                except subprocess.TimeoutExpired:
                    print('timed out after 3.5 seconds')
            print('exit after stream closed:', p.wait(timeout=3))
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
PY
```

#### I2. 目录刷新丢失下载目标时，活动任务继续锁住弹窗，但取消按钮消失

- **定位：** `apps/desktop/src/renderer/domains/kernels/components/KernelManagerDialog.tsx:88`、`:110`、`:224`；`apps/desktop/src/renderer/domains/kernels/components/KernelReleaseList.tsx:37`、`:72`。
- **触发：** 开始下载尚未安装的版本→下载中点击“刷新版本列表”→provider 返回 `catalogError` 且仅含本机安装项，或者目录不再包含该版本。刷新按钮在 active operation 时仍可用。后端这种降级是正常契约，不一定是 HTTP 错误，`useCheckKernelUpdate` 会直接替换 catalog。
- **原因：** 卡片集合只来自 catalog/installed。任务进度与取消按钮只能作为匹配 release 卡片的子节点渲染，而 `busy` 独立根据完整 operations 计算。staging 中的版本尚不属于 installed；丢失卡片后全部筛选也找不回它，弹窗仍禁止关闭。
- **影响：** 用户失去已承诺的取消能力，被迫等待下载自行完成/失败，或退出整个应用。未安装空库时能直接呈现“没有符合筛选条件的内核版本”并同时禁止关闭。目录恢复后可能恢复操作，故不是声称永远无法恢复。
- **本轮验证：** 直接加载并内存转译当前 TSX，用 `react-dom/server` 渲染 `KernelReleaseList({releases: [], operations: [downloading], busy: true, ...})`，得到只有空列表 `<p>`、`hasCancel:false`。完整“下载→刷新”未重跑真实网络/Electron；路径由上述组件状态与后端降级契约确认。
- **建议修复：** 为活动任务提供独立且不受目录/筛选影响的状态与取消区，或至少把 operation-only 项合入列表；复用现有 `KernelOperationStatus`，不要另建任务系统。补集成用例：下载中刷新得到 empty/local-only catalog→仍显示活动状态并可取消→终态后允许关闭，同时检查筛选不会藏起唯一取消入口。
- **置信度：高。**

### Minor

#### M1. 复制名称冲突显示为全局错误，未关联名称字段

- **定位：** `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.tsx:55`；后端 `apps/backend/src/autoflow/adapters/http/errors.py:164`。
- **问题：** `PROFILE_NAME_CONFLICT` 当前返回空 `details`，前端只在 `error.fields.name` 存在时调用 `setNameError`，所以真实名称冲突进入 `operationError`。输入仍保留且能重试，但不会得到 `FormField` 的 `aria-invalid`/错误关联，不符合交互基准“冲突时在字段下方显示错误”。已有冲突测试仅检查任意 alert，未检查字段关联。
- **修复：** 在共享后端冲突映射返回 `details.fields.name`，或按稳定错误码映射到名称字段；补关联断言。前者也改善新建/编辑冲突定位。
- **置信度：高。**

#### M2. 断线文案把可能已提交的操作说成“尚未执行”

- **定位：** `apps/desktop/src/renderer/domains/profiles/components/ProfileActionDialog.tsx:66`。
- **问题：** `disabled` 只表示本地服务当前离线，不能证明之前提交的复制/删除尚未落库。服务在提交后、响应送达前断开时，弹窗仍可能保留并显示“当前操作尚未执行”。与批准计划“恢复后提示核对，不假定上一请求失败”不一致。
- **影响与修复：** 当前没有自动重放，风险受限；仍应改成“操作结果可能未确认，恢复连接后请核对列表再重试”等中性提示，未发送场景也不应使用全局连接状态推断服务端结果。补已提交但响应丢失的文案/手动重试用例即可。
- **置信度：高（基于控制流，未单独注入网络断开）。**

#### M3. worker smoke 的文档多声称验证了进度消息

- **定位：** `docs/migration/browser-management-validation.md:17`；`scripts/smoke-browser-management.mjs:91`。
- **问题：** Task12 独立审查提出、此次已核对：脚本取 `messages.at(-1)`，断言 completed、resolvedVersion 和 executableRelativePath，没有断言前面的 progress 消息。因此删除进度消息也不会让这项 smoke 失败，文档“验证进度消息和完成结果”超出该命令的实际断言。
- **修复：** 最小做法是将验收措辞改为验证 worker 动态入口及完成结果；或者为现有 smoke 增加所需进度序列断言。它不否定另外的 worker 状态单元/集成测试。
- **置信度：高。**

## 测试证据判断与未核实范围

- 既有最终报告记录 backend `311 passed`、frontend `259 tests / 45 files`、scripts `9 passed`，以及 ruff/mypy/typecheck/lint/OpenAPI/build、源码/frozen/开发 Electron/packaged Electron smoke。此次未无理由重复这些全量命令；将其视为实现任务已有证据，而非宣称由本审查者再次执行。
- 已读取 `docs/migration/browser-management-evidence/validation-evidence.json` 与 `cancellation-evidence.json`：公开版 `145.0.7632.109.2` completed；`142.0.7444.175` cancelled，记录有 1 worker、worker 已退出、staging 已清理、health=ok。未重新下载，不把元数据等同授权版下载成功。
- 本轮新增验证只有 I1 的真实源码 sidecar/SSE/SIGTERM 复现、已安装 Uvicorn shutdown 源码核对、I2 的当前 TSX 静态渲染。没有启动用户任务窗口，没有修改产品代码、索引或 HEAD；唯一持久审查产物为本报告。
- 现有取消与 manager shutdown 测试直接调用 manager；它们并不覆盖 Uvicorn 持有 SSE 时是否能进入 shutdown，这正是 I1 漏过逐任务验证的原因。已有空目录与下载 UI 测试没有组合“活动下载后目录替换”，故不能排除 I2。
- Task12 六文件独立审查已 PASS，见 `task-12-review.md`；本报告接纳其中的文档准确性问题为 M3，没有重复承担其完整打包/CI 审查席位。该报告提到的 2 条既有 pytest 上游弃用、第三方 zod build 提示已经如实披露，非本分支新增产品缺陷，不增加一条阻塞或重复问题，留待后续依赖维护。其确认 shutdown handler 存在并不等同于持有 SSE 时能实际进入 handler，故不推翻 I1。
- Windows x64、macOS Intel 新 CI 结果尚无；本机仅 macOS arm64。真实商业 License 校验、下载、安装未核实。没有发布签名/安装器验收。

## 交付建议

由一名实现者在现有架构内修复 I1/I2，顺带处理 M1/M2/M3，再做针对性回归和最终复审。I1 应以真实进程退出证明，不能只加一个 fake shutdown 测试；I2 应验证操作目录消失后仍能取消。随后按改动范围补 lint/typecheck/相关测试，只有打包入口变化才重跑相应 frozen/desktop smoke。

**可以合并吗：修完再合。** 主体规格、架构和本机证据具备交付基础，但正常退出清理及下载取消可达性属于生产集成必需行为，当前两处缺口不能用已有全绿套件替代验证。
