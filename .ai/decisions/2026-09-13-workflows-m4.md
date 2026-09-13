# M4 结构化控制流

日期：2026-09-13；状态：confirmed；来源：用户批准实施计划。

采用配对控制块、可视化条件、count/foreach/while与只读局部变量；网页条件复用M3。文档v2兼容v1读取；结构化编译及application顺序调度，不展开循环、不引入任意DAG调度。每次调度独立executionId，沿用seq/SSE；产物从运行大JSON移入独立索引并分页，历史文件不移动。具体契约、验收与限制以正式M4规格为准。子流程/重试/Debug/录制仍未完成。


落地补充：typed literal 的可选 valueType 记录表单预期类型，使未完成数字/JSON仍可手动保存；输入有效性由正式域规则判断。实时日志小批合并，尺寸与连接点测量只在 React Flow 会话维护。高频日志输出停止后排空但不提交，防止管道堵塞清理。结果按执行标识判断本轮状态，不能由同一 nodeId 早前成功推断本轮成功。依据与证据见 ../../docs/migration/automation-studio-m4-validation.md。
