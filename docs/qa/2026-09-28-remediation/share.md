# SEC-01 / SEC-02 / FUNC-01 共享边界修复

日期：2026-09-28；状态：本机定向自动与真实 HTTP 验收 confirmed；Windows 实机 pending。

根因：静态 GET/继承 HEAD 绕过专用下载检查；重名上传在初次校验之后用 wb 打开新路径；Content-Length 短读仍解析落盘；preview 引用未迁入模块。当前源码与历史审计相同，修复前21项检查中16失败、5通过，见 share-before.xml/log。

最终行为：所有文件读取/列表走 ShareDirectory；单文件共享只能 GET/HEAD 指定文件，不能写或读同目录其他文件。URL 仅解码一次，拒绝相对逃逸、Windows盘符/ADS/设备名、反斜杠、NUL及链接。普通文件、中文/空格、query、Range、HEAD仍可用。为统一平台边界，共享目录内的符号链接与junction均不遍历，即使目标在根目录内；用户可以直接共享其目标目录。

上传先收全请求并验证结束边界，再在已打开的目标目录内以O_EXCL排他创建；冲突重选名称，响应返回实际名称。不完整请求没有文件；写入失败清理当前新建文件，成功写入不因响应丢失回滚。POSIX路径逐段用dir_fd/O_NOFOLLOW；Windows使用既有pywin32持有不允许删除共享的目录句柄，拒绝reparse point，再排他创建，不使用存在性检查决定创建。目录被替换的真实故障注入证明不会写到链接指向的外部目录。mkdir/delete也复用边界。

媒体缩略图读取安全打开的文件，复制到私有临时目录后交给ffmpeg；取消了全局路径缓存的再次打开。文档预览端点返回415与明确不支持提示，页面同步提示下载；原有图片/音频/视频/文本下载预览仍保留，没有伪造Office渲染。

验证：test_share_file_boundaries.py 24项实际loopback HTTP/磁盘检查，加网络共享host/executor 6项，共30 passed（share-after.xml/log）。额外故障注入只更改写入失败时机/真实目录替换，没有Fake外部成功响应。Ruff与该新增适配器mypy通过。用户业务文件、共享VM、既有服务未动。最终全量与打包验收待总任务稳定后执行。

平台实现依据：[Python os的dir_fd与排他打开](https://docs.python.org/3.11/library/os.html)、[Windows CreateFile与共享删除/重解析语义](https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilea)。Windows分支未在本机执行，不冒称跨平台通过。

改动：infrastructure/sharing/file_share.py、paths.py、file_share_page.py；tests/integration/test_share_file_boundaries.py。提交以Git日志中本切片为准。
