# 任务 6 第二轮修复复审报告

- 日期：2026-09-12
- 复审范围：仅提交 `b45ca84`（父提交 `f8d55f8` 的主线前端依赖不在本轮范围）
- 指定核对项：授权下载争用 License 门禁映射为 `KERNEL_BUSY`；退出争用保持 `LICENSE_IN_USE`；双 `KernelService` 回归测试的确定性
- 排除范围：Task 6 全量验收、Task 7 renderer 依赖与 UI、工作树中现存 automation/renderer 草稿
- 置信度：高
- 规格合规结论：**PASS**
- 代码质量结论：**PASS**

## Findings

无。

## 定向复审

### 授权下载门禁争用：PASS

`KernelService.download()` 只在 `edition == "licensed"` 的分支捕获 `license_guard()` 使用的 `LicenseInUse`，并在下载调用边界转换为 `KernelBusy`。HTTP 既有异常映射会因此返回 409 `KERNEL_BUSY`，与“同一时间只运行一个安装工作进程”的契约一致。公开版下载路径及底层安装门禁没有改动。

生产 `KernelWorkerManager.start()` 本身不会抛出 `LicenseInUse`；它的并发安装冲突为 `KernelWorkerManagerBusy`（`KernelBusy` 子类），其余启动故障映射为 `KernelWorkerManagerError`。因此本提交的捕获范围在当前生产调用链中不会吞掉另一类既有 License 业务错误。

### License 退出语义：PASS

`KernelService.disconnect_license()` 未增加异常转换。它取得同一个 `.license.lock` 失败时仍由 `FilesystemKernelInstallationStore.license_guard()` 抛出 `LicenseInUse`；取得门禁后发现活动授权 operation 时，License provider 也仍抛出 `LicenseInUse`。两种退出争用均继续映射为 409 `LICENSE_IN_USE`。

既有 `test_license_disconnect_cannot_pass_while_download_is_registering` 继续在授权下载登记窗口断言 `LicenseInUse`，本提交没有弱化原 P1 的旧 key 安全回归。

### 双 Service 测试确定性：PASS

新增测试创建两个独立 `KernelService` 和两个独立 `FilesystemKernelInstallationStore`，但让它们指向同一 kernels 根目录。首个服务的 `PausingOperations.start()` 在已取得 `.license.lock` 后设置 `entered` 事件，并阻塞在 `release` 事件；测试等待 `entered` 后才调用第二个服务，因此第二次下载必然发生在首个服务持锁期间。

底层 `ExclusiveFileLock.acquire()` 使用非阻塞 OS 文件锁。第二个 store 通过独立文件描述符争用同一 `.license.lock`，稳定进入 `LicenseInUse` → `KernelBusy` 映射分支；若第二个调用错误进入 operation manager，测试替身会抛出 `AssertionError`，不会产生假阳性。首个任务随后被显式释放并等待完成，测试也覆盖锁的正常退出路径。

## 验证结果

```text
uv run --directory apps/backend pytest tests/unit/test_kernel_service.py -q
10 passed in 0.06s

uv run --directory apps/backend ruff check \
  src/autoflow/application/kernels/service.py \
  tests/unit/test_kernel_service.py
All checks passed!

uv run --directory apps/backend mypy \
  src/autoflow/application/kernels/service.py
Success: no issues found in 1 source file

git diff --check b45ca84^ b45ca84
PASS
```

当前 HEAD 为 `b45ca84`。工作树中的 desktop/automation 草稿均未进入该提交，也未被本次复审修改。

## 结论

`b45ca84` 已关闭上一轮唯一 P2 finding：授权下载争用 License 门禁现在返回 `KERNEL_BUSY`，License 退出路径继续返回 `LICENSE_IN_USE`，并由确定性的双 `KernelService` 文件锁争用测试覆盖。Task 6 的这轮修复可以关闭。
