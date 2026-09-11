# 任务 4 修复定向复审报告

- 日期：2026-09-12
- 复审范围：提交 `7296105` 相对 `a0e3fb2` 的任务 4 修复包；对照原审查 `task-4-review.md`、修复包 `task-4-rereview.diff`、冻结计划及本地安装的 `cloakbrowser==0.5.9` 源码
- 范围限制：只审查 `domain/kernels`、`providers/kernel`、CloakBrowser 凭据适配及 `test_kernel_provider.py`；忽略当前工作区的 renderer、模型管理和自动化文档改动
- 置信度：高
- 结论：**PASS**

## Findings

未发现 P0/P1/P2 阻断项。原审查的四项问题均已修复，修复包没有引入新的任务 4 回归。

## 原 findings 修复核对

### 1. 版本格式与 wrapper 0.5.9 一致 — ADDRESSED

`catalog.py` 现在用共享的 `is_valid_kernel_version()` 约束公开 release、授权 release 和本机安装目录，接受四段或五段纯数字版本。该接受集合与本地 `cloakbrowser.config._VERSION_PIN_RE` 的 `^[0-9]+(?:\.[0-9]+){3,4}$` 一致。

- `../../escape`、绝对路径、带 `v` 前缀、三段和六段版本均被拒绝。
- `151.0.7922.108` 与 `151.0.7922.108.3` 均被 provider 和 wrapper 接受。
- `download_with_wrapper()` 在调用 SDK 前再次检查显式版本，不把非法 pin 传入 wrapper。
- 新增 `KernelVersionInvalid` 是下载边界所需的结构化错误，没有暴露远端值或用户输入。

目录扫描继续只接受符合该格式、含预期可执行文件且没有目录/可执行文件越界链接的安装项。任务 5 仍需验证 worker 返回的 resolved version 与路径后再原子发布；这属于已批准的后续边界，不是任务 4 缺陷。

### 2. wrapper 返回 `None` 的错误分类 — ADDRESSED

`validate_license_with_wrapper()` 现在把两类不可用情况统一映射为 `LicenseValidationUnavailable`：wrapper 调用抛出异常，或 `validate_license()` 返回 `None`。非空且 `valid=False` 的响应仍生成无效状态，并由 `CloakBrowserLicenseProvider.connect()` 映射为 `LicenseInvalid`；过期响应也保持无效。

测试分别覆盖 `None`、明确无效、过期和异常四条路径，并验证异常文字不泄露测试 key。不可用和无效校验都发生在凭据写入前，旧凭据不会被覆盖。

### 3. free plan 使用实际 resolved version — ADDRESSED

新的 free plan 测试实际调用 `download_with_wrapper()`，再进入锁定 wrapper 0.5.9 的公开 `ensure_binary()`。测试仅替换网络/文件下载相关依赖和 wrapper 内部 `_ensure_pro_binary()`，保留 wrapper 自身的 free plan 分支，因此证明了：

- 有效 free key 会把请求的版本 pin 丢弃，以 `requested_version=None` 调用授权下载路径；
- SDK 返回的路径可以指向服务器实际选择的另一版本；
- provider 通过扫描和精确可执行路径匹配，得到该返回路径中的 `152.0.8000.1`，而不是 UI 请求的 `151.0.7922.108.3`。

测试中的版本均符合真实 wrapper 格式，且 `-pro` 目录语义与 0.5.9 `_ensure_pro_binary()`/`get_binary_path(..., pro=True)` 一致。

### 4. strict mypy — ADDRESSED

原来多余的 `# type: ignore[import-untyped]` 已从有类型可推导的 `get_session_seats` import 移除。对任务 4 生产文件执行 strict mypy 通过；项目配置的 `mypy src` 也通过。保留在 wrapper 顶层动态导入处的两个 ignore 仍为必要项，因为 `cloakbrowser==0.5.9` 没有 `py.typed` 标记。

## Worker 与依赖边界

本轮不把“尚无 worker 实现”列为 finding。任务 5 明确负责 worker、staging、父进程路径验证和原子发布，任务 4 的修复符合这一依赖顺序：

- `CloakBrowserCatalogProvider` 不再默认直接绑定 `load_licensed_catalog`，而是强制注入 `licensed_catalog` 调用端口；
- `CloakBrowserLicenseProvider` 继续强制注入 `LicenseValidator`；
- catalog、license、download 三个直接接触 wrapper 的入口均集中在 provider 模块，并明确标注必须由任务 5 在设置任务专属 `CLOAKBROWSER_CACHE_DIR` 后于 worker 进程调用。

这避免任务 4 的 sidecar provider 装配提前把有全局缓存状态的 wrapper 固化进主进程，同时没有为尚未实现的 worker 预造额外抽象。

## 验证结果

```text
任务 4 聚焦 pytest：32 passed in 0.10s
后端全量 pytest：111 passed, 2 warnings in 1.36s
任务 4 Ruff：All checks passed
任务 4 生产文件 strict mypy：Success: no issues found
项目 mypy src：Success: no issues found in 46 source files
cloakbrowser 安装版本：0.5.9
cloakbrowser 锁定版本：0.5.9
uv lock --check：Resolved 74 packages
git diff --check a0e3fb2..7296105：通过
版本接受集合对照 wrapper `_VERSION_PIN_RE` 探针：通过
```

两条 pytest warning 来自现有 FastAPI/Starlette 测试依赖的弃用提示，与本修复无关。当前 HEAD 相对 `7296105` 没有任务 4 后端文件变化，因此以上结果对应复审包内容。
