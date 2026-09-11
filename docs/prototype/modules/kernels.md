# 内核管理原型

## 主流程
已安装区展示版本、平台、架构、路径和状态；可用版本区展示 release 卡片。安装按钮触发下载任务，任务卡显示下载/校验/安装阶段。

## 异步任务
任务状态：queued、downloading、verifying、installing、completed、failed、cancelled。进度条使用 300ms linear，取消需要确认；失败显示原因和“重试”。

## 平台行为
显示统一的人类可读状态，实际路径、权限和可执行文件检查由后端返回。禁止 renderer 自己拼接路径。
