# 系统 UUID 初始化发送边界

日期：2026-09-22。状态：confirmed。来源：R3 90 项后端、25 项 UI 检查；shared-data-follow-through.json 记录源码哈希。

复用 SyncOperationRow(systemIdentity)：公开原请求摘要保持不变，生成的 UUID、归属标记、原行证据在第一次发送前固定。Google 单次 batchUpdate 插列/写 UUID/开发者 metadata；未知结果仅按原计划读回核验。明确未发送的原计划可重复发送同一批 UUID。同步原操作发布本地 generation/绑定和成功状态同事务。系统列复用需本工作区原成功计划和当前完整源归属/UUID 校验。

GoogleAccess 标准库 RLock 覆盖同一 workspace 的读计划-写入序列；SQLite 短事务状态/CAS 保留发送与未知结果围栏。新来源结构操作不得越过值发送未知，反向也一样。领取、改绑/解绑和项目生命周期都重验围栏。未来 R4 复用它，不能以仅有进程内锁代替持久未知发送事实。

UUID 是本地 RecordKey 类型；物理 Sheets 单元格仍是文本。公共 lease 和来源校验摘要统一为物理文本键，记录 mark/cursor 保持本地类型。不能因另一绑定把该列映射为文本就获取第二把锁。

限制：受控 Google transport 与真实 HTTP/SQLite/React，不等同 Google 实网、当前打包全链或物理安装；releaseAccepted=false。
