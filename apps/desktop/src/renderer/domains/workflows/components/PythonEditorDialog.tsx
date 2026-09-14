// Source: WebRPA@5ccb900e, components/workflow/PythonEditorDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { registerEditorCompletions } from '../lib/editorCompletions'
import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import Editor, { type Monaco, loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import type { editor } from 'monaco-editor'
import { X, RotateCcw, Copy, Check, Loader2 } from 'lucide-react'
import { Button } from './controls/button'
import { AICodeAssistant } from './AICodeAssistant'

// 配置 Monaco Editor 使用本地包，避免从 CDN 加载
loader.config({ monaco })

// 预加载 Monaco Editor（只加载一次）
let monacoPreloaded = false
if (!monacoPreloaded) {
  loader.init().then(() => {
    monacoPreloaded = true
  }).catch((error) => {
    console.error('[PythonEditorDialog] Monaco 预加载失败:', error)
  })
}

interface PythonEditorDialogProps {
  isOpen: boolean
  code: string
  onClose: () => void
  onSave: (code: string) => void
}

const DEFAULT_CODE = `# ========================================
# WebRPA Python脚本模块 - 使用教程
# ========================================

# 一、访问工作流变量
# ----------------------------------------
# 系统自动注入所有工作流变量，可以直接通过 vars.变量名 访问
# 例如：
# - vars.username  # 获取 username 变量
# - vars.count     # 获取 count 变量
# - vars.items     # 获取 items 列表变量
# - vars.user_info # 获取 user_info 字典变量

# 如果变量不存在，可以使用 get() 方法提供默认值
# username = vars.get('username', '默认用户')
# age = vars.get('age', 0)

# 查看所有可用变量
print(f"所有可用变量: {list(vars.keys())}")


# 二、编写你的业务逻辑
# ----------------------------------------
# 示例1：简单计算
result = 1 + 1
print(f"计算结果: {result}")

# 示例2：使用工作流变量
# 假设工作流中有一个名为 'name' 的变量
if 'name' in vars.keys():
    name = vars.name  # 或者 vars.get('name')
    greeting = f"你好, {name}!"
    print(greeting)

# 示例3：处理列表数据
# 假设工作流中有一个名为 'numbers' 的列表变量
if 'numbers' in vars.keys():
    numbers = vars.numbers
    total = sum(numbers)
    print(f"数字总和: {total}")


# 三、返回结果给工作流
# ----------------------------------------
# 直接使用 return 返回结果即可
# 支持任意类型：字符串、数字、列表、字典等

# 示例：返回字典
output_data = {
    'status': 'success',
    'result': result,
    'message': '处理完成'
}

# 直接返回（系统会自动保存到指定的返回值变量）
return output_data


# ========================================
# 使用提示
# ========================================
# 1. 访问变量：直接使用 vars.变量名 或 vars.get('变量名', 默认值)
#    系统会自动注入所有工作流变量，无需手动配置
#
# 2. 返回值：直接使用 return 返回任意类型的数据
#    在配置面板的"返回值变量"中指定接收变量名
#    例如：result，然后可以用 {result} 引用
#
# 3. 标准输出：print() 的内容会保存到"标准输出变量"（如果配置了）
#
# 4. 内置库：可以使用Python 3.13的所有标准库
#    以及WebRPA内置的第三方库（requests、pandas等）
#
# 5. 简单易用：就像写普通Python脚本一样，无需复杂配置
# ========================================
`

export function PythonEditorDialog({ isOpen, code, onClose, onSave }: PythonEditorDialogProps) {
  const [currentCode, setCurrentCode] = useState(code || DEFAULT_CODE)
  const [copied, setCopied] = useState(false)
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<Monaco | null>(null)

  // 同步外部 code 变化
  useEffect(() => {
    if (isOpen) {
      setCurrentCode(code || DEFAULT_CODE)
    }
  }, [isOpen, code])

  // 配置 Monaco Editor
  const handleEditorDidMount = (editor: editor.IStandaloneCodeEditor, monaco: Monaco) => {
    editorRef.current = editor
    monacoRef.current = monaco

    // 注册自定义补全提供器
    registerEditorCompletions(editor, monaco, 'python', {
       
      provideCompletionItems: (model: any, position: any) => {
        const word = model.getWordUntilPosition(position)
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        }

         
        const suggestions: any[] = []

        // 常用代码片段
        const snippets = [
          {
            label: 'main',
            insertText: `def main():\n    """主函数"""\n    $0\n    return 0\n\nif __name__ == "__main__":\n    exit(main())`,
            detail: '主函数模板',
          },
          {
            label: 'for-loop',
            insertText: `for \${1:item} in \${2:items}:\n    $0`,
            detail: 'for 循环',
          },
          {
            label: 'while-loop',
            insertText: `while \${1:condition}:\n    $0`,
            detail: 'while 循环',
          },
          {
            label: 'if-else',
            insertText: `if \${1:condition}:\n    $0\nelse:\n    pass`,
            detail: 'if-else 语句',
          },
          {
            label: 'try-except',
            insertText: `try:\n    $0\nexcept Exception as e:\n    print(f"错误: {e}")`,
            detail: '异常处理',
          },
          {
            label: 'read-file',
            insertText: `with open('\${1:filename}', 'r', encoding='utf-8') as f:\n    content = f.read()\n    $0`,
            detail: '读取文件',
          },
          {
            label: 'write-file',
            insertText: `with open('\${1:filename}', 'w', encoding='utf-8') as f:\n    f.write(\${2:content})\n    $0`,
            detail: '写入文件',
          },
          {
            label: 'list-comprehension',
            insertText: `[\${1:item} for \${1:item} in \${2:items} if \${3:condition}]`,
            detail: '列表推导式',
          },
          {
            label: 'dict-comprehension',
            insertText: `{\${1:key}: \${2:value} for \${1:key}, \${2:value} in \${3:items}}`,
            detail: '字典推导式',
          },
          {
            label: 'class',
            insertText: `class \${1:ClassName}:\n    def __init__(self):\n        $0\n        pass`,
            detail: '类定义',
          },
        ]

        snippets.forEach(snippet => {
          suggestions.push({
            label: snippet.label,
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: snippet.insertText,
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            detail: snippet.detail,
            range,
          })
        })

        return { suggestions }
      },
    })

    // 聚焦编辑器
    editor.focus()
  }

  // 重置代码
  const handleReset = () => {
    setCurrentCode(DEFAULT_CODE)
  }

  // 复制代码
  const handleCopy = async () => {
    await navigator.clipboard.writeText(currentCode)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // 保存并关闭
  const handleSave = () => {
    onSave(currentCode)
    onClose()
  }

  if (!isOpen) return null

  // 阻止键盘事件冒泡到外层（如 React Flow）
  const handleKeyDown = (e: React.KeyboardEvent) => {
    e.stopPropagation()
  }

  // 计算行数
  const lineCount = currentCode.split('\n').length

  return createPortal(
    <div 
      className="fixed inset-0 flex items-center justify-center bg-black/40 animate-fade-in"
      style={{ zIndex: 2147483646 }}
      onKeyDown={handleKeyDown}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl flex flex-col w-[900px] h-[700px] max-w-[95vw] max-h-[90vh] overflow-hidden animate-scale-in"
        onKeyDown={handleKeyDown}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50 rounded-t-lg">
          <div className="flex items-center gap-3">
            <h3 className="font-medium">Python 代码编辑器</h3>
            <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
              {lineCount} 行
            </span>
          </div>
          <Button variant="tonal-danger" size="icon" onClick={onClose} title="关闭">

            <X className="w-4 h-4" />

          </Button>
        </div>

        {/* 工具栏 */}
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-gray-50">
          <AICodeAssistant
            language="python"
            currentCode={currentCode}
            onCodeGenerated={(code) => setCurrentCode(code)}
            variableReferenceFormat="vars.变量名"
            moduleType="python_script"
          />
          <Button size="sm" variant="tonal-success" onClick={handleReset}>
            <RotateCcw className="w-4 h-4 mr-1" />
            重置
          </Button>
          <Button size="sm" variant="tonal-success" onClick={handleCopy}>
            {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
            {copied ? '已复制' : '复制'}
          </Button>
          <div className="flex-1" />
          <span className="text-xs text-gray-500">
            提示：使用 <kbd className="px-1 bg-gray-200 rounded">Ctrl+Space</kbd> 触发代码补全
          </span>
        </div>

        {/* 编辑器区域 */}
        <div className="flex-1 flex min-h-0">
          {/* 代码编辑器 */}
          <div className="flex-1 border-r">
            <Editor
              height="100%"
              defaultLanguage="python"
              value={currentCode}
              onChange={(value) => setCurrentCode(value || '')}
              onMount={handleEditorDidMount}
              theme="vs-light"
              loading={
                <div className="flex items-center justify-center h-full gap-2 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>加载编辑器...</span>
                </div>
              }
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 4,
                wordWrap: 'on',
                suggestOnTriggerCharacters: true,
                quickSuggestions: true,
                parameterHints: { enabled: true },
                folding: true,
                bracketPairColorization: { enabled: true },
              }}
            />
          </div>

          {/* 右侧面板 */}
          <div className="w-72 flex flex-col bg-gray-50">
            {/* 使用说明 */}
            <div className="p-3 border-b">
              <h4 className="text-sm font-medium mb-2">使用说明</h4>
              <div className="text-xs text-gray-600 space-y-2">
                <p>• 默认使用 WebRPA 内置的 Python 3.13</p>
                <p>• 可以在配置中选择使用本地 Python</p>
                <p>• 支持命令行参数传递</p>
                <p>• 标准输出和错误可保存到变量</p>
                <p>• 返回码 0 表示成功</p>
              </div>
            </div>

            {/* 常用模块 */}
            <div className="p-3 border-b">
              <h4 className="text-sm font-medium mb-2">常用模块</h4>
              <div className="space-y-1">
                {[
                  { name: 'sys', desc: '系统相关' },
                  { name: 'os', desc: '操作系统接口' },
                  { name: 'json', desc: 'JSON 处理' },
                  { name: 'requests', desc: 'HTTP 请求' },
                  { name: 'pandas', desc: '数据分析' },
                  { name: 'openpyxl', desc: 'Excel 操作' },
                ].map(mod => (
                  <div
                    key={mod.name}
                    className="flex items-center justify-between text-xs bg-white px-2 py-1 rounded border cursor-pointer hover:bg-blue-50"
                    onClick={() => {
                      editorRef.current?.trigger('keyboard', 'type', { text: `import ${mod.name}\n` })
                    }}
                    title="点击插入"
                  >
                    <span className="font-mono text-blue-600">{mod.name}</span>
                    <span className="text-gray-400">{mod.desc}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 代码片段 */}
            <div className="flex-1 p-3 overflow-auto">
              <h4 className="text-sm font-medium mb-2">代码片段</h4>
              <div className="space-y-1 text-xs">
                <p className="text-gray-500">输入以下关键词触发补全：</p>
                <ul className="space-y-1 text-gray-600">
                  <li>• <code className="bg-gray-200 px-1 rounded">main</code> - 主函数模板</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">for</code> - for 循环</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">while</code> - while 循环</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">if</code> - if-else 语句</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">try</code> - 异常处理</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">read-file</code> - 读取文件</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">write-file</code> - 写入文件</li>
                  <li>• <code className="bg-gray-200 px-1 rounded">class</code> - 类定义</li>
                </ul>
              </div>
            </div>

            {/* 快捷键提示 */}
            <div className="p-3 border-t text-xs text-gray-500 space-y-1">
              <p><kbd className="px-1 bg-gray-200 rounded">Ctrl+Space</kbd> 触发补全</p>
              <p><kbd className="px-1 bg-gray-200 rounded">Ctrl+/</kbd> 注释/取消注释</p>
              <p><kbd className="px-1 bg-gray-200 rounded">Ctrl+Z</kbd> 撤销</p>
            </div>
          </div>
        </div>

        {/* 底部 */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t bg-gray-50 rounded-b-lg">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button variant="success" onClick={handleSave}>
            保存
          </Button>
        </div>
      </div>
    </div>,
    document.body
  )
}
