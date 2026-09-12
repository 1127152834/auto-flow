# redroid Demo 实施

- 日期：2026-09-13。
- 状态：confirmed。
- 授权：用户确认已保存的实施计划，随后明确要求实现；不再等待计划批准。
- 范围：`reference/redroid-demo/` 独立 Flask + Docker SDK / React + TypeScript + Vite。保留 RedroidManager / redroid-script 两个固定版本仓库原样，不接入 AutoFlow 正式服务。
- 输出：[启动与使用说明](../../reference/redroid-demo/README.md)、[API](../../reference/redroid-demo/API.md)、[复制来源](../../reference/redroid-demo/THIRD_PARTY.md)、[验证记录](../../reference/redroid-demo/VERIFICATION.md)。
- 功能：三实例上限、后台并发二、生命周期/配置复制、每设备互斥、单帧截图和坐标输入、APK、批量 Python 示例、固定源码 Magisk 构建及分层 root 记录。管理和 ADB 端口只发布在本机。
- 验证：25 后端 + 17 React + 7 脚本测试通过；Python 3.11 和 Linux amd64 镜像测试通过；类型/有限 lint/构建/Compose/真实 Docker socket 与 HTTP/浏览器检查通过。具体命令和证明范围以上述记录为准。
- 实际限制：当前 macOS arm64 + Docker Desktop 缺 binder 和 Android 镜像，后端准确阻止 Android 创建。没有 Windows/WSL、真实 Android、APK 或 Magisk/App root 实测结果。
- 经验：Docker SDK 不继承 Docker CLI 当前 context；CLI loopback 请求需避免环境代理干扰；Magisk 缺命令要通过固定 Android shell 返回诊断；批量创建部分失败或响应丢失时仍要逐台继续/发现并清理本次资源。
- 下一步：按验证矩阵在符合条件的 Windows/WSL2 或 Linux amd64 节点执行四个真实场景；摄像头、环境伪装、串流、集群不在本次实现范围。
