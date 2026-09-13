# 安卓设备管理与 M4 接入验收

日期：2026-09-13。状态：confirmed / passed（本期 Mac 范围）；来源：正式源代码、自动化测试、真实 Mac Lima/Docker/Android 与打包应用。

## 交付范围

- 按已选资源看板/创建页原型实现正式 React 组件：状态分组、搜索/筛选、列表切换、创建表单、配置复制、重命名、启停/重启、删除范围选择、实例详情及设备运行记录。
- 复用当前已准备的 Lima 环境和缓存 Android13 ARM64 镜像。默认1CPU/1536MiB/720×1280；实际设备/截图/操作状态来自鉴权 API。原生窗口继续使用原有 scrcpy 3.3.4。
- 管理操作先持久化、后执行；失败/中断保持待核实，跨工作区共用 VM 独占锁；写命令完成标记支持未知结果核实。恢复容器前先持久化目标名称，避免丢失创建响应后找不到已创建对象。
- 删除支持保留独立数据并恢复容器，或删除容器和数据。完整删除保留不在列表显示的请求回执记录；编号不复用。操作请求单设备上限1000，超出明确拒绝，不悄悄删除去重记录。
- 安卓工作流使用 M4 共享调度：通用条件/循环/变量、每轮独立执行和截图、独立人工 handoff。拒绝网页条件及浏览器/安卓混合图。M3、两个0007、已合并数据库经0008显式汇合，旧版本不重写。

## 验证证据

- [真实冻结后端闭环](android-management-qa/frozen/result.json)：两设备创建/启动、创建重试、停止/重启、数据保留删除与恢复、逐轮截图/人工处理、占用时拒绝停止，以及实际容器/卷清理。
- [循环记录](android-management-qa/frozen/loop-run.json)、[真实设备截图](android-management-qa/frozen/preview.png)。
- Python 全量 **586 passed**（84.09秒，2条既有弃用警告）；前端全量 **428 passed / 67 files**（2个worker）。最终布局调整后补跑创建表单3项、TypeScript和ESLint均通过。
- Ruff、mypy（176个源文件）、OpenAPI生成一致性、脚本12项与目录结构3项检查通过；React/Electron构建、PyInstaller冻结后端和Mac ARM64打包通过。
- `node scripts/smoke-workflow-control.mjs` 的7组真实浏览器M4回归通过：本轮执行的是源后端回归，不重复声称已验收所有浏览器打包界面。
- 打包Mac应用实测：创建停止状态实例、展开高级配置、原生操作窗口打开/关闭、结束人工会话释放占用、详情三标签及该设备实际运行日志。UI测试实例的容器和卷已清理，原设备空闲且数据保留：[清理证据](android-management-qa/ui/cleanup.json)。
- [看板对照](android-management-qa/ui/board-comparison.jpg)、[创建页对照](android-management-qa/ui/create-comparison.jpg)、[详情页](android-management-qa/ui/detail.png)、[真实原生窗口](android-management-qa/ui/native.png)；视觉核对结论见根目录 `design-qa.md`。

## 实测发现与修复

1. 原 VM 约7921MiB，原有安卓容器内存配额合计7680MiB。新增启动受到512MiB宿主预留预算拦截，失败保留可核实状态。两实例测试临时停止旧 Demo `afd-5a7beadf6de2468d`，结束后恢复启动；未删除或修改其数据。
2. 删除已完成时，测试脚本“列表后再按ID读取”可能得到正常404；改为列表轮询并最终核验Docker容器/卷均不存在。不将已删除对象的404当作资源泄漏。
3. 首次前端全量测试并行于打包时，Studio已有5秒用例超时；单独重跑通过，降低为2个测试worker后全量428项通过。
4. 创建页初次视觉检查发现资源输入使“数据与启动”落在首屏以下；按原型折叠为“更多设置”，保留配置摘要与输入能力；再次修正分组间距，最终首屏开关完整显示在按钮栏上方。

## 使用

在本机已准备环境中运行 `scripts/open-android-demo.command`。进入“安卓模拟器”，点击创建实例；按卡片观察 Android 就绪。手动操作使用“打开操作窗口”，完成后“结束操作”；工作流从独立 Studio 选择设备。

截图为每10秒刷新的只读单帧，不接收网页触控。服务端同设备最多1帧/秒、最多两个预览请求并发。停止设备保留数据；保留数据删除后的登记项提供“恢复实例”。复制配置只创建空白独立数据。

本期一次创建一台，设备管理和安卓控制串行；不含并行任务队列、临时实例回收、应用管理、元素选择器、摄像头或环境伪装。Root 均显示当前实例未验证。Windows/macOS Intel未实机验收；应用是未签名/未公证的本地测试包。

## 复验命令

从仓库根目录执行：

```sh
apps/backend/.venv/bin/python -m pytest apps/backend/tests
npm --workspace @autoflow/desktop test -- --maxWorkers=2
npm run typecheck
npm run lint
npm run openapi:check
npm run test:scripts
npm run test:structure
npm run build
npm run backend:build
npm run package:dir
```

设备实测脚本只清理自己创建的设备；默认不停止现有设备。VM内存不足时先主动安排容量，不自动挑选用户设备停止。

```sh
apps/backend/.venv/bin/python scripts/smoke-android-management.py \
  --executable apps/backend/dist/autoflow-backend/autoflow-backend \
  --workspace .local/android-management-smoke \
  --output docs/migration/android-management-qa/frozen
```

本轮额外显式传入 `--pause-reference-container afd-5a7beadf6de2468d` 腾出测试容量；脚本在finally中恢复这台既有Demo。本地验证证据中的时间、截图和设备ID均来自该次实测。

## 交付与主线状态

已验收的源码在 `codex/android-workflow-handoff` 分支、工作树 `/Users/zhangtiancheng/Documents/projects/autoflow-android-handoff`。当前Mac应用和 `scripts/open-android-demo.command` 位于该工作树。该分支已汇合提交 `2b5365e` 的M4；主工作区随后出现未提交M5调试改动，与本次代码重叠，所以未强行合入或改动主工作区。M5提交后应显式集成并复验，尤其是运行调度、调试状态和数据库迁移。
