# M5 调试运行

日期：2026-09-13；状态：confirmed；来源：用户批准完整M5计划。

沿用M4调度器，节点前调试闸门、有限worker命令与稳定ID；正常暂停允许原子修改流程变量，循环局部只读。顶层直跑需手动准备上下文，嵌套运行至此保留真实前置。失败暂停保留浏览器供检查，停止清理后仍failed。普通运行不变。诊断沿用事件/文件/产物索引，不建第二执行系统。详细行为见正式M5规格；实施状态见计划和后续验收。

实现位置：domain/workflows/debug.py负责起跑编译与纯校验，application/workflows/debug.py负责边界许可和变量诊断；有限传输留在process/provider。命令记录及purpose沿原数据库索引。主进程新增固定导出IPC与原生流式写盘，不接入网页动作。

验证来源：源码/冻结8组真实浏览器、正式Studio4组UI以及M1–M4回归，详见docs/migration/automation-studio-m5-validation.md。普通运行不承担完整诊断成本；暂停不冻结网页，强制崩溃不重建现场。
