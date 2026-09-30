# PM9 Windows 现有文件安全读取子片

日期：2026-09-23。状态：confirmed（原生读取子片），最终候选三平台回归待完成。来源：S4 已批准规格、生产代码、定向测试及 Windows Actions 35829751668 @2fe33528。

- `read_binary_output` 现在以已固定的父目录句柄和拒绝重解析点的目标句柄读取普通现有文件；目标句柄不共享写入/删除，二进制读取后复核身份。共用原有大小、取消、冲突语义；Base64 文件输入已走真实 worker 验证。
- Windows 原生 102 passed/28 skipped；新测试直接证明二进制内容、缺失、超限、目标写/删拒绝、父目录改名拒绝及 junction 拒绝。后补读取前取消断言不属于该次 run。
- 现有文件覆盖/追加仍返回 501；先前的持有目标句柄替换实验不能满足已批准的条件原子提交，不可放宽检查。三平台最终候选、物理安装、Google/OAuth 与签名仍独立待验收。`releaseAccepted=false`。
- 随后发现读取缺失路径沿用写入路径会建目录。全平台直接断言先失败后通过；读取现只打开已有父目录。旧 35830250231 完整矩阵已取消，不算最终候选证据。
- 35830710429 Windows 平台步骤的新读取和真实 worker 均通过，但一个旧表格 worker 测试仍预期 Windows 501，导致 250 passed/28 skipped/1 failed；其他两平台取消。修订旧断言，开放既有新文件 CSV/XLSX 差分测试在 Windows 运行，并扩充原生专项选择；本机相关 127 passed/17 skipped，最终原生与完整候选待复验。
- 35831675395 的宽差分文件选择因专项未检出冻结参考仓库产生 32 个夹具失败；Windows 绝对盘符路径另有应用层拒绝，未因新文件适配器而接通。专项收窄到两项相对新文件测试，绝对路径测试保留跳过并登记缺口；此轮原生专项不算通过。
- 收窄后的 35832075007 @113668fd 原生专项 127 passed/28 skipped，含上述真实读取/表格 worker 与两项相对新文件 CSV/XLSX。完整三平台候选仍待通过；`releaseAccepted=false`。
- 表格应用层原先无条件拒绝 Windows 绝对盘符路径；在 `Path.is_absolute()` 且盘符形状合法时放行，UNC/盘符相对路径/上跳仍拒绝，由 Windows 原生适配器完成最后核验。旧 35832710320 的唯一失败是斜杠字符串断言；改按 `Path` 身份比较后 35832925704 @680fd0ca 原生 131 passed/29 skipped，含真实 worker 的绝对 XLSX 导出。完整矩阵待完成。
- 最终源码 dadb24a1 的 Actions 35833223498 三平台 checks 全 success：Windows 原生边界 251/28、完整后端 3469/85，Mac 两平台后端各 3477/77，三平台前端各 5471、选定真实 worker 各 29/11 deselected；源码和打包 smoke、安装包构建通过。CI 证据及测量见 `docs/project-management/implementation/pm9/ci-s4-final-follow-through.json`，覆盖前段“完整矩阵待完成”。状态 confirmed，来源为该 run 的作业日志和上传报告。
- Windows 打包桌面真实 worker 1004 日志/128882 ms，观察 467/min；合成固定输入 1000/60120 ms。五路 HTTP 10000 行/834889 ms、1 次 busy 重试。两种负载和吞吐不互换，也不推断新性能门槛。
- 现有文件覆盖/追加仍 501；同路径条件原子替换不可证明，补充规格和版本化输出实施计划仅 proposed，未获架构确认。L1–L3、M1–M3、实网授权、物理安装、原生面板/凭据及签名公证继续作为缺口。`releaseAccepted=false`，PR 保持 draft。
- 随后从最终 CI 35833223498 取 ARM DMG，SHA256 `61b6ff8b...`，镜像校验/只读挂载/隔离复制后用公开版 145 内核跑原版安装应用桌面全链通过；具体检查和测量见 `installed-arm-current-candidate.json`。本机 Pro 首次版别不匹配、再试无有效许可均为失败，临时脚本改动已撤回；状态 confirmed，证据仅限当前这台 ARM Mac，发行条件仍 pending。
