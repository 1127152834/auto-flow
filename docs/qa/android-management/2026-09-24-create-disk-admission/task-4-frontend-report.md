# Task 4 前端实现报告

日期：2026-09-24。状态：前端实现完成，等待根任务统一 build 与隔离应用验收。

## 实现

- `CreateDeviceForm`、`CreateInstances`、`BackupPanel` 恢复新实例、`AndroidPage` 保留数据恢复均增加默认未选的磁盘未知估计确认，传递严格布尔 `allowUnknownDiskEstimate`。
- 单/批量创建的名称、配置、目标等编辑会清空确认；源设备或配置快照中的确认不会继承。备份目标切换也会清空先前目标的确认。
- 请求进行中及结果未知时冻结确认和请求参数；原编号重试复用原布尔值。已知磁盘拒绝释放原请求，保留真实错误提示。保留数据恢复未知时不能关闭对话框，仍可按原编号重试。
- 只改前端域文件和本报告；生成 API 类型由后端实现者更新，未在本提交中暂存。

## RED → GREEN

- RED 命令：`./node_modules/.bin/vitest run --environment jsdom apps/desktop/src/renderer/domains/android/tests/Management.test.tsx apps/desktop/src/renderer/domains/android/tests/AndroidPage.test.tsx apps/desktop/src/renderer/domains/android/tests/ManagementTools.test.tsx -t 'disk|retained-volume restoration|defaults to one persistent|describes private local'`。结果：6 failed，均因缺少“最终磁盘占用无法可靠估计”复选框；无编译或环境错误。
- GREEN 命令：同上，补入 `current restore confirmation` 选择器并 `--reporter=dot`。结果：6 passed、1 failed；剩余失败是测试查询先于异步备份目录加载，改为 `findByRole` 后相关 3 文件 87 passed。
- 第二轮 RED：`... AndroidPage.test.tsx -t 'keeps the retained restore confirmation'`，因未知响应后“取消”按钮仍可用而失败；冻结原请求后 1 passed。
- 第三轮 RED：`... ManagementTools.test.tsx -t 'does not carry disk confirmation'`，使用挂起的恢复请求证实切换目标后上一备份确认仍保持勾选；清空后 1 passed。

## 验证

- `./node_modules/.bin/vitest run --environment jsdom apps/desktop/src/renderer/domains/android/tests --reporter=dot`：14 files、193 tests passed。
- `./node_modules/.bin/eslint apps/desktop/src/renderer/domains/android`：exit 0，无输出。
- `./node_modules/.bin/tsc --noEmit -p apps/desktop/tsconfig.json`：exit 0，无输出。
- 末次测试调整后 `./node_modules/.bin/vitest run --environment jsdom apps/desktop/src/renderer/domains/android/tests/ManagementTools.test.tsx --reporter=dot`：47 passed。
- `git diff --check`：exit 0。

## 自审与风险

- 逐项核对四入口默认 false、源确认不继承、请求冻结、配置变化重置及已知拒绝后的重试。保留了原有请求 ref、会话和 generation 守卫；没有加入依赖或重构页面。
- 原组件 `BackupPanel` 已是整段 JSX 长行，本次仅在恢复记录上增加原生复选框；后续若调整布局可单独整理，不纳入本切片。
- 本任务没有运行 build 或真实 Android 操作；根任务负责统一构建及隔离工作区验收。
