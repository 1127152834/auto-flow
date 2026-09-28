# Task 4：已确认归属的退出进程清理

日期：2026-09-28

状态：completed

基线：`d1c18362bf77ffab362e399136973952d363e2a6`

提交：本报告与业务修复、测试和证据位于同一个Task 4提交；同一提交无法在自身内容中嵌入自己的SHA，权威SHA由`git show --format=%H --no-patch`及最终交付消息给出。提交消息为`fix(process): retain confirmed cleanup ownership after exit`。

## 根因与调用方

共享POSIX helper `project_browser_processes.capture_processes`先通过内核birth识别本次worker和上一轮已捕获PID，但随后候选扫描仍对这些已确认owned PID调用`_belongs_to_run`，重复读取原生可执行文件、argv和环境。真实SIGKILL后的macOS进程短暂处于Z状态：`kill(0)`仍判存在，birth仍匹配，但原生参数已经不可读。严格归属模式因此把已经确认归属的PID误报为未知候选并抛出`Candidate browser process ownership is unavailable`。

直接生产调用方是`ProjectWorkflowWorkerManager._cleanup_owned`经`force_process_tree`的两次捕获；重启恢复`recover_worker_directories`也复用同一helper和previous捕获。测试浏览器worker、普通workflow subprocess及worker父进程退出路径使用各自helper或同一发信号规则，未增加调用方补丁。

## 修改

- 候选扫描遇到已经由匹配birth进入`owned`的worker或previous PID时跳过冗余原生参数判断。新发现候选仍要求原生归属证据；birth不匹配的worker/previous仍进入判断，未知活候选在`strict_ownership=True`下继续失败关闭。
- 结果收集和`signal_processes`保持原有birth复验，未放宽PID复用边界、`strict_ownership`、异常传播或任何超时。
- 新回归固定匹配worker birth、匹配previous birth、root/previous PID复用以及未知活候选边界。旧实现下首项红灯；修复后进程归属/取消单元回归14项通过。
- `process-exit-fault-probe.py --expect-cleanup`采用主控已授权的`ownedCount == 1`断言。探针仍在真实birth读取后对自己的child发送SIGKILL，并由真实`wait`回收；没有伪造系统返回。
- sidecar shutdown测试在READY为空、前缀错误、JSON非法或port非法时抛出AssertionError，并附最多4096字节stderr尾部和最多256字符READY行；原启动与清理断言全部保留。

## Red / Green与真实证据

Red命令（独立`--basetemp`）在旧实现退出1：

`/Users/zhangtiancheng/Documents/projects/autoflow/apps/backend`

`.venv/bin/pytest tests/unit/test_browser_processes.py::test_confirmed_worker_and_previous_birth_do_not_need_native_arguments -q --basetemp=/tmp/autoflow-task4-red`

失败栈进入`capture_processes -> _belongs_to_run -> _native_arguments`，测试明确报错`confirmed ownership must not reread native arguments`。

真实Green探针退出0，系统事实为：state=`Z`、`kill(0)`存在、birth匹配、native arguments不可读、capture返回`ownedCount=1`、真实wait回收、return code=`-9`。完整逐字输出见`docs/qa/2026-09-28-remediation/process-exit-identity-fault-after-task4.log`；所有验证的精确cwd、argv、环境覆盖、exit code和输出见`process-cleanup-task4-validation.log`。

## 验证结果

- `tests/unit/test_browser_processes.py`：14 passed。
- credential/timing/webhook/interactive四个相关文件：31 passed。
- `tests/integration/test_workflow_recovery.py`：9 passed。
- `tests/integration/test_sidecar_shutdown.py`：5 passed。
- 真实SIGKILL探针：exit 0，ownedCount 1，child return code -9。
- Ruff changed-file check：通过。
- mypy changed-file check：通过。
- `git diff --check`：通过。

按任务边界未运行约18分钟的默认后端全量；主控在全部业务源码稳定后负责最终全仓回归。`ruff format --check`会要求重排三个长期未由formatter统一的完整文件，因此未将大范围格式改写混入本修复；Ruff规则检查和mypy均通过。

## 限制与未归因事项

本修复只覆盖POSIX共享捕获helper。Windows保留原生进程句柄、Job与taskkill路径，没有修改，也没有本轮实机证据。

原默认全量中的凭据空值、非法概率、webhook超时三项没有候选PID和启动身份证据；本轮31项通过不能反向证明三项全部由本缺陷造成。早期四项sidecar READY失败同样未确认根因，本轮只让未来启动失败保留有界stderr诊断。

没有修改超时、吞掉清理异常、关闭strict ownership、改变End业务语义、接管AOCI初始化或触碰其他任务WIP。
