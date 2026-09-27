# 后端依赖公开漏洞扫描

- 日期：2026-09-28；状态：confirmed；基线：`33ae3aa49600840b1700c83723408c494dc201a8` 的当前工作树。
- 执行时间：2026-09-28 01:30 Asia/Shanghai；宿主 macOS 26.4.1 arm64、项目 Python 3.11.13。
- 结论置信度：依赖版本及公告命中为高；AutoFlow 实际可利用性尚未验证。

## 结果

**本机已安装环境与生产锁定依赖均命中 2 个去重公告，涉及 2 个生产直接依赖：Paramiko 3.5.1 和 setuptools 80.10.2。** 两个原始扫描各输出“4 known vulnerabilities”，原因是每个包的同一 `PYSEC` 公告重复出现两次；不能把它们报成 4 个独立漏洞，也不能将两个扫描相加成 8 个。原始 JSON 保留重复项；[去重汇总](dependency/backend-summary.json) 按包、版本和公告 ID 计算。

| 扫描范围 | 实际范围 | 执行结果 |
|---|---|---|
| 当前 `.venv` | 187 个已安装 distribution；跳过本项目 editable 包，实际查询 186 个包 | 2 个受影响包、2 个独立公告；退出码 1，23.571 秒，无超时 |
| frozen 生产 lock，跨平台并集 | `uv export --frozen --no-dev --no-default-groups --no-emit-project` 得到 196 个固定包版本：34 直接、162 传递 | 196 个包全部查询、无跳过；相同 2 个受影响直接依赖；退出码 1，23.232 秒，无超时 |
| 上述生产集合适用于当前宿主的部分 | 167 个包：32 直接、135 传递；这 167 个版本均已安装 | 两个命中均属于这一部分；其余 29 个条件包为跨平台锁定范围，不代表当前宿主已安装 |

已安装环境比宿主生产闭包多 20 个 distribution，其中 1 个是本项目 editable 包，其余 19 个来自开发/构建工具及其依赖。生产传递依赖本次没有已知公告命中；这句话只描述此次数据库查询，不代表未知漏洞不存在。

## 公告与当前项目的关系

| 依赖 / 分类 | 公告与数据库严重度 | 命中原因和修复版本 | 当前应用证据与边界 |
|---|---|---|---|
| `paramiko==3.5.1`；生产直接依赖，当前已安装 | `PYSEC-2026-2858` / `CVE-2026-44405` / `GHSA-r374-rxx8-8654`；GitHub Reviewed Low，CVSS 3.4 | 公告涉及 RSA 的 SHA-1 支持，受影响范围为 `<=4.0.0`；扫描结果 `fix_versions=[]`，公告当时未标记修复 release。不能据此断言上游不存在修复提交。 | 正式 SSH Gateway 实际导入并使用 Paramiko；`gateway.py:85–94` 的连接没有显式 `disabled_algorithms`，`:110` 接受 RSA 私钥。未连接用户 SSH 主机，未验证实际算法协商或攻击条件；版本命中不等于已证实可利用。[公告](https://github.com/advisories/GHSA-r374-rxx8-8654) |
| `setuptools==80.10.2`；生产直接依赖，当前已安装 | `PYSEC-2026-3447` / `CVE-2026-59890` / `GHSA-h35f-9h28-mq5c`；GitHub Reviewed Moderate，CVSS 6.1 | 在 macOS APFS/HFS+ 构建 sdist 时，文件名 Unicode 规范化差异可能绕过 `MANIFEST.in` 排除，意外包含文件；公告修复版本 `83.0.0`。 | 项目声明为 `setuptools>=70,<81`，现有约束排除了已知修复版本。AutoFlow 自身构建后端是 Hatchling，桌面后端冻结走 PyInstaller，因此不能把此公告直接写成当前 App 会泄露文件；本轮未生成/发布 setuptools sdist，也未复现泄露。[公告](https://github.com/advisories/GHSA-h35f-9h28-mq5c) |

项目源码位置：[`pyproject.toml:28`](../../../apps/backend/pyproject.toml)、[`gateway.py:79`](../../../apps/backend/src/autoflow/providers/integrations/gateway.py)、[`build-backend.mjs:10`](../../../scripts/build-backend.mjs)。此处的路径用于审阅当前源码，公告严重度属于上游数据库评分，不代替 AutoFlow 场景优先级。

建议把 Paramiko 的算法限制和可信主机校验纳入 SSH 专项；在专用 SSH 测试端点验证协商、RSA/Ed25519 兼容性后再决定升级或限制策略。setuptools 应先查明 `<81` 上限对应的兼容性需求及实际打包用途，再调整约束、移出不必要的运行依赖或隔离构建工具；不能直接执行自动升级并假定 OCR/人脸识别、冻结打包不受影响。以上为修复方向，本轮没有修改依赖。

## 方法、证据与未覆盖范围

本机没有已安装的 `pip-audit`，因此通过官方 PyPI 的临时 `uvx` 工具环境运行固定版本 `pip-audit==2.10.1`，使用其 PyPI advisory service；没有使用 `--fix`。工具用途和选项依据 [PyPA 官方 pip-audit 文档](https://github.com/pypa/pip-audit)。实际扫描命令、时间与返回码保存在 [执行汇总](dependency/backend-execution-summary.json)。

生产集合由现有 `uv.lock` 使用 `--frozen` 导出，不重新解析或更新锁文件。导出中的平台 marker 保留在 [完整范围](dependency/backend-production-scope.json) 和 [原始 requirements](dependency/backend-production-requirements.txt)；随后只将固定 `name==version` 并集送入 `--no-deps --disable-pip` 查询，避免安装 Windows/Linux 条件依赖。这个方式查询的是跨平台已锁定版本，并不证明这些平台已成功安装或运行。

- [可复运行脚本](dependency/backend-scan.py)：从仓库 Python 运行，仅向证据目录写入；每个扫描 240 秒上限。
- [已安装环境原始结果](dependency/backend-installed.json)、[执行记录](dependency/backend-installed-execution.json)、[日志](dependency/backend-installed.log)。
- [生产依赖原始结果](dependency/backend-production.json)、[执行记录](dependency/backend-production-execution.json)、[日志](dependency/backend-production.log)。
- [扫描前快照](dependency/backend-before.json)、[扫描后快照](dependency/backend-after.json)：`uv.lock`、`pyproject.toml` SHA-256 及已安装包清单完全相同。

本轮查询 PyPI 中已知的 Python 包公告，没有审计 wheel 内嵌原生库、操作系统/Homebrew 组件、CloakBrowser 二进制、模型权重或 Docker 镜像漏洞，也没有解包最终 PyInstaller 产物核对每个模块。因此不能扩写为整个安装包的 SBOM/漏洞扫描全部完成。前端 npm 审计由独立报告给出，不合并计数。
