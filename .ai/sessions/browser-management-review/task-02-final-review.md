# 任务 2 修复最终复审报告

- 日期：2026-09-12
- 审查范围：`e3ac989..f1c9e05` 的任务 2 第二轮修复包；忽略 renderer、ProxyPanel 与自动化文档并发改动。
- 置信度：高
- 结论：**PASS**

## 复审结论

未发现阻塞任务 2 的问题。上次报告中的两个 P2 已完整修复，修复包没有引入可见回归。

1. URL 与 timezone 的解析异常现在统一转换为 `ProfileValidationError`。`urlparse()` 后主动求值 `hostname` 和 `port`，覆盖畸形 IPv6 与非法端口；`ZoneInfo()` 的 `ZoneInfoNotFoundError`、`TypeError`、`ValueError` 和 `OSError` 均被收敛到领域错误。回归测试覆盖畸形 IPv6、非法端口、空时区和绝对路径，额外探针也验证 `../UTC` 不再泄漏原生异常。
2. locale 校验已按 RFC 5646 的 BCP 47 子标签结构实现：primary language、extlang、script、region、variant、extension、private-use 与固定 grandfathered 标签均按位置和长度解析；重复 variant 与重复 singleton 会被拒绝，比较大小写不敏感。RFC 5646 Appendix A 的 31 个有效示例及 3 个标准无效示例均通过额外探针，原复审样例 `en-US-GB`、`en-a-aaa`、`x-private` 的结果也符合预期。

这里验证的是计划要求的 BCP 47 **语法/结构**，不要求随 IANA Language Subtag Registry 做动态语义有效性校验。RFC 5646 也明确区分 well-formed syntax 与 registry-backed validity；当前实现与冻结计划的“语法校验”一致。

## 回归与复杂度检查

- 修复仅涉及 `ProfileSpec` 校验、对应单元测试和任务报告，没有改变数据库映射、事务、迁移或启动装配。
- `_is_bcp47()` 是无 I/O 的领域内纯函数，没有新增生产依赖或跨层引用。相对于引入并维护外部 locale 解析依赖，这个实现保持了任务 2 的最小依赖边界。
- `git diff --check e3ac989..f1c9e05` 通过；修复包仅包含预期的 3 个文件。

## 验证结果

```text
ProfileSpec 聚焦测试：29 passed
全量后端测试：46 passed, 2 warnings
Ruff（src tests）：All checks passed
mypy（src）：Success: no issues found in 27 source files
RFC 5646 Appendix A/无效样例与解析异常额外探针：PASS
git diff --check e3ac989..f1c9e05：通过
```

两条 warning 来自现有 Starlette/FastAPI 测试依赖的弃用提示，不由本修复引入。

## 核对依据

- `docs/superpowers/plans/2026-09-12-browser-management.md` 任务 2 与第 2.1 节冻结契约。
- `.superpowers/sdd/2026-09-12-browser-management/task-2-review.md`。
- `.superpowers/sdd/2026-09-12-browser-management/task-2-rereview.md`。
- `.superpowers/sdd/2026-09-12-browser-management/task-2-report.md`。
- RFC 5646 Sections 2.1、2.2.5、2.2.6、2.2.9 与 Appendix A：https://www.rfc-editor.org/rfc/rfc5646.html
