# Mac 验证证据

日期：2026-09-13；状态：confirmed。说明和局限见 [MAC_TEST.md](../../MAC_TEST.md)。

- `batch-summary.json`：真实三实例 Python 示例及清理原始结果。
- `live-results.json`：隔离、失败、安装结果与 API root。保留有意失败和修复前失败，不能仅按失败条目数量判断最终状态。
- `root-build.json`：固定脚本构建时的来源、下载摘要与镜像产物；构建时未做启动验证，后续结果另存。
- `mac-base-adb.json`、`mac-root-adb.json`：VM 宿主 ADB 独立验证。
- `vm-restart.json`：整台 VM 停止/启动后的环境、设备启动、数据和 Magisk 核查。
- `final-resources.json`：最后保留的两个实例、两个设备卷及上传卷，无多余测试卷。
- `notes-ui-text.png`：浏览器发送含空格及 `%s` 的文本后的真实 Android PNG。

动态端口和任务 ID 是本次观测值，复测会变化；不应写入配置。没有应用内 root 授权证据。
