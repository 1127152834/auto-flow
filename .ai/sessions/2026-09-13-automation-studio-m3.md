# M3 元素拾取与定位测试交付

日期：2026-09-13；状态：implemented；来源：用户批准 M3 计划、实际代码、受控网页与 Electron 验收。

新增专用可见临时会话和原五类元素节点 framePath。共享定位入口支持主页面、嵌套/跨域 iframe、开放 Shadow DOM。拾取预览后原子应用、真实匹配测试、过期请求保护、与运行互斥及原离开协议。公共接口/OpenAPI已更新，无数据库迁移、无新运行时依赖。运行和拾取复用 Profile/内核检查及进程清理。

后端最终全量529、前端412测试通过。Ruff/mypy/TS/ESLint/OpenAPI/结构/脚本/构建通过。真实浏览器8组、源码与冻结worker各5组、开发/构建HTML/目录包Studio各4组，M1实际回归13组、M2实际回归8组。详情与未实测项以 docs/migration/automation-studio-m3-validation.md 为准；Windows无实机验收，不声称跨平台全通过。

新增“应用前再次核实目标”防止页面变化后旧结果写入；启动响应未知保留原sessionId并阻止离开。原研究里程碑标历史superseded，复杂控制流/录制/Debug未交付。用户模型/Redroid研究及并发改动未纳入提交。

启动即关闭的真实验收发现 Python 3.11 wait_for 的完成/取消竞态；通过任务栈及4个修复前失败的确定性用例定位，运行/拾取通道改用 asyncio.timeout。原生进程识别补齐 inspection worker，无法确认退出时有界失败并保留重试责任；源码与冻结入口连续5次启动即关闭通过。
