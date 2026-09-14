# Studio 语音请求交付

日期：2026-09-14；状态：confirmed（有界前端切片）。依据：冻结WebRPA语音请求、当前保留节点清单、真实本地HTTP/SSE及原生浏览器操作。

语音改为稳定请求领取/结果确认；复用脚本的有限命令确认机制，错误及过期不重放。发布Pydantic/OpenAPI合同，Mock仅模拟服务，不增加真实自动化后端。默认值来自配置，显式非法值拒绝，0音量保留。正常成功不调用全局cancel，停止由本请求负责。

普通断流时手动connect复用原Socket的重连与游标，保留朗读和Worker；更换地址执行disconnect清理。真实sidecar重启新epoch仍未解决。

专项63项、全量157文件1884项、后端19项、脚本21项及类型/lint/OpenAPI通过；原生SpeechSynthesis零音量在08:20:36完成回传。证据及边界见docs/migration/studio-frontend-completion/speech-request-validation.md。F0–F6不标整体完成，继续代码编辑器配套和服务缺口。
