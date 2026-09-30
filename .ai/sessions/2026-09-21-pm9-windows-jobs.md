# PM9 Windows worker Job ownership

日期：2026-09-21。状态：proposed（实现已完成；Windows 原生 CI 待运行）。来源：S4 规格、原生实验 35574503412、当前实现及定向测试。

- 复用 bootstrap kill-on-close Job，增加每个 Run/generation 的随机命名身份；ready 时用进程 birth 与 Job membership 同时核验，持有该 Job 句柄直到整棵树清理成功。取消恰逢句柄登记时仍等待登记并负责关闭。
- 将 Run/generation/name/pid/birth 写入私有运行目录，重启只按该证明打开 Job；核验同一进程句柄后终止同一 Job 句柄。缺证明、错 birth、外部 Job、权限拒绝均保留目录及 blocker。
- 新增 Windows 实际进程/后代测试：存活恢复、root 退出、错 birth、外部 Job、终止拒绝。未经过 runner 之前不算原生通过。
- 本机：30 passed、5 Windows-only skipped；ruff 通过；mypy 401 文件通过。Windows 任意既有文件原子替换仍受限，未删除 501；releaseAccepted=false。

后续原生运行 35576938888 未通过：Job membership/birth 复合检查拒绝有效 worker，未释放保护。已拆开错误原因用于原生定位；不能把本机跳过当作通过。

同片新增新文件输出子集：逐层目录句柄拒绝写/删除共享、拒绝重解析点与歧义 Windows 名称；同卷暂存句柄原子发布且不覆盖，登记失败通过同一文件句柄删除。沿用既有快照/哈希/登记；现有文件覆盖/追加和安全读取未开放。新增原生冲突、取消、登记失败、junction、目录改名、路径拒绝测试，仍待 Windows runner。此子集不是 S4 完成。

第二轮原生运行 35577374427：68 passed、27 skipped，14 failed 均为 Job 非成员。已定位 Python venv launcher 与实际 interpreter PID 不同：ready 时仅允许监督者将直接拥有且 birth 一致的 launcher 纳入 worker 随机命名 Job；恢复路径绝不扩展成员。新文件全部原生断言通过；新增实际 --workflow-worker 的 Base64 写文件→快照→artifact 事件链，本机通过，下一原生轮补验。

第三轮原生运行 35577767754（30170c66）通过，包含实际 launcher/Job/后代、父退出、错误身份和权限拒绝、实际文件 worker。后续删除没有生产调用者的独立单 PID 终止实验函数，将同句柄拒绝规则直接放在生产 Job 路径验证；不新增第二套终止器。补恢复目录 junction 拒绝、复用 pathlib Windows 保留名判断，最终三平台候选复验。
