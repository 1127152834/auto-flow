# PM9 验收基础设施

日期：2026-09-20；状态：confirmed（已验证部分），完整 PM9 in_progress。

用户要求先汇总 baseline 再开 PM9 分支；基线归并见同日 baseline-before-pm9 会话。用户确认其他平台使用现有 Actions，实机缺口保留。

本次复用生产 HTTP 合同与 Electron CDP，更新已失效 PM1 smoke，并新增共享断言的桌面入口；输出保护防止覆盖 PM1 历史，拒绝 QA 环境注入，验证等号 executable 参数确实进入打包产物。删除操作通过 workspace 原键回执核验成功，避免删除后项目 scope 404 造成错误失败。

修复真实浏览器测试过时的 bootstrap 名与被 Studio 重用的 HTML 选择器。最终 8 项生产浏览器测试通过；无新增运行时产品后门。全量与实际截图/万行数据证据见 `docs/project-management/implementation/pm9/`，复跑命令和边界见 `docs/migration/project-management-validation.md`。

独立审查指出的 CLI 参数和 QA 环境问题已修复，脚本 94 项通过。核心项目执行仍仅四节点；共享图运行时与 capability RPC 的规格已具体化为 R1–R4，按 AGENTS 架构审批规则待确认。下一步为 Actions 实际运行核验与获批后的完整执行接入；不得将本提交标为 PM9 全部完成。

Actions 首次推送运行 35507028913 的 arm64 前端结果为 5442 passed / 3 failed：测试写死上海时间、jsdom Blob 被 Node 22 Response 当作原生 Blob。已在 Node 22 + UTC 复现并修正夹具，相关 10 项通过，Node 22 脚本 94 项、类型和 lint 通过。CI 全量前端测试移到打包冒烟后以尽早采集平台构建证据，未删减测试或忽略失败；继续实际重跑。

当前代码提交 `10dc916c` 已推送，Actions 运行 35507610003 已开始；本记录时三平台均进行中，未宣称结果通过。PM9 仍未完成，R1–R4 架构确认待用户答复，缺失实机证据仍待验收。
