# 自定义 Android 候选镜像生命周期实测

- 日期：2026-09-24；状态：confirmed（下列真实链），AM2 和完整目标仍 partial。
- 基线：隔离分支 `codex/android-management-complete@471b816f`；本增量只新增 QA 脚本和证据，不改生产代码、契约、迁移或前端。
- 平台：Apple Silicon macOS、Lima ARM64 `autoflow-redroid`、Docker/ReDroid。
- [可运行脚本](scripts/custom-image-smoke.py)、[实际结果 JSON](2026-09-24-custom-image-result.json)。

## 候选来源与实际步骤

从本机固定基础 imageId `sha256:5a42a569ee1d7c71796c0385e906cbaa4c3e0a162a56d9f26b29bdb1befac13b` 派生两份独立候选。Docker build 的网络关闭；构建上下文只含 `FROM <固定 imageId>`、QA 工作区标签以及 `COPY marker /autoflow-qa-marker`，文件内容分别为 candidate-v1/v2。未修改基础镜像或原 tag，没有加入 GApps，也没有账户数据。

实际候选 A 为 `sha256:7be20039abba18ffa8467d94092c13238bb78150d7f4e96a31b5fa0290d2aa72`；B 为 `sha256:2fc0639293e24e8c42acf4ebe60d0c475101ad1fc7f51b3bdbc8f4cbb4162aca`。A 完成真实 Android 启动、重启和备份恢复；B 用于 tag 漂移，不声称已启动 B。

全链使用完整认证 HTTP 后端、真实 SQLite、生产 Mac runtime 和新建资源，没有替换运行时结果：

1. 登记基础/A/B，Google validation 均为 not_tested；创建引用 A 的模板。只有模板引用时，删除 A 返回 409 ANDROID_IMAGE_REFERENCED。
2. 经模板批次创建并启动候选，另建未修改基础实例；两台均 ready。候选可读到 candidate-v1；基础实例没有该测试文件。
3. 将独立 QA candidate tag 改指 B，并把模板更新为 B；旧 revision 更新返回409。原候选 restart 后数据库、creationConfig 和实际 Docker Image 均保持 A，读回仍为 candidate-v1。此时只有设备引用 A，内容删除仍409。
4. 候选写入合成数据、停机备份；恢复生成新 deviceId/容器/卷。新实例启动后，镜像文件为 candidate-v1，数据探针为 custom-data，证明按备份固定 imageId 恢复，没有使用已漂移 tag。
5. 删除原候选和恢复实例；此时仅备份引用 A，删除仍409。公开清理预览必须恰好选中该备份，执行后备份记录消失；随后 HTTP 删除 A 内容成功并核实 imageId 不存在。模板归档成功。
6. 未修改基础实例仍 ready，基础 tag 的 imageId 不变。最终经生产生命周期清理本轮三台设备及数据卷、备份；仅清理带本轮标签的候选镜像，未使用全局 prune 或删除其他实例。

## 命令与实际输出

| 命令（仓库根） | 输出摘要 |
| --- | --- |
| `uv run --project apps/backend python docs/qa/android-management/scripts/custom-image-smoke.py --allow-device-mutation` | 最终 exit0；status=passed；deleteBlockedBy=[template,device,backup]；candidateAndBaseReady/tagDriftPreservesFrozenImage/customBackupRestored/candidateContentDeleted/baseUnchanged/ownedDevicesBackupsImagesDeleted 均true；googleValidation=not_tested。 |
| `uv run --project apps/backend pytest apps/backend/tests/integration/test_android_images_templates.py apps/backend/tests/contract/test_android_images.py apps/backend/tests/contract/test_android_templates.py apps/backend/tests/unit/test_android_images.py apps/backend/tests/unit/test_android_image_catalog.py -q` | exit0；40 passed, 1 warning in0.95s；既有 Starlette anyio 别名弃用提示。 |
| `uv run --project apps/backend ruff check docs/qa/android-management/scripts/custom-image-smoke.py` | exit0；All checks passed。 |
| 新脚本 `--help` / 缺少授权开关 | exit0 / exit2；后者要求 --allow-device-mutation。 |
| `uv run --project apps/backend alembic -c apps/backend/src/autoflow/infrastructure/database/alembic.ini heads` | am01_management_operations (head)，唯一head。 |
| `git diff --check` | exit0。 |

## 失败、外部中断与重跑

- QA 初版等待错误终态 completed，实际批次已 succeeded；确认无在途操作后对测试进程发SIGINT，清理成功，修正脚本为契约终态后重跑。该轮exit130，不计完整通过。
- 第二轮清理预览使用错误的 backup: 前缀，得到空预览，真实镜像删除仍因备份引用返回409；脚本exit1，生产保护正确。改用实际备份ID，并增加预览恰含该ID及清理后记录消失的断言，没有修改生产逻辑。
- 第三轮执行等待被外部中断，随后确认原QA进程不存在、同工作区后端仍存活。停止该后端，经生产流程删除两台自建实例，并按标签和固定ID清理候选。该轮无完整结果，不计通过；不是因观察超时就重复启动。
- 第四轮完整重跑exit0，结果见JSON。随后另外使用生产 verify_deleted 和 Docker `image ls -a --no-trunc -q` 复核上述所有轮次的资源，首次包含 -a 的复核发现第二轮一个无tag候选仍在，旧枚举漏掉该镜像，因此第二轮先前清理标志不代表完整清理。核实该固定ID、归属标签且无其他tag后，使用 image rm --no-prune 清除。再次核实四轮共9台设备均missing、8个候选ID均不存在、备份记录为0，见[清理复核](2026-09-24-custom-image-cleanup-result.json)。脚本最终也将镜像清理枚举加强为包含 -a；这一枚举在上述独立复核中实际执行。

这是新增真实验收证据，未改业务逻辑，不冒称新增生产代码 RED→GREEN。受测生产/前端代码未变，全量门槛沿用[命令树修复验证](2026-09-24-restore-cancel-and-disk-full.md)，不写成本轮重新执行。

T12.3 已有基础与可启动自定义候选的直接证据。T12.4 的停用新入口/保留表记录/向前补丁回退演练仍未运行；T09 桌面内容删除和真实断线、GApps候选与账号链仍未验收。这个带测试文件的候选不是谷歌兼容性或任意ROM兼容性证明。
