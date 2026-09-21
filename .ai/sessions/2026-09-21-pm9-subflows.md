# PM9 S1 冻结项目子流程

日期：2026-09-21。状态：confirmed（源实现与定向验证）；三平台新候选待验证。
来源：用户继续实现、S1–S5 approved 规格、当前独立工作区测试。

复用既有 canvas gateway；抽取其纯画布依赖选择供 prepare/Studio/project worker 共用。项目子流程显式 inputs/outputs，深复制输入，仅成功声明输出写回。声明定义不作为根节点执行。父端验证冻结依赖调用路径和父 visit 存活，继承原 Task/Run/代次及权限。子 End、跨子图边和未隔离并行图继续拒绝。

RED：双调用失败；缺失调用路径、错误定义、已结束父调用曾被接受。GREEN：100 项目标回归、175 项 Runtime/Studio worker/差分/HTTP 契约通过；真实 HTTP/worker/browser 覆盖两 Task 冻结双调用及父 Run 撤销后的迟到写拒绝，已提交记录保留。ruff/mypy（398 源文件）通过。覆盖台账 251 引用校验通过；205 有断言/46 未定位，状态不批量升级。

S2 声明人工输入/继续位置、S3 分支隔离、S4 Windows 边界、S5 多 Run 未完成。旧 4f392ed5 CI 继续独立收集；不得当作本次代码验证。releaseAccepted=false。只提交现有 PM9 分支，未改主工作区，未合并发布。
