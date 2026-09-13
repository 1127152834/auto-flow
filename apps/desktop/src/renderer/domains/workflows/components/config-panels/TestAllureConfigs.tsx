// Source: WebRPA@5ccb900e, components/workflow/config-panels/TestAllureConfigs.tsx; see SOURCE.md for license and adaptation boundaries.
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { SelectNative as Select } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'
import { PathInput } from '../controls/path-input'
import { Checkbox } from '../controls/checkbox'

// Allure初始化配置
export function AllureInitConfig({ 
  data, 
  onChange 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="resultsDir">结果目录</Label>
        <PathInput
          value={(data.resultsDir as string) || './allure-results'}
          onChange={(v) => onChange('resultsDir', v)}
          placeholder="./allure-results"
        />
        <p className="text-xs text-muted-foreground">
          存储测试结果的目录路径，支持变量
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="testSuite">测试套件名称</Label>
        <VariableInput
          value={(data.testSuite as string) || '测试套件'}
          onChange={(v) => onChange('testSuite', v)}
          placeholder="测试套件"
        />
        <p className="text-xs text-muted-foreground">
          测试套件的名称，用于分组测试用例
        </p>
      </div>
      
      <div className="flex items-center space-x-2">
        <Checkbox
          id="clean"
          checked={(data.clean as boolean) ?? true}
          onCheckedChange={(checked) => onChange('clean', checked)}
        />
        <Label htmlFor="clean" className="cursor-pointer">
          清空已有结果
        </Label>
      </div>
      <p className="text-xs text-muted-foreground ml-6">
        初始化时是否删除结果目录中的旧文件
      </p>
    </>
  )
}

// 开始测试用例配置
export function AllureStartTestConfig({ 
  data, 
  onChange 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="name">测试用例名称</Label>
        <VariableInput
          value={(data.name as string) || '测试用例'}
          onChange={(v) => onChange('name', v)}
          placeholder="测试用例"
        />
        <p className="text-xs text-muted-foreground">
          测试用例的标题，支持变量
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="description">测试用例描述</Label>
        <VariableInput
          value={(data.description as string) || ''}
          onChange={(v) => onChange('description', v)}
          placeholder="描述测试用例的目的和预期结果"
          multiline
        />
        <p className="text-xs text-muted-foreground">
          详细描述测试用例的内容（可选）
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="severity">严重程度</Label>
        <Select
          id="severity"
          value={(data.severity as string) || 'normal'}
          onChange={(e) => onChange('severity', e.target.value)}
        >
          <option value="blocker">阻塞</option>
          <option value="critical">严重</option>
          <option value="normal">一般</option>
          <option value="minor">次要</option>
          <option value="trivial">轻微</option>
        </Select>
        <p className="text-xs text-muted-foreground">
          标记测试用例的重要程度
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="testId">测试用例ID</Label>
        <VariableInput
          value={(data.testId as string) || ''}
          onChange={(v) => onChange('testId', v)}
          placeholder="TC-001"
        />
        <p className="text-xs text-muted-foreground">
          用于追踪的测试用例ID（可选）
        </p>
      </div>
    </>
  )
}

// 添加测试步骤配置
export function AllureAddStepConfig({ 
  data, 
  onChange 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="name">步骤名称</Label>
        <VariableInput
          value={(data.name as string) || '测试步骤'}
          onChange={(v) => onChange('name', v)}
          placeholder="测试步骤"
        />
        <p className="text-xs text-muted-foreground">
          测试步骤的名称，支持变量
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="description">步骤描述</Label>
        <VariableInput
          value={(data.description as string) || ''}
          onChange={(v) => onChange('description', v)}
          placeholder="描述此步骤的具体操作"
          multiline
        />
        <p className="text-xs text-muted-foreground">
          详细描述步骤内容（可选）
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="status">步骤状态</Label>
        <Select
          id="status"
          value={(data.status as string) || 'passed'}
          onChange={(e) => onChange('status', e.target.value)}
        >
          <option value="passed">通过</option>
          <option value="failed">失败</option>
          <option value="skipped">跳过</option>
          <option value="broken">中断</option>
        </Select>
        <p className="text-xs text-muted-foreground">
          标记此步骤的执行状态
        </p>
      </div>
    </>
  )
}

// 添加附件配置
export function AllureAddAttachmentConfig({ 
  data, 
  onChange 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="filePath">文件路径</Label>
        <PathInput
          value={(data.filePath as string) || ''}
          onChange={(v) => onChange('filePath', v)}
          placeholder="C:/screenshots/test.png"
        />
        <p className="text-xs text-muted-foreground">
          要添加的附件文件路径，支持变量
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="name">附件名称</Label>
        <VariableInput
          value={(data.name as string) || ''}
          onChange={(v) => onChange('name', v)}
          placeholder="截图"
        />
        <p className="text-xs text-muted-foreground">
          附件在报告中显示的名称（可选，默认使用文件名）
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="attachmentType">附件类型</Label>
        <Select
          id="attachmentType"
          value={(data.attachmentType as string) || 'image'}
          onChange={(e) => onChange('attachmentType', e.target.value)}
        >
          <option value="image">图片</option>
          <option value="text">文本</option>
          <option value="video">视频</option>
          <option value="json">JSON</option>
          <option value="xml">XML</option>
          <option value="html">HTML</option>
        </Select>
        <p className="text-xs text-muted-foreground">
          附件的类型，影响在报告中的展示方式
        </p>
      </div>
    </>
  )
}

// 结束测试用例配置
export function AllureStopTestConfig({ 
  data, 
  onChange 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="status">测试状态</Label>
        <Select
          id="status"
          value={(data.status as string) || 'passed'}
          onChange={(e) => onChange('status', e.target.value)}
        >
          <option value="passed">通过</option>
          <option value="failed">失败</option>
          <option value="skipped">跳过</option>
          <option value="broken">中断</option>
        </Select>
        <p className="text-xs text-muted-foreground">
          测试用例的最终状态
        </p>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="message">失败原因</Label>
        <VariableInput
          value={(data.message as string) || ''}
          onChange={(v) => onChange('message', v)}
          placeholder="描述失败的原因"
          multiline
        />
        <p className="text-xs text-muted-foreground">
          如果测试失败，可以在此说明原因（可选）
        </p>
      </div>
    </>
  )
}

// 生成测试报告配置
export function AllureGenerateReportConfig({ 
  data, 
  onChange 
}: { 
  data: NodeData
  onChange: (key: string, value: unknown) => void
}) {
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="reportDir">报告目录</Label>
        <PathInput
          value={(data.reportDir as string) || './allure-report'}
          onChange={(v) => onChange('reportDir', v)}
          placeholder="./allure-report"
        />
        <p className="text-xs text-muted-foreground">
          生成的HTML报告存储目录，支持变量
        </p>
      </div>
      
      <div className="flex items-center space-x-2">
        <Checkbox
          id="autoOpen"
          checked={(data.autoOpen as boolean) ?? false}
          onCheckedChange={(checked) => onChange('autoOpen', checked)}
        />
        <Label htmlFor="autoOpen" className="cursor-pointer">
          自动打开报告
        </Label>
      </div>
      <p className="text-xs text-muted-foreground ml-6">
        生成报告后自动在浏览器中打开
      </p>
      
    </>
  )
}
