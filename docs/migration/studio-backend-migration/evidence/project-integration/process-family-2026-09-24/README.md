# 项目任务命令与 Python（2026-09-24）

- 复用冻结 WebRPA@5ccb900e 的 `RunCommandExecutor` 和 `PythonScriptExecutor`；项目目录 178→180，213 范围和14通知排除不变。项目接入还有33个入口（含画布工具），不按数量推断整体完成。
- AutoFlow 必要适配：项目登记命令实际变量及 Python stdout、stderr、退出码、return 对象；冻结后端增加 `--python-script` 入口，用 `runpy` 执行脚本并保留参数、本地导入、退出码。用户显式指定解释器的路径保持原规则。UI 不再误称运行环境为 WebRPA/Python 3.13，实际使用 AutoFlow 随包 Python。
- 冻结缺陷先复现：上一包直接以脚本作为后端参数返回 exit 2（unrecognized arguments）。入口及命令构造新增两项回归先失败，修复后与原版单测/差分共29项通过（4.19秒）；首轮冻结包已通过内置脚本真实执行，新增标准输入及令牌隔离后的最终包也已通过。
- 真实 worker 的命令/Python停止和超时四项最初均超过15秒：只杀父进程，子进程持有输出管道。修复沿 `ExecutionContext.process_cleanup` 注入已有进程身份校验，POSIX只杀身份确认的子树PID、不杀所在worker组；Windows复用现有树清理。普通Studio、项目、子流程和自定义模块均传递同一清理入口。四项后续通过（13.74秒）。不把POSIX测试算作Windows实机结果。
- Python 70,000汉字单行输出用例先得到空串，暴露StreamReader行限制和吞掉采集异常。改为分段读完一行后解码，保留原版空行过滤/换行规则，采集错误不伪报成功。追加标准输入和令牌隔离后，项目真实worker全族11项通过（32.05秒）：成功、非零退出/脚本错误、大输出、停止/超时及子进程消失；无Profile或浏览器依赖。嵌套工作流、画布子流程及自定义模块关联7项通过（14.81秒）。
- [开发版正式窗口](../formal-project-process-electron-EDlSvR/result.json)使用真实UI从项目进入Studio，编辑命令、Monaco代码及四类输出字段、保存和正常关窗，创建项目自动化并启动。命令中文结果传入Python，stdout/stderr/退出码及返回对象持久化，在任务输入输出页可见。没有直接写Store，API只准备夹具和读取证据。
- 前端配置分支52项通过（5.90秒）；受影响Ruff、11个生产文件mypy、TypeScript、ESLint、OpenAPI及renderer/main/preload构建通过。正式目录包已验证。
- AI字段提示和前端表单统一说明 AutoFlow 随包 Python，生成器显式记录来源差异；213节点元数据与来源摘要6项通过，不修改冻结源码。其他平台、用户数据库未实测。

- 工作流子进程复用 worker stdin 导致脚本读取阻塞；真实用例先失败，再统一设为 DEVNULL。普通和项目 worker 在现有启动边界移除宿主/HTTP鉴权令牌，保留普通环境变量；仅使用合成令牌验证，无真实秘密输出。这是宿主权限边界适配，不宣称脚本具备沙箱隔离。70项进程、入口和原版差分关联回归通过（7.32秒）。
- 扩大回归发现旧测试将已经完成的 list_export 当作不可运行节点：现单列其合法配置成功断言，保留未知类型和画布分组拒绝断言；对应领域回归60项通过（0.98秒），未删除失败要求。

- [最终 macOS arm64 目录包](../formal-project-process-electron-bEJxFs/result.json)通过同一真实UI链路；内置 Python 的 stdin 返回空串，宿主令牌键不存在，结果、stderr、退出码和对象持久化正确。截图已人工复核。冻结后端164.3秒；包未签名。最早 xG7yb1/VY8pTn 为新增隔离修复前的证据，不代替最终 EDlSvR/bEJxFs 结果。
- 最终包 SHA-256：backend `6ce232e2541819d740db44ea3249c2365f64e3c06be311f31befdd3fcbce0266`；app.asar `b4aa3dcf370500ffc1feea87bf147045efdffa9efddaf3aae1bffd8849b065a0`。没有执行用户脚本或修改用户数据库。
