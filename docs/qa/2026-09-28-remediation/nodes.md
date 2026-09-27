# 节点与数据约束修复验收

日期：2026-09-28。状态：confirmed（下列限定检查）；完整系统验收仍在进行。历史审计与原始结果不改写。

| 编号 | 根因与最终行为 | 改动位置 | 修复前证据 | 修复后证据 |
|---|---|---|---|---|
| N-01 | CSV 去表头错误地要求至少两行；现在 hasHeader=true 时即使仅一行也返回零记录，false 保留原行 | string_convert.py / CsvParseExecutor | nodes-before.log 中表头用例失败 | nodes-after.log；nodes-native/results.json 的真实生产 worker CSV 场景 |
| N-02 | str.split 破坏引号、空参数与空格路径；保留字符串契约，Unix 使用 shlex，Windows 使用 CommandLineToArgvW，始终无 shell | python_script.py、workflow_subprocess.py、PythonEditorDialog.tsx | nodes-before.log 中真实脚本读取失败 | nodes-after.log；nodes-native 中真实文件路径与生产 worker；nodes-review-after.log 的无效输入拒绝 |
| N-03 | 未知 SHA 通过 getattr 默认降为 SHA256；现在只接受明确的固定长度 SHA 家族，未知算法明确失败且保留旧输出 | utility_tools.py / SHAEncryptExecutor | nodes-before.log 中四种未知/非 SHA 算法失败断言未满足 | nodes-after.log 独立 hashlib 对仓库源码摘要；nodes-native 中失败后不执行后继节点 |
| DB-01 | ORM 游标唯一性滞后于已执行的 pm10_shared_sheet_cursors 迁移；模型改为 task_id + record_ref | project_run_models.py / ProjectTaskRecordCursorRow | cursor-before.log：真实迁移 SQLite 与声明约束不一致 | cursor-after.log/xml：14 项迁移、代次隔离、共享 Sheets 游标相关检查通过 |

节点初始红测 6 失败 / 6 通过；修复后关联回归 55 通过，其中包含数据库约束测试。独立数据库组合为 14 通过，不能与前一组直接累加为去重计数。后续审查发现 Windows NUL 截断边界，新增平台解析前拒绝；argv-nul-before.log 保留红测，nodes-review-after.log 为修复后 15 通过，覆盖脚本未执行和旧输出未变。Windows 允许末尾未闭合双引号，测试保留其原生语义；POSIX 明确失败。

真实 worker 验收使用生产 WorkflowRuntime、真实子进程、实际 package.json 副本及审计真实 CSV 导出表头；3 场景通过，无外部成功替身。real_nodes.py 复用历史 harness 但指定新的独占输出目录，退出清理自身临时文件。nodes-native/results.json 记录当时 HEAD 2497896b 与未提交修复运行事实；随后共享安全提交 59ed54b9 未改动这些节点文件。新增 NUL 拒绝之后未重复三个无关正向场景，已有完整参数回归覆盖。

兼容性：普通空白分隔参数不变；有引号的参数现在按平台命令行规则解释；不执行 shell 表达式。以前依赖未知 SHA 隐式 SHA256 的流程现在明确失败，需要选择真实算法。冻结来源差分只对已证实的未知 SHA 错误行为显式分叉，仍断言旧源原行为与新实现完整失败结果，其余差分不变。

数据库只修改声明，不改迁移历史，不触碰真实用户数据库，无数据升级或回滚操作。真实迁移库已采用正确约束；通过旧模型 create_all 生成的非迁移库不在自动支持路径，应保留副本并先诊断其迁移历史。该修复不代表全库 Alembic metadata check 的其他漂移已关闭。

质量检查：从 apps/backend 运行 Ruff 与既有 mypy 配置，记录 nodes-ruff.log、nodes-mypy.log；前端 tsc 与定向 ESLint 记录 nodes-typecheck.log、nodes-eslint.log。Windows 原生参数、Windows 8.3、打包 Python 路径仍缺实机验收。对应提交以本文件首次引入提交为准，可用 git log --follow 检索。

独立复审确认 CSV、SHA 和游标修复方向；发现的 NUL 问题已修正并保留红绿证据。Windows API 内存由 LocalFree 释放，使用原生参数语义，参考 [CommandLineToArgvW 官方契约](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-commandlinetoargvw)。
