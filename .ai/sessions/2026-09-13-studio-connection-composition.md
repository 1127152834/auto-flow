# Studio 连接显式装配

日期：2026-09-13；状态：局部 implemented/verified。

transport 移除隐式 Mock 导入。Studio 入口与测试入口明确选择 Mock；API 调用时读取 origin。注入真实 HTTP adapter 后相同 service 和 SSE consumer 通过。9 新用例；完整前端 1,146 用例及类型/lint/构建通过；浏览器重开旧变量草稿通过。

仍需完成鉴权、全部服务 DTO、生命周期及前端交付矩阵。切换连接前须结束旧事件客户端，连接装配函数本身不承担工作区切换。下一切片处理新建/打开/导入的保存、放弃、取消及响应竞态。
