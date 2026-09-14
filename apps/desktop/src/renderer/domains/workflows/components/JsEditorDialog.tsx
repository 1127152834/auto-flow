// Source: WebRPA@5ccb900e, components/workflow/JsEditorDialog.tsx; see SOURCE.md for license and adaptation boundaries.
import { registerEditorCompletions } from '../lib/editorCompletions'
import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import Editor, { type Monaco, loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import type { editor } from 'monaco-editor'
import { X, Play, RotateCcw, Copy, Check, Loader2 } from 'lucide-react'
import { Button } from './controls/button'
import { useWorkflowStore } from '../editor-store'
import { AICodeAssistant } from './AICodeAssistant'
import { runJsScript } from '../lib/runJsScript'

// 预加载 Monaco Editor（只加载一次）
let monacoPreloaded = false
if (!monacoPreloaded) {
  loader.config({ monaco })
  loader.init().then(() => {
    monacoPreloaded = true
  }).catch((error) => {
    console.error('[JsEditorDialog] Monaco 预加载失败:', error)
  })
}

interface JsEditorDialogProps {
  isOpen: boolean
  code: string
  onClose: () => void
  onSave: (code: string) => void
}

const DEFAULT_CODE = `// 自定义 JavaScript 脚本
// 通过 vars 对象访问工作流中的变量、列表、字典
// 例如: vars.myVar, vars.myList, vars.myDict

function main(vars) {
  // 在这里编写你的代码
  
  // 示例：字符串处理
  // const text = vars.inputText || '';
  // return text.toUpperCase();
  
  // 示例：列表过滤
  // const list = vars.myList || [];
  // return list.filter(item => item > 10);
  
  // 示例：数学计算
  // return vars.a + vars.b;
  
  return null;
}

// main 函数的返回值将存储到指定的变量中
`

export function JsEditorDialog({ isOpen, code, onClose, onSave }: JsEditorDialogProps) {
  const [currentCode, setCurrentCode] = useState(code || DEFAULT_CODE)
  const [testResult, setTestResult] = useState<{ success: boolean; result?: string; error?: string } | null>(null)
  const [copied, setCopied] = useState(false)
  const [testing, setTesting] = useState(false)
  const testController = useRef<AbortController | null>(null)
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<Monaco | null>(null)
  
  const variables = useWorkflowStore((state) => state.variables)
  const nodes = useWorkflowStore((state) => state.nodes)

  // 同步外部 code 变化
  useEffect(() => {
    if (isOpen) {
      setCurrentCode(code || DEFAULT_CODE)
      setTestResult(null)
    }
  }, [isOpen, code])

  useEffect(() => {
    setTestResult(null)
    setTesting(false)
    return () => { testController.current?.abort(); testController.current = null }
  }, [isOpen, currentCode])

  const handleClose = () => {
    testController.current?.abort()
    testController.current = null
    setTesting(false)
    onClose()
  }

  // 配置 Monaco Editor
  const handleEditorDidMount = (editor: editor.IStandaloneCodeEditor, monaco: Monaco) => {
    editorRef.current = editor
    monacoRef.current = monaco

    // 收集所有变量名用于自动补全
    const varNames = new Set<string>()
    variables.forEach(v => varNames.add(v.name))
    nodes.forEach(node => {
      const data = node.data as Record<string, unknown>
      const fields = ['variableName', 'resultVariable', 'itemVariable', 'indexVariable']
      fields.forEach(field => {
        const val = data[field]
        if (typeof val === 'string' && val.trim()) {
          varNames.add(val)
        }
      })
    })

    // 注册自定义补全提供器
    registerEditorCompletions(editor, monaco, 'javascript', {
       
      provideCompletionItems: (model: any, position: any) => {
        const word = model.getWordUntilPosition(position)
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        }

         
        const suggestions: any[] = []

        // vars 对象补全
        suggestions.push({
          label: 'vars',
          kind: monaco.languages.CompletionItemKind.Variable,
          insertText: 'vars',
          detail: '工作流变量对象',
          documentation: '包含所有工作流变量的对象，如 vars.myVar',
          range,
        })

        // 变量名补全 (vars.xxx)
        varNames.forEach(name => {
          suggestions.push({
            label: `vars.${name}`,
            kind: monaco.languages.CompletionItemKind.Property,
            insertText: `vars.${name}`,
            detail: '工作流变量',
            range,
          })
        })

        // main 函数模板
        suggestions.push({
          label: 'main',
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: `function main(vars) {\n  $0\n  return null;\n}`,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          detail: '主函数模板',
          documentation: '定义 main 函数，接收 vars 参数，返回值将存入变量',
          range,
        })

        // 常用代码片段
        const snippets = [
          {
            label: 'filter-list',
            insertText: `const filtered = vars.\${1:listName}.filter(item => \${2:item > 0});\nreturn filtered;`,
            detail: '过滤列表',
          },
          {
            label: 'map-list',
            insertText: `const mapped = vars.\${1:listName}.map(item => \${2:item * 2});\nreturn mapped;`,
            detail: '映射列表',
          },
          {
            label: 'reduce-list',
            insertText: `const sum = vars.\${1:listName}.reduce((acc, item) => acc + item, 0);\nreturn sum;`,
            detail: '归约列表',
          },
          {
            label: 'object-keys',
            insertText: `const keys = Object.keys(vars.\${1:dictName});\nreturn keys;`,
            detail: '获取对象键',
          },
          {
            label: 'object-values',
            insertText: `const values = Object.values(vars.\${1:dictName});\nreturn values;`,
            detail: '获取对象值',
          },
          {
            label: 'string-split',
            insertText: `const parts = vars.\${1:text}.split('\${2:,}');\nreturn parts;`,
            detail: '分割字符串',
          },
          {
            label: 'string-replace',
            insertText: `const result = vars.\${1:text}.replace(/\${2:pattern}/g, '\${3:replacement}');\nreturn result;`,
            detail: '替换字符串',
          },
          {
            label: 'json-parse',
            insertText: `const obj = JSON.parse(vars.\${1:jsonString});\nreturn obj;`,
            detail: '解析JSON',
          },
          {
            label: 'json-stringify',
            insertText: `const str = JSON.stringify(vars.\${1:object}, null, 2);\nreturn str;`,
            detail: '序列化JSON',
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

  // 测试运行代码
  const handleTest = async () => {
    if (testController.current) return
    const controller = new AbortController()
    testController.current = controller
    setTesting(true)
    setTestResult(null)
    try {
      const testVars = Object.fromEntries(variables.filter(variable => variable.value !== undefined).map(variable => [variable.name, variable.value]))
      const result = await runJsScript(currentCode, testVars, controller.signal)
      if (controller.signal.aborted || testController.current !== controller) return
      setTestResult(result.success ? { success: true, result: JSON.stringify(result.result, null, 2) } : { success: false, error: result.error || '脚本测试失败' })
    } catch (error) {
      if (!controller.signal.aborted && testController.current === controller) {
        setTestResult({ success: false, error: error instanceof Error ? error.message : String(error) })
      }
    } finally {
      if (testController.current === controller) { testController.current = null; setTesting(false) }
    }
  }

  // 重置代码
  const handleReset = () => {
    setCurrentCode(DEFAULT_CODE)
    setTestResult(null)
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
    handleClose()
  }

  if (!isOpen) return null

  // 阻止键盘事件冒泡到外层（如 React Flow）
  const handleKeyDown = (e: React.KeyboardEvent) => {
    e.stopPropagation()
  }

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
            <h3 className="font-medium">JavaScript 代码编辑器</h3>
            <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
              {variables.length} 个变量可用
            </span>
          </div>
          <Button variant="tonal-danger" size="icon" onClick={handleClose} title="关闭">

            <X className="w-4 h-4" />

          </Button>
        </div>

        {/* 工具栏 */}
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-gray-50">
          <AICodeAssistant
            language="javascript"
            currentCode={currentCode}
            onCodeGenerated={(code) => setCurrentCode(code)}
            variableReferenceFormat="vars.变量名"
            moduleType="js_script"
          />
          <Button size="sm" variant="tonal-success" onClick={() => void handleTest()} disabled={testing}>
            <Play className="w-4 h-4 mr-1" />
            {testing ? '正在测试' : '测试运行'}
          </Button>
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
            提示：输入 <kbd className="px-1 bg-gray-200 rounded">vars.</kbd> 查看变量补全
          </span>
        </div>

        {/* 编辑器区域 */}
        <div className="flex-1 flex min-h-0">
          {/* 代码编辑器 */}
          <div className="flex-1 border-r">
            <Editor
              height="100%"
              defaultLanguage="javascript"
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
                tabSize: 2,
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
            {/* 变量列表 */}
            <div className="p-3 border-b">
              <h4 className="text-sm font-medium mb-2">可用变量</h4>
              <div className="max-h-40 overflow-auto space-y-1">
                {variables.length === 0 ? (
                  <p className="text-xs text-gray-500">暂无变量</p>
                ) : (
                  variables.map(v => (
                    <div
                      key={v.name}
                      className="flex items-center justify-between text-xs bg-white px-2 py-1 rounded border cursor-pointer hover:bg-blue-50"
                      onClick={() => {
                        editorRef.current?.trigger('keyboard', 'type', { text: `vars.${v.name}` })
                      }}
                      title="点击插入"
                    >
                      <span className="font-mono text-blue-600">vars.{v.name}</span>
                      <span className="text-gray-400">{v.type}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 测试结果 */}
            <div className="flex-1 p-3 overflow-auto">
              <h4 className="text-sm font-medium mb-2">测试结果</h4>
              {testResult ? (
                <div
                  className={`p-2 rounded text-xs font-mono whitespace-pre-wrap ${
                    testResult.success
                      ? 'bg-green-50 border border-green-200 text-green-800'
                      : 'bg-red-50 border border-red-200 text-red-800'
                  }`}
                >
                  {testResult.success ? testResult.result : `错误: ${testResult.error}`}
                </div>
              ) : (
                <p className="text-xs text-gray-500">点击"测试运行"查看结果</p>
              )}
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
          <Button variant="outline" onClick={handleClose}>
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
