# 最终两项配置修复的原生验收

日期：2026-09-28；状态：confirmed；置信度：高，仅限本节明确操作。
源码 c2367a17；包身份见 provenance.json。首应用 PID 29039，完整退出后重启 PID 30739；第二会话 ../native-session-oa0ENH。

## 真实数据与方法

native-final-fixture.mjs 只在本任务专属工作区，通过生产 API 新建表、字段、记录、工作流和自动化。记录保存本仓库实际 README.md 的路径、字节数及 SHA256（fixture.json 可复核），静态 recordTargets 使用 API 返回的完整真实 RecordRef，包含项目、表、数据代次与类型化记录键。没有数据库写入或外部成功响应替身。
之后所有选择、编辑、保存、退出和重新打开都由原生 CUA 完成；native-evidence.mjs 仅只读采集页面文本与截图，SQLite 仅 mode=ro 检查。API 没有在 UI 保存后补写修正结果。

## 两个验收场景

1. 静态目标：打开 End 后准确显示真实 RecordRef 数组；只修改节点备注为“静态目标保留验证”并保存。static-target-preserved-sqlite.json 确认 revision2 的数组逐项等于原 API 返回值。随后原生点击“清空记录目标”，保存后 native-saved-sqlite.json 确认 revision3 的内层 recordTargets 为 []，没有转换为 JSON 字符串。
2. 子流程：有效 nested.isSubflow=true、外层 false 的分组可选，名字为内层“嵌套有效名”；nested=false、外层 true 的陈旧分组未列出。原生选择后配置面板和节点显示有效名；revision3 持久 subflowGroupId=nested-definition/subflowName=嵌套有效名，外层陈旧字段仍保持，未拍平或静默迁移文档。

完整退出首应用后，从主页面重新进入相同自动化及 Studio。第二会话 restarted-subflow/restarted-end 截图与文本确认有效子流程、清空目标、备注和环境名均保持。restarted-sqlite.json 确认 revision3 文档逐字节解析值与保存时一致，重开未额外改写。

两会话 owned-before-quit.json 与 exit-check.json 分别记录7个归属进程的 PID/启动身份；正常退出后均无残留。退出不是仅凭监听端口消失判断。

## 边界

此工作流用于配置往返，未启动执行；静态记录存在不代表当前 Task 已取得写租约。不会用本场景证明无授权目标可被关联。真实项目数据写回、状态、End关联及登录复用由独立生产 worker/浏览器场景证明；原生 End 实际环境名称一致证据见 ../native-session-LCCIyR/README.md（e49144f2），最新版完整包链另见 packaged-end-v4。

单元测试两处旧形状夹具 Minor 仍保留；本场景使用真实生产 RecordRef 独立补足实际显示/保存验收，不将组件 mock 计为业务成功。无跨平台或人工检查点恢复证明。
