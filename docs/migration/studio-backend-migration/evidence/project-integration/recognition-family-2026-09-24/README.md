# 项目识别节点接入（2026-09-24，正式项目UI待验收）

能力：`node:ocr_captcha`、`node:slider_captcha`、`node:face_recognition`、`node:image_ocr`。

分类为 AutoFlow 必要适配：复用已迁入的原版执行器，不增加识别算法。项目目录注册四节点；节点启动时复用现有文件适配器；项目输出取执行器实际变量，保留默认变量名、显式空名禁用、验证码变量名优先级及空白处理、敏感变量不发布。人脸未检出仍是成功的 false 分支，不改成执行失败。

EasyOCR 两个模型从冻结源码原样迁入 `apps/backend/src/autoflow/resources/easyocr`，SHA-256/来源见该目录 SOURCE.md。源码运行与 PyInstaller 都使用同一拥有的资源；删除运行时向上寻找 reference 的回退。保留显式模型环境配置和禁止自动下载的规则。源码使用授权沿用户确认记录，不扩展为商业或公开发布许可。

## 证据与边界

| 文件 | 实际结果 |
| --- | --- |
| resources-red.log | 资源边界两个回归先失败，证明旧代码读取 reference |
| registration-red.log | 项目注册回归先失败，四种节点均缺失 |
| source.log | 原版差分及节点单元 23 项通过，1.88 秒 |
| real-worker.log | 真实项目文档、SQLite、调度器、子进程、FaceRecognition/EasyOCR 模型：匹配、无脸分支、缺文件、停止共 4 项通过，18.44 秒 |
| real-cloakbrowser.log | 真实主应用 Profile 参数、项目 API/SQLite/worker/CloakBrowser：验证码识别/输入/提交及滑块、缺元素失败、等待中停止共 3 项通过，37.68 秒；正常场景两任务分别验证页面实际值及位移；全部场景验证环境副本清理、worker 空闲、资源阻塞清空 |
| regression.log | 共享项目图/数据、识别单元及源码差分 131 项通过，3.98 秒；含 14 项默认名/显式空值/别名/敏感输出检查 |
| admission.log | 项目准入、运行校验、目录合同 77 项通过，3.73 秒 |
| ruff.log / mypy.log | 受影响文件 lint、4 个生产文件类型检查通过 |
| openapi.log / structure.log | OpenAPI 一致性及目录检查通过，无新接口或迁移 |

各批次存在重叠，不相加为唯一用例数量。真实网页使用本地自建测试图（1234）、输入框和位移计数器，未访问第三方验证码服务。HTTP 浏览器测试使用 ASGI 路由，不宣称为 TCP/SSE 或正式 Electron UI 证据。首次运行因环境变量名称错误跳过，改用既有 fixture 的 `AUTOFLOW_TEST_CLOAKBROWSER` 后取得上列实测结果；跳过不计通过。

## 可复现命令

从仓库根目录运行：

```sh
apps/backend/.venv/bin/python -m pytest apps/backend/tests/integration/test_project_recognition_worker.py -q
# 指向已有 CloakBrowser 可执行文件，测试会复制到独立临时工作区
AUTOFLOW_TEST_CLOAKBROWSER=/path/to/Chromium apps/backend/.venv/bin/python -m pytest apps/backend/tests/integration/test_project_batch_real_cloakbrowser.py -k captcha -q
```

两组测试支持 `AUTOFLOW_TEST_PROJECT_WORKER=/path/to/autoflow-backend`，用于真实冻结 worker 验证。没有修改用户数据库或运行中的主应用。

## 保留门槛

项目目录由 184 增至 188/213；25 个入口尚未注册，不等于整体剩余只有25项。交互两节点及本批四节点正式项目 UI 尚未核销，因此上一检查点的31项项目接入门槛仍不能关闭。图像OCR屏幕区域、原生权限、正式开发/打包UI及 Windows/macOS Intel 继续单列。Mac 锁定是原生UI阻塞，不是服务端测试通过的替代证据；不使用 BrowserWindow.destroy() 绕过正常关窗。

## 冻结与目录包验证

