# iOS 实验 Demo

- 日期：2026-09-13；状态：confirmed（用户已明确授权克隆两个项目并开始实验 Demo）。
- 分类：有界实验，独立于 AutoFlow 正式架构；沿用安卓 Demo 的 Python + React 组织方式。
- 输入：固定版本 vphone-cli / vphone-aio；Apple Silicon Mac。
- 输出：本机诊断、设备列表、受控启停、截图预览/点击/滑动/按键/设置剪贴板、单设备步骤回放、Python socket 示例、实际验证记录。
- 第一阶段只用 upstream CLI 与 host socket；不修改上游内核或 guest、不接入正式工作流、不把未实现的控件树与输入能力标为已支持。

## 接口与实施顺序

1. 原仓库保持独立 Git；aio 克隆时跳过大体积 LFS 镜像，CLI 包含递归子模块。记录 commit 与恢复方式。
2. Python 标准库实现 socket 客户端与同源 HTTP 服务；固定动作白名单、数值范围、socket 超时、真实截图响应验证、设备串行占用。
3. React 组件先做诊断、设备屏幕、步骤控制，再组合页面。所有状态来自真实后端；没有设备显示空状态。
4. `GET /api/state` 返回宿主检查、设备配置、进程状态和本次服务 token；`POST /api/action` 执行一个白名单动作；`POST /api/lifecycle` 只启停本 Demo 管理的进程。变更请求验证 Host/Origin 和 token。默认 loopback 8083。
5. 默认 VM 根目录为 `~/.vphone-autoflow-demo`，避免项目绝对路径过长触发 Unix socket 长度上限。首次固件创建在终端执行，让上游交互选择和系统授权有真实终端；页面不采集 sudo 密码。
6. 回放串行执行已有动作、每步回读截图；成功仅表示指令与图像传输成功，不等于业务语义断言。暂停在步骤边界生效。截图坐标按 plist 的完整屏幕尺寸换算。

## 验证

- Python unittest：真实临时 Unix socket 验证缩放、分帧读取、错误/空图像/超时、非法动作和路径；HTTP Host/Origin/token 拒绝。
- React：TypeScript、Vitest、构建，浏览器检查真实环境诊断、空设备状态。
- 上游：源码编译及签名，宿主 preflight；只有实际 iOS 启动并能回读画面才算实机通过。
- 当研究虚拟机策略关闭时，保存真实失败证据，完成可独立验证的 Demo，记录恢复模式与重启后的继续步骤。不得自动更改 SIP/AMFI、重启宿主或伪造设备。
