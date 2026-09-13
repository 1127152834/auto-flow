# M3 元素拾取与定位测试

状态：confirmed，2026-09-13 用户批准完整 M3 计划并要求实施。

专用可见临时会话，复用 Profile 参数但 headless=false，不改 Profile、不访问起始 URL、不继承或保存登录态。用户手动进入目标页面。每工作区一个会话，与运行原子互斥，清理后释放 Profile/内核锁。运行前确认关闭拾取会话；保存失败和离开取消保留会话。

六节点不扩容。五个元素动作新增可选 framePath:string[]，缺省主文档；嵌套/跨域 iframe 每层唯一，CSS 与 xpath=，共享节点预算，不回退主文档。整页/视口截图忽略 selector/framePath。支持开放 Shadow DOM；不声称能定位封闭内部。保存仍允许未完成稿。

拾取左键确认、Esc取消；拦截业务点击，预览后用户应用 selector+framePath 为一次撤销。绑定工作区/文档/节点/原定位值，过期结果不覆盖草稿。候选按 ID、属性、类/祖先、位置路径生成，以真实执行定位语义验证唯一且同一元素。导航和框架失效取消在途请求。

定位测试仅匹配、高亮、摘要，不操作元素。10秒预算、匹配数量准确、首个可见性，最多高亮前100项3秒。声明初值引用解析一次，不用历史输出。会话内存轮询500ms拾取/1s状态，稳定请求ID幂等、非消费结果。同服务重连可恢复，服务重启不恢复浏览器。

接口前缀 /api/v1/workflows/inspection-sessions：POST/GET集合，GET/{id}，POST/{id}/page，POST/{id}/picks，GET/{id}/picks/{requestId}，POST/{id}/picks/{requestId}/cancel，POST/{id}/test-selector，POST/{id}/close。静态路由在文档ID之前。复用鉴权、错误、停写、OpenAPI生成。

不含录制、Debug、自愈、批量提取、持久登录态。临时会话不入运行历史、不增数据库表。验收必须真实拾取→保存→独立运行；开发/构建/冻结/打包及平台结果分别记录。
