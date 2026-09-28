# DEP-01 依赖修复与兼容性记录

日期：2026-09-28；状态：confirmed（仅下述已执行范围）；置信度：高。官方资料本轮重新读取；首次网络失败、registry临时404与再次成功均保留，不将网络错误计为零漏洞。

## Monaco / DOMPurify

官方 [Monaco 0.57.0 发布](https://github.com/microsoft/monaco-editor/releases/tag/v0.57.0) 与 npm registry 的确切版本、依赖、integrity 已核对。只升级 monaco-editor 0.55.1→0.57.0 并精确锁定；未 force、未进行全依赖升级。候选依赖指定DOMPurify 3.4.15；实际安装的 `esm/vs/base/browser/dompurify/dompurify.js` 以及重新构建的 AICodeAssistant chunk 都显示3.4.15。原审计曾证实这两个位置为3.2.7，不能仅用顶层依赖替代嵌入代码验证。

新增 scripts/editor-sanitizer.test.mjs 检查编辑器真正嵌入实现至少达到本次审查基线3.4.15，旧版3.2.7必失败；不把版本门禁当作通用XSS证明。编辑器定向4文件38项通过；tsc、Electron前端构建通过。npm-audit-after.json 是本次修复后原始扫描，0公告匹配；不等于整个应用已不存在安全问题。实际桌面/打包编辑器交互单列验收。

## SSH SHA-1

当前 [Paramiko公告](https://github.com/advisories/GHSA-r374-rxx8-8654) 仍列<=4.0.0、无patched release。此次不凭猜测升级主版本；在唯一 WorkflowIntegrationGateway 连接入口使用[官方 disabled_algorithms](https://docs.paramiko.org/en/stable/api/client.html) 参数同时禁用 host keys 和 user pubkeys 的 ssh-rsa（RSA SHA-1）。RSA密钥本身仍支持rsa-sha2-256/512，不删除RSA私钥加载能力。

真实隔离回环SSH服务器协商：修复前3个安全断言失败；修复后限定ssh-rsa服务器被明确拒绝，rsa-sha2-256/512连接成功，真实transport的preferred_pubkeys不再含ssh-rsa。加上原生产worker五节点SSH/SFTP文件往返/失败/取消，共13项通过，所有自有服务器/命令子进程关闭。Ruff和普通mypy通过。没有访问用户SSH账户，也没有把协议测试服务当作供应商实网证据。

兼容变化：仅支持RSA SHA-1的旧SSH服务器会连接失败，错误保留现有SSH连接失败分类；不提供静默降级。依赖版本仍被公告扫描匹配，本修复是应用入口算法缓解，不能将其写为Paramiko库自身全部修复。现有AutoAddPolicy缺少持久可信主机确认仍是独立设计缺口，不能因算法限制通过就标记SSH整体隔离完成。

## setuptools 保留的兼容阻塞

[官方公告](https://github.com/advisories/GHSA-h35f-9h28-mq5c)针对macOS构建sdist时Unicode路径排除，修复83.0.0。当前声明setuptools>=70,<81，实际face_recognition_models 0.3.0仍直接导入pkg_resources；[PyPI上游版本](https://pypi.org/project/face-recognition-models/)仍为0.3.0，不能直接跨过移除pkg_resources的版本并假定识别功能可用。AutoFlow自身使用Hatchling和PyInstaller，本轮没有运行/发布setuptools sdist；公告匹配不等于已证明应用泄露。

此项未修复。后续需要验证上游模型资源读取替换及冻结包兼容，再移除运行期setuptools依赖或升级到修复版本；本轮不修改site-packages、不注入同名兼容模块、不隐藏扫描结果。

## SSH 主机信任差异方案（proposed，未实施）

这不是依赖版本升级能消除的缺口：当前首次连接自动信任未知主机。最小方案是在既有SSH连接节点增加明确的SHA-256主机公钥指纹配置，由唯一连接gateway在发送认证凭据之前校验远端key；指纹不是秘密，不进入系统凭据键，也不新增第二套凭据或数据库框架。缺失、格式错误或不匹配时明确失败，不自动接受新key，不从一次未经认证的连接自动填写可信指纹。指纹由操作者从已可信渠道取得。

兼容影响：旧工作流未配置指纹时将不能继续连接，必须显式补全；保留原文档和凭据，不做数据迁移，不清理既有keychain条目。不提供静默AutoAdd回退。若产品选择维持旧工作流自动连接，则该风险仍存在，不能标为安全修复完成。

待决定部分仅为是否批准这一旧SSH工作流的失败关闭兼容变化及新增节点字段。批准后按后端连接契约→生成客户端/配置面板/可定位错误→真实回环SSH匹配/不匹配/主机更换/旧文档拒绝→生产worker文件往返/取消的顺序实施；证明错误主机未收到认证尝试，并保持当前RSA SHA-1禁用。当前未发起第二个打断式问题，也未将方案视作已批准；本轮仍有先前人工恢复语义问题待答。
