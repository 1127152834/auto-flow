# 输入路径工具请求保护

按F2/F3继续推进。InputPromptDialog复用systemApi并保护请求身份/手工编辑/提交后的迟到路径，显示服务错误。源system_dialog.py取消使用success:false；在API仅对这两个接口精确映射，error不被吞掉。

新增18项，相关68项通过，类型/lint通过。未验收原生文件选择器，不将Mock路径视作真实文件。继续DebugBar请求状态与停止优先级，不需要用户再次授权。
