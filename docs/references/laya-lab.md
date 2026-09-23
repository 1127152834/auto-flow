# Laya 决策实验：来源、部署与接口

- 日期：2026-09-23
- 状态：confirmed（来源和首版设计）；真实权重、平台打包验证结果以实施任务的测试记录为准。
- 验证方式：阅读上游 README、PyPI 元数据、Hugging Face 模型卡与推理源码；核对 AutoFlow 当前 Python、PyInstaller、OpenAPI 和桌面导航实现。

## 外部资料（均于 2026-09-23 核查）

| 来源 | 可直接支持的结论 |
| --- | --- |
| [Laya GitHub](https://github.com/NandhaKishorM/laya) 与 [PyPI](https://pypi.org/project/laya/) | 0.3.6、Python ≥3.10、Apache-2.0、`choice`/`score`/`noul`/Router；PyPI 版本发布于 2026-09-22。 |
| [Laya 模型卡](https://huggingface.co/convaiinnovations/laya) 与 [Typed Decisions 模型卡](https://huggingface.co/convaiinnovations/laya-typed-decisions) | English 512 token、Multilingual 和 Typed Decisions 1024 token；后者英语专用，针对四类工作流微调。模型仓库修订固定为 `1c5edc17a7acd8701df6fc341c0d179f1c62c982`。 |
| [Laya 限制](https://huggingface.co/convaiinnovations/laya#honest-limits) | 长状态、长问题或过多选项会截断；基础模型原始概率偏向过度自信，`score` 相对较弱。作者基准不等于 AutoFlow 业务表现。 |
| [第三方场景评估](https://huggingface.co/convaiinnovations/laya/discussions/3) | 2026-09-20 用 Laya 0.3.4 对 100 个英语场景、305 个决策做的手写测试，报告否定、撤回、算术和置信度分流失败。该结果是不同版本和样本上的观察，不能直接推断 0.3.6 的业务准确率。 |
| [Jev 官方介绍](https://typesafe.ai/blog/introducing-system-one-models-and-jev)、[NanoJev](https://github.com/TianyuCodings/NanoJev)、[Jev 工单路由 Demo](https://github.com/Zafer-Liu/jev-demo-router)、[Laya Space](https://huggingface.co/spaces/convaiinnovations/laya-demo) | 展示候选概率、路由原因、人工兜底和可重放案例的交互参考；不以它们的性能数字推断 Laya。此次未取得可稳定核对的 X/Twitter 原帖，采用这些公开源码和页面。 |

## AutoFlow 部署方式

后端锁定 `laya==0.3.6`，与现有的 Python 3.11、Torch 2.14 一起装入 PyInstaller sidecar。安装包不含模型权重。首次请求某个 checkpoint 时，从固定修订下载该 checkpoint 的模型、tokenizer、encoder 配置到 `AppPaths.cache/laya`；后续从本地缓存读取。下载或加载阶段只显示真实阶段，不显示虚构进度。最多两个模型常驻；切换到第三个会按最近使用情况释放一个，因此以后再次选择被释放的模型会重新加载，但不会重新下载。

由于加入模型依赖后打包的 sidecar 冷启动可能超过原有的 15 秒，生产桌面端及打包冒烟允许最多 90 秒就绪；开发模式仍为 15 秒。这个启动期限与单次模型下载／加载期限分开计算。

Laya 默认优先使用可用 CUDA，其次 Apple Silicon MPS，否则 CPU；GPU 内存不足时上游会回退 CPU。返回的 `runtime.device` 是完成推理时的实际设备。CUDA 是否可用取决于打包时的 PyTorch 构建和本机 NVIDIA 驱动，需要在真实 GPU 上另行验证；无 GPU 的 CI 只能验证依赖导入和 CPU 路径。

首次使用需访问 Hugging Face 模型仓库并预留权重缓存空间。本机两个 checkpoint 的缓存约 1.4 GiB；Typed Decisions 另占空间。当前没有可靠的最低内存实测值，不设未经验证的 RAM 门槛。离线运行仅限已完整下载的 checkpoint。

## HTTP 与隐私边界

`GET /api/v1/lab/laya/status` 不加载权重。`POST /api/v1/lab/laya/predict` 接收 `{model,state,questions}`，模型为 `auto|english|multilingual|typed-decisions`。`state` 是字符串、对象或数组；问题是以 ID 为键的 `choice`、`score`、`noul` 定义。响应返回逐题答案／概率／置信度、路由、输入 token、加载和推理耗时、checkpoint、修订与设备。`noul` 的 `false` 概率由 `1 - P(true)` 补齐。

状态中的 `auto: available` 只表示语言 Router 可用；真正选中的 checkpoint 仍可能显示“未下载”，首次推理时才会下载。

请求最多 16 KiB、8 个问题，每个 `choice`/`score` 为 2–10 项；实际模型 token 与选项预算在加载 tokenizer 后再次校验，避免静默截断。输入错误 422、占用 409、下载／模型失败 503、超时 504。超时只终止 HTTP 等待，不声称能中断已在执行的底层推理；工作线程结束前继续拒绝新请求。实验内容不写入后端日志；用户点击保存后，原始输入才进入按工作区隔离的浏览器 `localStorage`。

自动化预览的 0.85 阈值仅供演示，未经校准；没有调用项目自动化、邮件或其他外部执行接口。若以后接入真实节点，应先积累带人工标签的业务样本，比较基线、校准概率和误判成本，再决定各类动作的准入条件。

## 本机实测（2026-09-23）

在 macOS Apple Silicon 上使用固定修订、`laya==0.3.6`：英文重复扣款输入经 Router 选择 English；中文重复扣款输入经 Router 选择 Multilingual；两次实际设备均为 MPS，分类均返回 `billing`。两模型的缓存合计约 1.4 GiB。包含首次下载和加载的 `loadMs` 分别约 249 秒、348 秒，推理分别约 2.9 秒、1.8 秒；这些是本机网络与环境中的单次观察，不是性能承诺。另通过真实 HTTP 接口一次返回 `choice`、`score`、`noul` 三类答案及完整概率和运行指标；该样例的 `score` 置信度只有 0.3079，因此演示阈值会建议人工复核。

桌面端在独立临时工作区完成了真实界面流程：进入“实验室”→选择“中文多语言路由”→运行推理→看到 Multilingual、MPS、逐项概率和自动化预览→手动保存实验记录。打包后的 macOS arm64 sidecar 也以同一固定权重完成中文 HTTP 推理；这验证了本机依赖收集，不替代 Windows、macOS Intel 或 CUDA 的实机验收。
