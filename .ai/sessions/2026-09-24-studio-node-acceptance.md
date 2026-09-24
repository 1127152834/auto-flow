# 2026-09-24 Studio 全节点验收检查点

状态：confirmed（测试实际结果）；不是整体完成。

- 仓库 `/Users/zhangtiancheng/Documents/projects/autoflow`，分支 `codex/project-management-pm9`，起点dd93a80b。保留原有validation/implementation/component-tools及其它脏文件，本次不提交它们。
- 用户要求快速完成所有节点验收。范围仍为213，14通知排除，204已有验收、9未全部实机验收。本次只改验收脚本/证据/台账，没有生产业务修改。
- 全节点族 unit+differential 1462 passed/165.92s；剩余9专项52 passed/18.90s；映射/范围77 passed/1.78s；registry12 passed/0.44s。不可累加重叠测试制造覆盖。
- 热键和鼠标CUA输入未被真实pynput全局监听器接收；独立25秒只计数诊断0事件，未记录用户按键文本。实际正向超时保留，不改执行器绕过。
- 图像直接生产执行器真实ImageGrab/OpenCV成功、0.9825196862220764及变量一致；正式窗口正向4次因屏幕目标未满足而超时，原因仍需实机配合确认，不能核销。
- 原脚本新增AUTOFLOW_NATIVE_TRIGGER及显式NEGATIVE_ONLY部分验证模式，正向成功断言保留。三节点正式包UI配置、保存、正常关闭和重开、实际2秒超时、UI停止通过；鼠标直接检查worker PID退出。
- Windows4节点没有环境：shutdown_system/lock_screen/sound_trigger/printer_call。摄像头2节点缺真实目标配合。用户输入问题已发出，尚未回答；不重复授权、不安装不适用Linux KVM方案、不修改隐私权限。
- 证据唯一入口：docs/migration/studio-backend-migration/evidence/b6/native-acceptance-2026-09-24/README.md。capabilities原639槽位保留630通过、9待验收，gap与real-execution证据指向本次结果。
- 继续时先读该证据与当前git状态，不重新审计204已验收节点；环境具备后用现有脚本补正向和独有原生分支。项目集成大目标仍单独未完成。
