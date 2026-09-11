# 任务 9 Round 1 修复复审报告

- 日期：2026-09-12
- 复审范围：`2b7e000..d829c6f`，仅核对 `task-9-review.md` 中唯一 P2 及该修复 diff 新引入的重要问题
- 依据：`task-9-review.md`、`task-9-rereview.diff`、`task-9-brief.md`、提交源码和指定测试
- 排除范围：Task 9 其余既有实现、Task 10/12 及其他并行工作区改动；不扩大为 profiles 全组件审计
- 置信度：高
- 结论：**ADDRESSED**

## Findings

无。未发现该修复 diff 新引入的重要问题。

## 唯一 P2 闭环证据

- `ProfileFormDialog.tsx:53-59` 将后端 `viewportJson` 映射到 `viewportMode`，并为它指定当前已挂载的 `[data-profile-viewport-focus]` 焦点目标；`ProfileFormDialog.tsx:107-115` 在切换到“浏览器环境”标签后的 animation frame 聚焦该目标。因此跟随浏览器和预设模式聚焦“视口预设”，自定义模式聚焦“视口宽”，不再查询条件卸载的 `name="viewportWidth"`。
- 跟随浏览器和预设模式共用的 `Select` 带 `data-profile-viewport-focus`，服务端错误存在时设置 `aria-invalid`，并用 `aria-describedby="profile-viewport-error"` 指向同区块中 `id="profile-viewport-error"`、`role="alert"` 的可见错误文本（`EnvironmentFields.tsx:84-88`）。错误的显示、关联和聚焦三项均成立。
- 自定义模式的“视口宽”输入带同一焦点标记。`FormField` 接收 `errors.viewportWidth?.message ?? errors.viewportMode?.message` 后生成 `id="profile-viewport-width-error"` 的 `role="alert"`；输入的 `aria-describedby` 指向该 ID，并在 `viewportMode` 服务端错误存在时标记 `aria-invalid`（`EnvironmentFields.tsx:76-79`）。自定义模式同样完成显示、关联和聚焦。
- 新增参数化回归通过真实 `ApiProvider` 和 fake network 分别让 `viewportJson: null`、预设尺寸 `1280 × 800`、自定义尺寸 `1234 × 777` 收到同一 422，验证标签切换、错误可见和对应控件获得焦点（`ProfileFormDialog.test.tsx:105-123`）。
- `viewportJson: null` 的值链路保持不变：修复没有修改 `toForm()`、schema 或 `toWrite()`；原回归仍验证编辑跟随浏览器配置后 PUT payload 为 `viewportJson: null`（`ProfileFormDialog.test.tsx:134-141`）。
- 修复对 `EnvironmentFields` 的行为变更仅限视口错误呈现、焦点标记及在用户切换视口模式/预设时清除旧 `viewportMode` 服务端错误。语言、时区、色彩模式、人类行为预设和 User Agent 的控制器及值转换未改变；指定 `EnvironmentFields` 回归全部通过。

## 修复 diff 评估

`d829c6f` 的父提交精确为 `2b7e000`。该提交只修改 `EnvironmentFields.tsx`、`ProfileFormDialog.tsx` 和 `ProfileFormDialog.test.tsx`，共 31 行新增、6 行删除；`git diff --check 2b7e000..d829c6f` 通过。新增的 `focusSelectors` 只覆盖复合视口控件，其他字段继续使用原有具名控件聚焦路径；`clearErrors('viewportMode')` 也只清除本次映射的视口服务端错误，没有清除其他环境字段错误。

## 验证结果

在 `d829c6f` 的独立 `git archive` 快照中运行，以隔离当前 Task 10/12 和其他未提交工作区改动：

```text
ProfileFormDialog.test.tsx + EnvironmentFields.test.tsx：2 files / 15 tests passed
TypeScript：npm run typecheck（tsc --noEmit）通过
git diff --check 2b7e000..d829c6f：通过
```

原审查唯一 P2 已修复，可以按 Task 9 的复审门禁继续后续流程。