- PyInstaller 构建 153.48 秒完成，unsigned macOS arm64 目录包生成；前端源码本批未变，沿用 `14ac58e3` 已核验 renderer/main/preload 构建，不重复构建前端。
- `frozen-code.log`、`packaged-code.log`：5 个完整生产模块的字节码、常量、名称与源码一致；两份模型在冻结目录及包内的 SHA-256 与拥有资源一致。可执行文件摘要见 build-artifacts.json。
- `frozen-worker-red.log`：首次冻结模型用例 101.61 秒超时，保留原失败。SQLite 当时已完成真实人脸匹配，正在OCR；没有删用例、延长100秒测试等待或60秒节点超时。
- `frozen-import-sample.txt`：复现时仅采样本任务worker，观察到原生扩展动态导入占用GIL；该轮在40.33秒通过（frozen-repro.log）。这不足以断言首次超时唯一根因，首次运行与目录包装并行是待排除影响之一。
- `frozen-worker-final.log`：同代码同断言全四场景 19.96 秒通过。首次超时仍作为稳定性观察项保留；不能仅凭复跑就称已根治。
- `packaged-captcha.log`：直接使用正式包内后端，真实项目/CloakBrowser三场景全部通过，47.35秒。这是包内worker证据，不是启动正式Electron后的UI验收。
- 后续共享构建与真实模型/浏览器验证串行安排，避免重负载争用干扰结果。正式UI解锁后仍须跑原生及项目闭环，不用本页证据代替。

## 取消／超时终态收口（2026-09-24，后续真实回归）

新增 `ocr_stop` 在OCR节点开始后等待0.2秒再停止，新增 `ocr_timeout` 使用0.5秒节点预算；两项均使用真实项目worker和原识别器。`ocr-stop-red.log`、`ocr-timeout-red.log`分别证明旧终态从期望cancelled/failed变成interrupted。

明确根因：取消 `asyncio.to_thread` 不能终止底层计算线程。worker已完成调度和浏览器/provider清理并发送 `finished(cleanupConfirmed=true)`，但 `asyncio.run` 等待线程池退出；父进程额外等待自然退出超时，丢掉已确认的业务终态。

修复位于现有项目进程边界：对已确认的非成功终态立即清理受管进程树，再返回原失败/取消结果。POSIX沿既有出生身份/目录/可执行文件核验直接SIGKILL，Windows继续使用原进程句柄与Job清理；不向未经核验PID发信号。正常成功仍校验自然退出码。没收到终态确认、清理失败或归属不明继续保留待核验及占用，不据HTTP接受就报告已停止。

- `ocr-stop-green.log`：新增真实OCR取消通过，4.60秒含启动/人脸步骤；停止至清理断言仍严格小于3秒。
- `cancel-regression.log`：取消修复后的共享进程/调度/真实数据节点98项通过，152.44秒，早于最终超时失败分支扩展。
- `terminal-green.log`：最终六场景全部通过，24.47秒；验证超时节点错误码WORKFLOW_NODE_TIMEOUT、停止不再执行后继、两种分支及空资源占用。
- `terminal-regression.log`：最终34项相关失败、停止、取消、超时、未知归属、清理回归通过，26.48秒。新进程测试启动忽略SIGTERM的实际子进程，验证确认取消时小于1秒清理，仅POSIX实测，Windows未冒称通过。
- `terminal-ruff.log`、`terminal-mypy.log`：受影响文件检查通过。

该根因证明并修复了**已确认终态后的退出误判**；不能据此宣称上一批首次冻结OCR的100秒超时已完全解释。原生扩展导入占用GIL/冷启动性能仍保留观察，正式项目UI依然受Mac锁定影响。

最终冻结构建156.10秒、unsigned arm64目录包完成。`terminal-frozen-code.log`/`terminal-packaged-code.log`核对7个完整模块（新增父进程管理与清理helper）和两个模型一致；`terminal-build-artifacts.json`保留本次摘要，旧构建摘要不覆盖。`terminal-packaged-worker.log`使用正式包内worker通过六个真实识别场景，33.43秒，含OCR动作中停止与节点超时后的正确终态/清理。本测试父进程由当前源码运行；冻结父进程代码已核对，不宣称等价于完整正式Electron/冻结sidecar入口验收。
